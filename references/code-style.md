# Code Style

These rules come from the course template's AI-assistant rules
(`.cursor/rules/base-data-science-project.mdc` and the `.claude/skills` in
`cookiecutter_chartbook`) and from the final-project rubric. They are written
for research data code: readable by the next analyst, testable, and quiet.

## Files and modules
- **Every `.py` file starts with a docstring** that says what the file is for, where its
  data comes from, and how to run it (`python src/x.py` or `doit <task>`).
- **Separate concerns, without going overboard.** At minimum, use one pull file per
  external source, cleaning separate from analysis, and outputs written by
  dedicated scripts. Put project-specific cleaning in its own file. Keep cleaning
  that every future project will reuse with the pull/load code.
- **Use config only through `settings`.** Write `from settings import config` and then
  `DATA_DIR = config("DATA_DIR")`.
- **Avoid global filename constants** (`INPUT_FILENAME = "..."`). Build the path
  where it is used, in `__main__` or in the function, so each script reads
  standalone. (Exception: a value shared by several functions in the module,
  such as a ticker list or a URL.)

## Functions
- **Use a functional style.** Prefer pure functions: inputs in, outputs out, no
  side effects, no reliance on variables defined out of scope. Avoid classes
  unless there is a strong reason (state that must persist, or a real
  interface).
- **Each function does one thing.** Break large multi-step functions into small,
  well-named steps. That improves readability and testability.
- **Prefixes promise behavior:**
  - `pull_*` fetches from the outside world. It only pulls (it does not save, clean or plot).
  - `load_*` reads from disk. It never pulls, and a missing file raises an error.
  - `plot_*` plots and does nothing else (it does not save, compute or load).
  - `calc_*`/`compute_*` compute. `clean_*`/`drop_*`/`filter_*` filter.
  - `test_*` tests.
- **Use descriptive names** that say what something is: `book_equity`,
  `nyse_size_breakpoints`, `drop_trades_after_maturity`. Avoid `process_data`,
  `pipeline`, `temp_df`, `df2` and `stuff`.
- Use snake_case, never camelCase.
- Write docstrings for public functions, with an example or doctest where it
  clarifies the function.

## Imports
- Import your own modules by full name: `import pull_options_data`, not
  `import pull_options_data as pod`.
- Use the conventional aliases for common libraries: `import pandas as pd`,
  `import numpy as np`, `import polars as pl`,
  `from matplotlib import pyplot as plt`, `import seaborn as sns`.
- Import heavy or credential-requiring clients (`wrds`, `xbbg`) inside the
  function that needs them, so the rest of the module imports anywhere.

## Quiet code
- **No progress prints** ("Pulling S&P CUSIP table...") and no "Saved to ..."
  confirmations. A script that finishes without an error has succeeded. Use
  `logging` if a long job truly needs progress, and keep it off by default.
- **No redundant existence checks** before reading. `pd.read_parquet` /
  `pl.read_parquet` already raise a clear `FileNotFoundError`.
- **No defensive type casting downstream** (`strict=False`, blanket
  `astype(str)`). Fix types once, in the `pull_` function.
- **No broad `try/except`** that hides failures. Let the pipeline fail loudly.
  Catch only specific exceptions you can handle meaningfully.

## Refactoring
- When splitting or renaming, update every caller. **Do not keep old functions
  around for compatibility.**
- **Delete dead code.** Do not comment it out, because git remembers it.
- Keep a refactor in its own commit or PR, separate from behavior changes.

## Library versions
- Write Polars code for **Polars ≥ 1.0** (`group_by`, `pl.len()`, `with_columns`).
- pandas: avoid chained assignment. Use `.loc`/`assign`. Use `validate=` in
  `merge`.
- Match the pinned versions in `requirements.txt`, and do not use APIs newer than
  the pins.

## Formatting
- Use `ruff`/`black` defaults (line length 88). The template's `pyproject.toml`
  configures `ruff` with `select = ["E", "F", "I"]`.
- `# fmt: off` / `# fmt: on` is acceptable around aligned config blocks.

## Notebooks (`*.ipynb.py`)
- Use jupytext percent format with a YAML header. Markdown cells use
  `# %% [markdown]` + `# ` lines.
- Do not use `sys.path` or `__file__`. Rely on the DAG running from `src/`.
- End a cell with the object to display it. Do not use `print(df)`. Use `.glimpse()` for wide
  Polars frames.
- Do not add defensive programming. Assume inputs exist, because the DAG guarantees them.
