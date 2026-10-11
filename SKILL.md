---
name: reproducible-research-pipeline
description: Conventions for reproducible, data-centric research and data pipelines (any data size) - project layout, settings and .env, pull_/load_ data modules, a doit task DAG, pytest unit and data-validation tests, jupytext notebooks, code-generated LaTeX/ChartBook outputs, and CI. Use when creating, extending, refactoring or reviewing a repo whose output is a dataset, table, chart, model or report built from raw data - replicating a paper, building a research dataset, factor research, recurring reports or monitors, production data feeds, theses and course projects - or when adding a data source, cleaning step, analysis, test, notebook or report. Not for library development, online services, or throwaway exploration.
---

# Reproducible Research Pipeline

Distilled from UChicago FINM 32800 *Data Pipelines for Quantitative Research*
(Jeremy Bejarano, https://finm-32800.github.io/) and its project template
(`backofficedev/cookiecutter_chartbook`). The course stack is the default.
Every tool can be swapped for another. The principles stay fixed.
Source and updates: https://github.com/haocheng1130/reproducible-research-pipeline

## The contract

> A stranger clones the repo, follows only the README, runs **one command**, and
> regenerates every dataset, table, figure and number in the report. The tests
> then tell them whether the data and the results can be trusted.

Every rule below serves this contract. When a request conflicts with it, say so
before writing code.

## When to use this skill

It fits **data-centric work**: any project whose output is a dataset, number,
table, chart, model or report derived from raw data. The *size* of the data
does not matter. A 5 MB FRED pull needs the same discipline as a 400 GB TRACE
panel. The more of these signals apply, the more of the skill is worth using:

- The result must be **reproduced** later, by someone else or by you in six months.
- Data comes from **external sources** (WRDS, Bloomberg, vendor APIs, the web) and needs cleaning.
- Results are **refreshed** when new data arrives (daily, monthly, each quarter).
- **Several people** work on the code, or it will be handed over.
- Someone **acts on the numbers**: a PM, a risk committee, a referee, a client, a grader.

### Typical scenarios

| Scenario | Examples | What the skill contributes |
|---|---|---|
| Replicating a paper | Fama-French factors, GSW yield curve, VPIN | Charter, replication tests with pre-set tolerances, update vs. extension |
| Building a research dataset | Cleaned TRACE panel, CRSP-Compustat merge, option-implied measures | Pull/load modules, filter waterfall, validation tests, dataset docs |
| Factor and signal research | Anomaly signals, return predictors, backtest inputs | Point-in-time discipline, pure `calc_` functions, look-ahead checks |
| Recurring reports and monitors | Monthly risk report, daily FedWatch-style monitor, dashboards | Generated exhibits, validation before publishing, scheduled rebuilds, CI |
| Production data pipelines | Vendor ingestion, reconciliation jobs, a firm's data feeds | Idempotent tasks, data checks that stop the run, orchestration |
| Theses, course projects, papers | Final projects, dissertation chapters, working papers | One-command rebuild, LaTeX report whose numbers come from code |
| Models in production | Forecasts retrained on new data | Experiment tracking, drift checks, monitoring |
| Inheriting or reviewing a repo | "Make this reproducible", code review | Audit script, Definition of Done |

### When not to use it, or use it lightly

- **Library or algorithm development** (a pricing library, an optimizer): use
  standard package conventions (`pyproject.toml`, tests, versioning). Only the
  testing, packaging and style rules apply.
- **Online services** (low-latency trading systems, web apps, APIs): their
  concerns are latency, uptime and state, which this skill does not cover.
- **Throwaway exploration** (a quick chart, a sanity check): a notebook is fine.
  Adopt the structure once the work has to be rerun or shared.
- **Repos with established conventions**: follow the repo. Bring in the
  principles, not a parallel structure, and do not migrate tools unless asked.

Some rules help any Python project, whatever its type: config and secrets in
`settings.py` + `.env`, a pinned environment, a README with run commands, unit
tests, CI and the code style. Outside the scope above, apply only those.

### How much structure to adopt

| Level | Situation | Adopt |
|---|---|---|
| 1 | A script you will rerun (personal analysis) | `settings.py` + `.env`, pinned environment, README run commands, no hard-coded paths |
| 2 | Shared or multi-step work (team project, homework) | + pull/load modules, `dodo.py` DAG, unit tests, CI |
| 3 | Results others rely on (paper, report, research dataset) | + validation and replication tests, filter waterfalls, numbers generated into the report, output catalog |
| 4 | Runs on a schedule (production feed, monitor, live model) | + scheduling or orchestration, idempotent tasks, drift checks, alerts, experiment tracking |

Pick the lowest level that fits the task, and tell the user which level you
are applying. Do not impose level 3 on a level 1 request. Suggest moving up a
level when the signals above appear.

## Principles

| # | Principle | What it means in practice |
|---|-----------|---------------------------|
| P1 | **One command from a clean clone** | `doit` (or the project's runner) builds everything. No manual steps, no "run cell 7 first". |
| P2 | **Raw data is immutable. Outputs are disposable.** | `_data/` (pulled) and `_output/` (generated) can be deleted and rebuilt, and are never committed. Data that cannot be re-pulled goes in `data_manual/` (version-controlled). Hand-made figures go in `assets/`. |
| P3 | **Analysis is a DAG** | Every step declares its inputs (`file_dep`) and outputs (`targets`). The runner decides what to rerun. |
| P4 | **Settings live apart from code** | A single `src/settings.py` reads `.env` and the CLI and supplies defaults. Secrets never enter git. `.env.example` documents every variable. |
| P5 | **Pull ≠ load** | `pull_*` talks to the outside world and returns a DataFrame. `load_*` only reads from disk. Saving happens in `if __name__ == "__main__":`. |
| P6 | **Keep stages in separate files** | Pull → clean (tidy data only) → calc/analysis → tables/charts → report. Cleaning code never does analysis. |
| P7 | **Code generates every number** | No hand-typed statistics in the report, README or slides. Tables and numbers are generated `.tex`/`.md` files that the report `\input`s. |
| P8 | **Two kinds of tests** | *Unit tests* use synthetic data with known answers and run anywhere, including CI. *Data-validation tests* check real data against independent knowledge. Set replication tolerances **before** seeing results. |
| P9 | **Pin the environment** | One environment per project. Pin exact versions (`==`) or use a lockfile. Unpinned upgrades silently change results. |
| P10 | **Every filter is a convention** | Document why each filter exists, count the rows it removes, and make each removal visible (a waterfall). Use only information available at time *t* (no look-ahead). |
| P11 | **Idempotent, point-in-time tasks** | A rerun overwrites its output and never appends. Retries and backfills must produce the same result as a timely run. |
| P12 | **Change through review** | Each feature gets a branch, a PR that links its issue, CI on the PR, and a reviewer other than the author. |

## Default layout

```
project/
├── README.md              # what/why, quick start (env + `doit`), data sources, outputs
├── dodo.py                # the DAG (PyDoit). `doit list` shows every task
├── requirements.txt       # pinned with == (or pyproject.toml + uv.lock / pixi.toml + pixi.lock)
├── .env.example           # every config var, dummy values, comments. COMMITTED
├── .env                   # real values and secrets. NEVER COMMITTED (and never in history)
├── .gitignore             # ignores /_data/*, /_output/*, .env*, !.env.example, .doit-db*
├── chartbook.toml         # optional: registry of dataframes/charts/notebooks and their sources
├── .github/workflows/     # CI: pytest on every push and PR
├── src/
│   ├── settings.py        # single source of config: `from settings import config`
│   ├── pull_<source>.py   # pull_<x>() + load_<x>() per external source
│   ├── clean_<x>.py       # project-specific filters → tidy data
│   ├── calc_<x>.py        # analysis / model / replication logic (pure functions)
│   ├── create_<table|chart>_<x>.py  # writes .tex/.html/.png into _output/
│   ├── NN_<topic>.ipynb.py    # jupytext notebooks (tours/reports, not core logic)
│   ├── misc_tools.py      # small generic helpers
│   └── test_<module>.py   # tests sit next to the code
├── data_manual/           # irreplaceable, hand-made or licensed-to-keep small data. COMMITTED
├── assets/                # hand-drawn figures and logos. COMMITTED
├── reports/               # LaTeX sources. They \input generated files from ../_output
├── _data/                 # pulled data. GITIGNORED, safe to delete
└── _output/               # generated tables, figures, executed notebooks. GITIGNORED
```

Naming: `pull_` = external I/O, `load_` = disk read, `clean_` = filters,
`calc_` = analysis, `create_`/`chart_`/`table_` = outputs, `plot_` = plots and
nothing else, `test_` = tests. Use snake_case everywhere. Prefix notebooks with
`01_`, `02_`, and so on.

## Default stack and swaps

| Concern | Course default | Swaps (keep the principle) |
|---|---|---|
| Environment | conda env + `pip install -r requirements.txt` (pinned `==`) | uv (`pyproject.toml` + `uv.lock`), pixi (conda-forge, `pixi.lock`) |
| In-project DAG | PyDoit `dodo.py` | Make, Snakemake. `uv run doit` / pixi task calling doit |
| Config | `settings.py` + python-decouple + `.env` | pydantic-settings, hydra (same precedence idea) |
| Storage | Parquet in `_data/`, hive-partitioned when big | DuckDB file, warehouse tables |
| DataFrames | pandas (<1 GB), Polars lazy (1-100 GB) | DuckDB SQL. Spark/Dask (100 GB+) |
| Tests | pytest + doctests (`pytest --doctest-modules`) | add pandera/great_expectations for data contracts |
| Notebooks | jupytext percent `*.ipynb.py`, executed by the DAG | Quarto, marimo |
| Report | LaTeX + `latexmk`, `\input{../_output/...}` | Quarto/Markdown → PDF/Word |
| Catalog/site | ChartBook → GitHub Pages | Sphinx/MkDocs, internal catalog |
| CI/CD | GitHub Actions (tests on push/PR, scheduled rebuilds) | GitLab CI, Jenkins |
| Cross-project orchestration | Apache Airflow (asset-triggered, retries, backfill) | Dagster, Prefect |
| Experiment tracking | MLflow, logged from inside a DAG task | Weights & Biases |
| Big compute | SSH + SLURM (`sbatch`). Pulls on a node with internet, processing offline | cloud batch |

If a repo already uses a swap, follow the repo. Do not migrate tools unless asked.

## Agent playbook

### 0. Before touching code in an existing repo
1. Read `README.md`, `dodo.py`, `src/settings.py`, `.env.example`, and `chartbook.toml` if it exists. Run `doit list`.
2. Find the existing pattern for the thing you are adding (another `pull_*.py`, another task) and **copy its shape**. Do not invent a parallel structure.
3. Never read, print or commit `.env`. Ask for credentials through `.env.example` entries instead.

### 1. Starting a project
1. Write a five-line **charter** in the README first: (a) the claim or target in one sentence, (b) what existing work lacks, (c) what will be built, (d) who would clone it and what they would do with it, (e) how success is verified, including what the data-validation tests will check.
2. Scaffold the layout above. Start from `cruft create https://github.com/backofficedev/cookiecutter_chartbook`, or copy `templates/project/` from this skill.
3. Create the environment, pin it, and make `doit` and `pytest` pass on the empty skeleton before adding research code.

### 2. Adding a data source
1. Create `src/pull_<source>.py`. Its module docstring states what the data is, where it comes from, links to the vendor docs, the identifiers and their quirks, and the units.
2. `pull_<dataset>(start_date=..., end_date=..., ...)` returns a DataFrame and does **nothing else** (no saving, no printing). In the SQL, select only the needed columns and filter in `WHERE`. **This function owns dtypes.** Cast dates, numerics and categoricals here so downstream code can trust them.
3. `load_<dataset>(data_dir=DATA_DIR)` only reads the parquet. If the file is missing, it fails loudly. It never falls back to pulling.
4. In `if __name__ == "__main__":`, call `pull_`, create `DATA_DIR`, and write `DATA_DIR / "<dataset>.parquet"`.
5. Add a `doit` subtask with `file_dep=[settings.py, pull file]`, `targets=[parquet]`, and `clean: []`, so that `doit clean` does not delete expensive pulls. If the pull depends on settings such as dates, add `uptodate=[config_changed({...})]`.
6. Add each new credential to `.env.example`. Add the source to the README data table and to `chartbook.toml` (sources, providers, license, how it is pulled).
7. Optional: offer a cached-extract path, so the repo runs without credentials (`NO_CACHE=False` downloads a cached copy, `True` pulls live).

### 3. Adding cleaning or transformation
- Put project-specific filters in `src/clean_<x>.py`, as small named functions, one filter each. Each filter's docstring states its **purpose** and **threshold**, and why the threshold was chosen.
- Log a **filter waterfall**: the row count (and unique entity count) before and after each filter. Write it to `_output/` as a table.
- If a cleaning step is universal to the source and every future project would reuse it (for example a CRSP-Compustat merge), keep it in the `pull_` module.
- Check key uniqueness and row counts before and after every merge. An unexpected change in row count is a bug.
- Use only information available at the observation's date. Use point-in-time identifiers, lagged accounting data and ex-ante breakpoints.

### 4. Adding analysis, tables, figures and report numbers
- Put the logic in `calc_*.py` as pure functions (DataFrame in, DataFrame or array out) so it is unit-testable.
- Output scripts read only through `load_*`, write only to `OUTPUT_DIR`, and are registered as `doit` tasks with exact `file_dep` and `targets`.
- Put report numbers in generated files: tables go in `_output/<name>.tex` and scalars in an `_output/stats.tex` of `\newcommand`s. The LaTeX file `\input`s them.
- Give every table and figure a caption that states what the reader should learn. Do not put code snippets in the report.

### 5. Adding a notebook
- Author it as `src/NN_topic.ipynb.py` in jupytext percent format. Register it in `dodo.py`'s notebook dict with its `file_dep` (the modules and data it uses) and `targets`. The DAG converts it, executes it, exports HTML, and moves the result to `_output/`.
- A notebook *tours* data and results. It imports logic from modules and never becomes the only home of logic.
- Do not manipulate `sys.path` or use `__file__`. End a cell with a bare `df` to display it. Do not add defensive file checks.

### 6. Writing tests (see `references/testing-and-validation.md`)
- **Unit tests** use tiny synthetic inputs with hand-checkable answers and Arrange-Act-Assert, with one behavior per test and a descriptive name. Also test properties, for example "the GMV portfolio beats 500 random portfolios", and expected exceptions with `pytest.raises`.
- **Data-validation tests** cover reconciliation with a second source, identities (weights sum to 1, put-call parity), the expected number of rows each filter removes, coverage through time with no unexplained gaps, key uniqueness, and plausible ranges.
- **Replication tests** compare against the paper's or the authors' numbers within a tolerance that was set and justified in advance.
- Tests that need credentials or pulled data use `pytest.mark.skipif` so CI stays green and meaningful. Everything else must run in CI, on small samples if needed.
- Run the tests inside the DAG (a `task_test` that runs pytest) so every rebuild checks itself before publishing.
- Tests are the specification. Never weaken a test or its tolerance to make it pass. Report the failure instead.

### 7. Changing configuration
- Add new variables to `settings.py` defaults **and** to `.env.example`. Read them with `config("NAME")`. Never call `os.environ` in random modules.
- Precedence: CLI `--NAME=value` > environment variable or `.env` > `settings.py` defaults > in-line default > error.
- `file_dep` tracks files, not settings. Any task whose output depends on a setting needs `uptodate=[config_changed(...)]`, or a change to `END_DATE` will not trigger a rebuild.

### 8. Reviewing or auditing a repo
Run `python scripts/audit_pipeline.py <repo>` from this skill for a static check. Then confirm the Definition of Done by hand.

## Code style (summary; full rules in `references/code-style.md`)
- Each `.py` file opens with a docstring that states its purpose. Functions have descriptive names (not `process_data` or `temp_df`) and docstrings where helpful.
- Prefer small pure functions with no side effects and no reliance on out-of-scope variables. Avoid classes unless clearly justified.
- Do not add `print` progress chatter or "saved to ..." messages. Do not add redundant `Path.exists()` checks before reading, because the reader raises a clear error itself.
- Import your own modules by full name (`import pull_crsp`, not `as pc`). Use the standard aliases `pd`, `np`, `plt`, `sns`, `pl`.
- When refactoring, update every caller and delete old code. Do not comment it out or keep compatibility shims.
- Write Polars code for Polars ≥ 1.0.

## Anti-patterns (stop and fix)
- Hard-coded absolute paths (`/Users/...`, `C:\...`) or paths built from the current working directory.
- Credentials in code, notebooks, logs or git history. `.env` committed, even once.
- A `load_` that silently hits the network, or a `pull_` that also saves, cleans and plots.
- Logic that lives only in a notebook. `.ipynb` files committed with outputs.
- Numbers copied by hand into the report or README.
- Append-mode writes, and outputs that depend on run order or wall-clock time without being recorded.
- Silent `dropna()`, filters or merges that change row counts with no record.
- Full-sample information used in a time-*t* decision (look-ahead), and survivorship-biased universes.
- `>=` dependency floors in a research repo. Mixing package managers in one env without recording it.
- Broad `try/except` that swallows errors so the pipeline "succeeds" with bad data.
- Tests that compare code to its own saved output, tolerances tuned after seeing results, or tests silently deleted.

## Definition of done (pipeline or research repo)
- [ ] Fresh clone → README steps → `doit` succeeds with no manual intervention
- [ ] `pytest` passes locally, and CI runs it on every push and PR (credential-only tests skip in CI)
- [ ] Replication tests have pre-set, documented tolerances. Validation tests check data against independent facts, and their results appear as a table or figure with an interpretive caption
- [ ] Every number in the report comes from code. Every exhibit has a caption saying what to learn
- [ ] Data cleaning is in its own files. Analysis is in separate files. Every filter is documented and counted
- [ ] `settings.py` + `.env.example` cover all config (data dir, credentials, `START_DATE`, `END_DATE`, ...)
- [ ] No secrets, `.env`, or licensed raw data anywhere in git history
- [ ] Environment pinned. README gives exact setup and run commands
- [ ] Every `.py` file has a purpose docstring. Function names say what they do
- [ ] Outputs are registered (`chartbook.toml` or equivalent) with sources, so a reader can trace raw → final

## References (load on demand)
- `references/project-structure.md`: layout, what is committed vs ignored, naming, README skeleton
- `references/config-and-secrets.md`: the settings.py pattern, precedence, `.env`, the cached-extract switch
- `references/data-pulls-and-cleaning.md`: pull/load module template, SQL/WRDS habits, dtypes, filter waterfalls, merges, point-in-time
- `references/task-runner-doit.md`: dodo.py patterns, up-to-date rules, `clean`, notebooks, LaTeX, `config_changed`, debugging
- `references/testing-and-validation.md`: unit vs validation vs replication tests, tolerances, CI skips, literate tests
- `references/notebooks-reports-publishing.md`: jupytext, generated LaTeX, ChartBook, GitHub Pages
- `references/scale-and-automation.md`: Polars/Parquet, HPC/SLURM, CI/CD, cron, Airflow, MLOps, Git/PR workflow
- `references/code-style.md`: the full style rules
- `templates/project/`: a minimal runnable skeleton (settings, dodo, pull/clean/calc/create, tests, notebook, report, CI)
- `scripts/audit_pipeline.py`: a static audit of a repo against these conventions (stdlib only)
