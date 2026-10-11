"""Run or update the project with PyDoit (`doit`). It works like a Makefile.

    doit            # build everything that is out of date, in dependency order
    doit list       # list tasks
    doit info -s X  # why task X would (not) run
    doit clean      # delete generated outputs (pulls are kept on purpose)
    doit forget X   # force task X to rerun next time

Every task declares its inputs (`file_dep`) and outputs (`targets`), so doit
reruns only what changed. Settings are not files: tasks that depend on
START_DATE/END_DATE use `config_changed` so that changing a date in `.env`
triggers a rebuild.

DAG: config -> pull -> clean_data -> test -> create_exhibits -> run_notebooks
     -> compile_report -> build_site
"""

import sys

sys.path.insert(1, "./src/")

import shutil
from pathlib import Path

from doit.tools import config_changed

from settings import config

DOIT_CONFIG = {"backend": "sqlite3", "dep_file": "./.doit-db.sqlite"}

DATA_DIR = config("DATA_DIR")
OUTPUT_DIR = config("OUTPUT_DIR")
SAMPLE_WINDOW = {
    "START_DATE": str(config("START_DATE")),
    "END_DATE": str(config("END_DATE")),
}


def task_config():
    """Create the _data/ and _output/ directories."""
    return {
        "actions": ["python ./src/settings.py"],
        "file_dep": ["./src/settings.py"],
        "targets": [DATA_DIR, OUTPUT_DIR],
        "clean": [],
    }


def task_pull():
    """Pull raw data from external sources (one subtask per source)."""
    yield {
        "name": "fed_yield_curve",
        "doc": "GSW zero-coupon yield curve from federalreserve.gov",
        "actions": ["python ./src/pull_fed_yield_curve.py"],
        "file_dep": ["./src/settings.py", "./src/pull_fed_yield_curve.py"],
        "targets": [DATA_DIR / "fed_yield_curve.parquet"],
        "verbosity": 2,
        # Pulls can be slow or need credentials, so `doit clean` keeps them.
        # Force a fresh pull with `doit forget pull` (or delete the file).
        "clean": [],
    }


def task_clean_data():
    """Apply the documented filter chain; write the tidy panel and the waterfall."""
    return {
        "actions": ["python ./src/clean_yield_curve.py"],
        "file_dep": [
            "./src/settings.py",
            "./src/pull_fed_yield_curve.py",
            "./src/clean_yield_curve.py",
            DATA_DIR / "fed_yield_curve.parquet",
        ],
        "targets": [
            DATA_DIR / "yield_curve_tidy.parquet",
            OUTPUT_DIR / "yield_curve_waterfall.csv",
        ],
        "uptodate": [config_changed(SAMPLE_WINDOW)],
        "clean": True,
    }


def task_test():
    """Run unit tests and data-validation tests before anything is published."""
    return {
        # List-form actions run without a shell, so paths with spaces are safe.
        "actions": [["pytest", f"--junitxml={OUTPUT_DIR / 'pytest_results.xml'}"]],
        "file_dep": [
            *sorted(Path("./src").glob("*.py")),
            DATA_DIR / "yield_curve_tidy.parquet",
            OUTPUT_DIR / "yield_curve_waterfall.csv",
        ],
        "targets": [OUTPUT_DIR / "pytest_results.xml"],
        "verbosity": 2,
        "clean": True,
    }


def task_create_exhibits():
    """Write tables, figures and report macros into _output/."""
    return {
        "actions": ["python ./src/create_exhibits.py"],
        "file_dep": [
            "./src/settings.py",
            "./src/pull_fed_yield_curve.py",
            "./src/clean_yield_curve.py",
            "./src/calc_yield_curve_stats.py",
            "./src/create_exhibits.py",
            DATA_DIR / "yield_curve_tidy.parquet",
            OUTPUT_DIR / "yield_curve_waterfall.csv",
        ],
        "targets": [
            OUTPUT_DIR / "summary_table.tex",
            OUTPUT_DIR / "waterfall_table.tex",
            OUTPUT_DIR / "term_spread.png",
            OUTPUT_DIR / "stats.tex",
        ],
        "task_dep": ["test"],
        "clean": True,
    }


# Register each jupytext notebook with the modules and data it reads.
notebook_tasks = {
    "01_data_tour.ipynb.py": {
        "path": "./src/01_data_tour.ipynb.py",
        "file_dep": [
            "./src/settings.py",
            "./src/pull_fed_yield_curve.py",
            "./src/clean_yield_curve.py",
            "./src/calc_yield_curve_stats.py",
            DATA_DIR / "yield_curve_tidy.parquet",
            OUTPUT_DIR / "yield_curve_waterfall.csv",
        ],
        "targets": [],
    },
}


def task_run_notebooks():
    """Convert *.ipynb.py to .ipynb, execute it, export HTML, move it to _output/."""
    for key, spec in notebook_tasks.items():
        pyfile = Path(spec["path"])
        notebook = pyfile.with_suffix("")  # strips .py, leaves .ipynb
        yield {
            "name": key,
            "actions": [
                ["jupytext", "--to", "notebook", "--output", notebook, pyfile],
                # Execute in place so the notebook runs from src/ and can import modules.
                ["jupyter", "nbconvert", "--execute", "--to", "notebook",
                 "--ClearMetadataPreprocessor.enabled=True", "--inplace", notebook],
                ["jupyter", "nbconvert", "--to", "html", f"--output-dir={OUTPUT_DIR}", notebook],
                (shutil.move, [str(notebook), str(OUTPUT_DIR / notebook.name)]),
            ],
            "file_dep": [pyfile, *spec["file_dep"]],
            "targets": [
                OUTPUT_DIR / f"{notebook.stem}.html",
                OUTPUT_DIR / notebook.name,
                *spec["targets"],
            ],
            "task_dep": ["test"],
            "clean": True,
        }


def task_compile_report():
    """Compile reports/report.tex (needs a LaTeX distribution with latexmk + xelatex)."""
    return {
        "actions": [
            "latexmk -xelatex -halt-on-error -cd ./reports/report.tex",
            "latexmk -xelatex -halt-on-error -c -cd ./reports/report.tex",
        ],
        "file_dep": [
            "./reports/report.tex",
            OUTPUT_DIR / "summary_table.tex",
            OUTPUT_DIR / "waterfall_table.tex",
            OUTPUT_DIR / "term_spread.png",
            OUTPUT_DIR / "stats.tex",
        ],
        "targets": ["./reports/report.pdf"],
        "clean": True,
    }


def task_build_site():
    """Build the ChartBook documentation site into docs/ (browse with `chartbook browse`)."""
    return {
        "actions": ["chartbook build -f"],
        "file_dep": [
            "./README.md",
            "./chartbook.toml",
            *[OUTPUT_DIR / Path(spec["path"]).with_suffix("").name
              for spec in notebook_tasks.values()],
        ],
        "targets": ["./docs/index.html"],
        "clean": True,
    }
