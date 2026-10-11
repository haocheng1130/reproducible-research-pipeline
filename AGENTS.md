# AGENTS.md: Conventions for Reproducible Research and Data Pipelines

Instructions for AI coding agents (Claude Code, Codex, Cursor, Copilot, Gemini,
and others) working in this repository. They are distilled from UChicago FINM
32800 *Data Pipelines for Quantitative Research* (https://finm-32800.github.io/)
and its `cookiecutter_chartbook` template (source and updates:
https://github.com/haocheng1130/reproducible-research-pipeline). The default
tools are listed below, and any of them can be swapped. The principles stay
fixed. If this repository
already uses a different tool for a role (uv instead of conda, Make instead of
doit), follow the repository.

## The contract
A stranger clones the repo, follows only the README, runs **one command**
(`doit`), and regenerates every dataset, table, figure and number. The tests
then say whether the data and results can be trusted. Do not make a change that
breaks this contract. If a request would break it, say so first.

## Scope: when these conventions apply
They fit **data-centric work**, meaning any project whose output (a dataset,
number, table, chart, model or report) is derived from raw data. Data size is
irrelevant. Typical cases:
- replicating a paper
- building a cleaned research dataset
- factor and signal research
- recurring reports, monitors and dashboards
- production data feeds and reconciliations
- theses and course projects
- models retrained on new data

The more of these hold, the more structure is worth adding: the result must be
reproduced later, data comes from external sources, results refresh with new
data, several people work on the code, someone acts on the numbers.

Use the conventions lightly, or not at all, for:
- **Library or algorithm development:** use standard package conventions.
- **Online services** (low-latency trading, web apps, APIs).
- **Throwaway exploration.**
- **Repos with established conventions:** follow the repo and bring in principles, not a parallel structure.

Some rules help any Python project: settings and `.env`, pinned dependencies,
README run commands, unit tests, CI and code style.

Adopt structure in levels, choosing the lowest that fits and telling the user
which one you chose:

| Level | Situation | Adopt |
|---|---|---|
| 1 | A script you will rerun | Config, a pinned environment, README commands |
| 2 | Shared or multi-step work | + pull/load modules, a `dodo.py` DAG, unit tests, CI |
| 3 | Results others rely on | + validation and replication tests, filter waterfalls, generated report numbers |
| 4 | Scheduled runs | + orchestration, idempotency, drift checks, alerts |

## Principles
1. **One command from a clean clone.** No manual steps and no "run cell 7 first".
2. **Raw data is immutable. Outputs are disposable.** `_data/` (pulled) and
   `_output/` (generated) are gitignored and rebuildable. Irreplaceable data
   goes in `data_manual/` (committed). Hand-made figures go in `assets/`.
3. **Analysis is a DAG.** Every step declares its inputs and outputs in `dodo.py`.
4. **Settings live apart from code.** `src/settings.py` reads the CLI and `.env`
   and supplies defaults. Secrets never enter git. `.env.example` documents every
   variable.
5. **Pull ≠ load.** `pull_*` fetches and returns a DataFrame. `load_*` only reads
   from disk. Saving happens in `if __name__ == "__main__":`.
6. **Keep stages in separate files.** pull → clean (tidy data only) → calc
   (analysis) → create (tables/figures) → report.
7. **Code generates every number.** Do not hand-type statistics into the report,
   README or slides.
8. **Two kinds of tests.** Unit tests use synthetic data with known answers
   (they always run, including in CI). Data-validation and replication tests run
   on real data (they skip when the data is absent). Set tolerances before seeing
   results.
9. **Pin the environment.** Use one environment per project, with `==` pins or a
   lockfile.
10. **Every filter is a convention.** Document its purpose and threshold, count
    what it removes (a waterfall), and use only information available at time *t*.
11. **Keep tasks idempotent and point-in-time.** Overwrite, never append. A rerun,
    retry or backfill gives the same result.
12. **Change through review.** Each change gets a branch, a PR that links its
    issue, CI on the PR, and a reviewer who is not the author.

## Layout
```
README.md  dodo.py  requirements.txt  .env.example  .gitignore  chartbook.toml
.github/workflows/tests.yml
src/settings.py            # the only config module
src/pull_<source>.py       # pull_<x>() + load_<x>()
src/clean_<x>.py           # documented filters -> tidy data + waterfall
src/calc_<x>.py            # pure analysis functions
src/create_<x>.py          # writes .tex/.png/.html exhibits into _output/
src/NN_<topic>.ipynb.py    # jupytext notebooks, executed by doit
src/test_<module>.py       # tests next to the code
data_manual/  assets/  reports/  (committed)
_data/  _output/           (gitignored, rebuildable)
```
Name files by role: `pull_` = external I/O, `load_` = disk read, `clean_` =
filters, `calc_` = analysis, `plot_` = plots only, and `test_` = tests. Use
snake_case.

## Default stack (swappable)
| Role | Default | Swaps |
|---|---|---|
| Environment | conda + `pip install -r requirements.txt` (pinned) | uv + `uv.lock`, pixi + `pixi.lock` |
| DAG | PyDoit `dodo.py` | Make, Snakemake |
| Config | `settings.py` + python-decouple + `.env` | pydantic-settings |
| Storage / frames | Parquet. pandas (<1 GB), Polars lazy (1-100 GB) | DuckDB. Spark (100 GB+) |
| Tests | pytest + doctests | + pandera |
| Notebooks | jupytext percent `*.ipynb.py` | Quarto |
| Report / site | LaTeX `\input{../_output/...}`. ChartBook → GitHub Pages | Quarto, MkDocs |
| CI / schedule / orchestration | GitHub Actions. cron. Airflow | GitLab CI. Dagster/Prefect |

## Patterns to copy

**Config.** Every module reads config like this:
```python
from settings import config
DATA_DIR = config("DATA_DIR")        # absolute Path
END_DATE = config("END_DATE")        # pandas Timestamp
```
Precedence: CLI `--NAME=value` > environment/`.env` > `settings.py` defaults >
in-line default > error. Add every new variable to `.env.example`. Do not call
`os.environ` outside `settings.py`, and never read, print or commit `.env`.

**Pull/load module:**
```python
"""Pull <dataset> from <provider>. Source: <url/table>. Units: ... Grain: ... Quirks: ..."""
import pandas as pd
from settings import config

DATA_DIR = config("DATA_DIR")

def pull_<dataset>(start_date=config("START_DATE"), end_date=config("END_DATE")):
    """Fetch and return a DataFrame with correct dtypes. Pulls only: no saving or printing."""
    import wrds  # heavy or credentialed clients are imported inside the function
    ...
    return df

def load_<dataset>(data_dir=DATA_DIR):
    """Read the cached file. Never pulls; a missing file should raise."""
    return pd.read_parquet(data_dir / "<dataset>.parquet")

if __name__ == "__main__":
    df = pull_<dataset>()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(DATA_DIR / "<dataset>.parquet")
```
In SQL, select only the needed columns, filter in `WHERE`, comment each
condition, and parameterize dates from settings. The pull function owns dtypes,
so downstream code does not cast defensively.

**A doit task:**
```python
def task_clean_data():
    """Filters -> tidy panel + waterfall."""
    return {
        "actions": ["python ./src/clean_x.py"],
        "file_dep": ["./src/settings.py", "./src/pull_x.py", "./src/clean_x.py",
                     DATA_DIR / "x.parquet"],
        "targets": [DATA_DIR / "x_tidy.parquet", OUTPUT_DIR / "x_waterfall.csv"],
        "uptodate": [config_changed({"START_DATE": str(START_DATE), "END_DATE": str(END_DATE)})],
        "clean": True,       # pull tasks use "clean": [] so `doit clean` keeps them
    }
```
List **every** input in `file_dep`, including imported local modules and data.
Settings are not files, so tasks that depend on them need `config_changed`.
Use upstream targets as `file_dep` to order tasks. Run pytest as a task
(`task_test`) before any task that publishes (exhibits, notebooks, report,
site).

**Cleaning:** use one function per filter. Each docstring gives the purpose,
the threshold and the reason for the threshold. Apply filters in a declared
order, and save a waterfall (rows and entities before and after each step) to
`_output/`. Before every merge, assert key uniqueness and use
`validate="many_to_one"` (or whichever cardinality applies). Check row counts
after it.

**Exhibits:** tables are written with `to_latex()` to `_output/*.tex`. Scalars
go in `_output/stats.tex` as `\newcommand{\Name}{value}` (letters-only names).
`plot_*` returns a figure and the caller saves it. Every caption states what
the reader should learn. The report has no code snippets.

**Notebooks:** use jupytext percent format with a YAML header, `# %% [markdown]`
cells whose lines start with `# `, and `# %%` code cells. Notebooks import logic
from modules and never hold the only copy of it. Do not use `sys.path` or
`__file__`. End a cell with a bare `df` to display it. Register each notebook
in `dodo.py` with its `file_dep` and `targets`.

## Tests
- **Unit tests** use tiny synthetic inputs with hand-checkable answers,
  Arrange-Act-Assert, one behavior per test, and descriptive names. Add property
  tests (an optimum beats random portfolios), cross-method checks (numerical =
  closed form), and `pytest.raises` for invalid inputs. Compare floats with
  `np.allclose`/`pytest.approx`. Test SQL `WHERE` logic against a small in-memory
  database.
- **Data-validation tests** cover reconciliation with a second source,
  identities (weights sum to 1, put-call parity), expected waterfall shares,
  coverage through time without unexplained gaps, key uniqueness, dtypes, and
  plausible ranges and units. Show the results in a table or figure with an
  interpretive caption.
- **Replication tests** compare against the paper or authors' numbers within a
  tolerance chosen and justified **before** looking.
- Tests needing data or credentials use
  `pytest.mark.skipif(not PATH.exists(), reason=...)`. Everything else must pass
  in CI.
- **Never** weaken, delete or edit a test or tolerance to make it pass. Report
  the failure and its likely cause.

## Code style
- Each `.py` file opens with a docstring that states its purpose. Use
  descriptive names, never `process_data`, `temp_df` or `df2`.
- Write small pure functions. Avoid classes unless they are clearly needed. Each
  function does one thing.
- Do not add progress `print`s or "saved to ..." messages. Do not add redundant
  `exists()` checks before reading. Do not use broad `try/except` that swallows
  errors.
- Import local modules by full name (`import pull_crsp`, not `as pc`). Use the
  standard aliases `pd`, `np`, `pl`, `plt`, `sns`.
- When refactoring, update every caller and delete dead code. Do not comment it
  out or add compatibility shims.
- Polars code targets ≥ 1.0. Use only APIs available in the pinned versions.

## Anti-patterns (stop and fix)
- Absolute paths (`/Users/...`, `C:\...`). Secrets in code, notebooks, logs or
  git history. A committed `.env`.
- A `load_` that silently pulls. A `pull_` that also saves, cleans or plots.
- Logic that lives only in notebooks. `.ipynb` committed with outputs.
- Hand-copied numbers. Append-mode writes. Silent `dropna()`, filters or merges
  that change row counts.
- Look-ahead (full-sample information in a time-*t* decision) and
  survivorship-biased universes.
- `>=` pins in research repos. Tests that compare code to its own saved output.

## Workflow for agents
1. Read `README.md`, `dodo.py`, `src/settings.py` and `.env.example`, and run
   `doit list` before writing code. Copy the existing pattern for the thing you
   are adding.
2. When adding a data source: write the `pull_`/`load_` module, add a `doit`
   subtask (with `clean: []`), add `.env.example` entries, and add the source to
   the README data table and `chartbook.toml` (sources, providers, license, how
   it is pulled). Then add validation tests.
3. When adding analysis: write `calc_` pure functions with unit tests, then a
   `create_` script and a doit task with exact `file_dep` and `targets`.
4. After changes: run `doit` (or the affected tasks) and `pytest`. Report what
   reran, what failed and why. Never claim a run succeeded without running it.
5. Commit on a feature branch with a clear message. Never commit `_data/`,
   `_output/`, `.env` or licensed raw data.

## Definition of done
- [ ] Fresh clone → README → `doit` succeeds with no manual steps
- [ ] `pytest` passes locally and in CI on every push and PR (credential-only tests skip in CI)
- [ ] Replication tolerances are pre-set and documented. Validation results are shown with captions
- [ ] Every report number is generated by code. Every caption states the takeaway. No code in the report
- [ ] Cleaning is separate from analysis. Every filter is documented and counted
- [ ] All config lives in `settings.py` + `.env.example`. No secrets or licensed data in git history
- [ ] Environment pinned. README has exact setup and run commands
- [ ] Every `.py` file has a purpose docstring
- [ ] Outputs are registered (for example in `chartbook.toml`) with sources, traceable from raw to final
