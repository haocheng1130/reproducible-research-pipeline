# The Task DAG with PyDoit

## Why a task runner
A build file gives you **reproducibility** (it records the order steps run in),
**dependency tracking** (which script produces which file), **incremental
reruns** (only stale steps rerun), **early error stops** (validation fails the
build before bad data spreads), **standardization** (everyone runs it the same
way), **parallelism** (the DAG shows what can run at once), and
**documentation** (the build file *is* the workflow). Use one even when working
alone. Future-you is a collaborator.

PyDoit is the course default because it is plain Python. Make, Snakemake and
others work the same way. `uv run`/`pixi run` only pick the environment and do
not track dependencies, so they wrap `doit`, they do not replace it (for
example `uv run doit`).

## Anatomy
```python
# dodo.py  (run `doit` from the repo root)
import sys
sys.path.insert(1, "./src/")          # dodo.py may do this; notebooks/modules must not

from doit.tools import config_changed
from settings import config

DOIT_CONFIG = {"backend": "sqlite3", "dep_file": "./.doit-db.sqlite"}
DATA_DIR = config("DATA_DIR")
OUTPUT_DIR = config("OUTPUT_DIR")


def task_config():
    """Create _data/ and _output/."""
    return {
        "actions": ["python ./src/settings.py"],
        "file_dep": ["./src/settings.py"],
        "targets": [DATA_DIR, OUTPUT_DIR],
        "clean": [],
    }


def task_pull():
    """Pull raw data (one subtask per source)."""
    yield {
        "name": "fed_yield_curve",
        "doc": "GSW yield curve from federalreserve.gov",
        "actions": ["python ./src/pull_fed_yield_curve.py"],
        "file_dep": ["./src/settings.py", "./src/pull_fed_yield_curve.py"],
        "targets": [DATA_DIR / "fed_yield_curve.parquet"],
        "clean": [],      # `doit clean` must not delete expensive pulls
    }


def task_clean_data():
    """Filters -> tidy panel + filter waterfall."""
    return {
        "actions": ["python ./src/clean_yield_curve.py"],
        "file_dep": [
            "./src/settings.py",                    # every local module the script imports
            "./src/pull_fed_yield_curve.py",
            "./src/clean_yield_curve.py",
            DATA_DIR / "fed_yield_curve.parquet",   # target of task_pull -> implicit ordering
        ],
        "targets": [DATA_DIR / "yield_curve_tidy.parquet", OUTPUT_DIR / "yield_curve_waterfall.csv"],
        "uptodate": [config_changed({"START_DATE": str(config("START_DATE")),
                                     "END_DATE": str(config("END_DATE"))})],
        "clean": True,
    }
```

### Task dictionary keys
| Key | Meaning |
|---|---|
| `actions` | Shell strings, argument lists (run without a shell, so paths with spaces are safe), or Python callables (`func` or `(func, args, kwargs)`). They run in order, and the first failure stops the task. |
| `file_dep` | Input files. The task reruns if any changed since the last success (MD5 by default). **List every input**, including imported helper modules and data files. |
| `targets` | Output files. The task reruns if any is missing. A task whose `file_dep` matches another task's `targets` automatically runs after it. |
| `task_dep` | Run these tasks first. This orders execution but does not make the task stale. Prefer `file_dep` on real files when possible. |
| `uptodate` | Extra conditions: `config_changed(value)`, `run_once`, `False` (always run), or a callable. |
| `clean` | `True` lets `doit clean` delete the targets. `[]` makes it a no-op (use this for pulls). A list of actions means custom cleanup. |
| `verbosity` | 0 captures all output, 1 (default) shows stderr, 2 shows everything. Use 2 for long pulls and LaTeX. |
| `name` | Required for subtasks (`yield`). Run one with `doit pull:fed_yield_curve`. |
| `doc` | Shown by `doit list`. The function docstring also works. |

### Up-to-date rules (what reruns and why)
- A task with **no `file_dep` and no `uptodate`** always runs.
- A task reruns if any `file_dep` changed, any `target` is missing, or any `uptodate` condition is false.
- **Settings are not files.** Changing `END_DATE` in `.env` does nothing unless the task has `uptodate=[config_changed({...})]`. This is a classic exam and interview question: "what reruns if END_DATE changes, and how does doit know?"
- A stale upstream target makes downstream tasks rerun because their `file_dep` content changes. That is the DAG doing its job.

## Commands
```bash
doit                 # run all default tasks in dependency order
doit list            # list tasks (add --all to include subtasks)
doit info -s <task>  # show deps/targets and why it would (not) run
doit <task>          # run one task (+ what it depends on)
doit pull:fed_yield_curve   # one subtask
doit clean           # delete targets of tasks with clean=True
doit clean <task>    # clean one task
doit forget <task>   # forget state so it reruns next time (doit forget --all)
doit -n 4            # run up to 4 tasks in parallel (tasks must be independent and safe)
```

## Notebook tasks (jupytext → execute → HTML)
```python
notebook_tasks = {
    "01_data_tour.ipynb.py": {
        "path": "./src/01_data_tour.ipynb.py",
        "file_dep": ["./src/clean_yield_curve.py", "./src/calc_yield_curve_stats.py",
                     DATA_DIR / "yield_curve_tidy.parquet"],
        "targets": [],
    },
}

def task_run_notebooks():
    """Convert *.ipynb.py -> .ipynb, execute it, export HTML into _output/."""
    for key, spec in notebook_tasks.items():
        pyfile = Path(spec["path"])
        nb = pyfile.with_suffix("")            # .../01_data_tour.ipynb
        yield {
            "name": key,
            "actions": [
                # list-form actions run without a shell: safe for paths with spaces
                ["jupytext", "--to", "notebook", "--output", nb, pyfile],
                # executed in place so it runs from src/ and can import modules
                ["jupyter", "nbconvert", "--execute", "--to", "notebook",
                 "--ClearMetadataPreprocessor.enabled=True", "--inplace", nb],
                ["jupyter", "nbconvert", "--to", "html", f"--output-dir={OUTPUT_DIR}", nb],
                (shutil.move, [str(nb), str(OUTPUT_DIR / nb.name)]),
            ],
            "file_dep": [pyfile, *spec["file_dep"]],
            "targets": [OUTPUT_DIR / f"{nb.stem}.html", OUTPUT_DIR / nb.name,
                        *spec["targets"]],
            "clean": True,
        }
```
The `.py` source is what gets diffed and tracked, so metadata-only changes
never trigger reruns.

## Tests inside the DAG
Validation runs **before** publishing. Then a failed check stops the build
before a corrupted table reaches the report or the site.
```python
def task_test():
    """Run pytest (unit + data validation). Publishing tasks depend on this."""
    return {
        "actions": [["pytest", f"--junitxml={OUTPUT_DIR / 'pytest_results.xml'}"]],
        "file_dep": [*Path("./src").glob("*.py"), DATA_DIR / "yield_curve_tidy.parquet"],
        "targets": [OUTPUT_DIR / "pytest_results.xml"],
        "verbosity": 2,
        "clean": True,
    }
```
Note: pytest writes the XML even when tests fail. doit records the task as
failed because the action failed, so it reruns next time.

## LaTeX report task
```python
def task_compile_report():
    """Compile reports/report.tex into a PDF after outputs and tests are ready."""
    return {
        "actions": [
            "latexmk -xelatex -halt-on-error -cd ./reports/report.tex",
            "latexmk -xelatex -halt-on-error -c -cd ./reports/report.tex",  # remove aux files
        ],
        "file_dep": ["./reports/report.tex", OUTPUT_DIR / "summary_table.tex",
                     OUTPUT_DIR / "stats.tex", OUTPUT_DIR / "term_spread.png"],
        "targets": ["./reports/report.pdf"],
        "task_dep": ["test"],
        "clean": True,
    }
```

## ChartBook / site task
```python
def task_build_site():
    """Build the ChartBook docs site into docs/."""
    return {
        "actions": ["chartbook build -f"],
        "file_dep": ["./README.md", "./chartbook.toml",
                     *[Path(s["path"]) for s in notebook_tasks.values()]],
        "targets": ["./docs/index.html"],
        "task_dep": ["run_notebooks", "test"],
        "clean": True,
    }
```

## Debugging a DAG
| Symptom | Likely cause | Fix |
|---|---|---|
| Changed a setting, nothing reran | Settings are not file deps | `uptodate=[config_changed(...)]` |
| Edited a helper module, outputs are stale | Helper missing from `file_dep` | Add every imported local module |
| Task reruns every time | No `file_dep`, a target written to a different path than declared, or a non-deterministic target name (dates in filenames) | Declare exact targets and stable names |
| `doit clean` wiped hours of pulls | Pull task had `clean: True` | Use `clean: []` for pulls |
| Works for you, fails for a teammate | Absolute paths, unpinned env, `.env`-only variables without defaults | `settings.py` defaults + `.env.example` + pins |
| Tasks run in the wrong order | Dependency only implied by naming | Use the upstream target as a `file_dep` |

## On HPC / schedulers
The course's older `blank_project` dodo.py switches off its colored console
reporter when `SLURM_JOB_ID` is set, because batch logs do not render ANSI colors. Pull tasks need internet, and
many compute partitions have none. Run `doit pull` on a node with internet and
the remaining tasks anywhere (see `scale-and-automation.md`).
