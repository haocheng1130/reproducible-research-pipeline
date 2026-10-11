# GSW Treasury Yield Curve: A Minimal Reproducible Pipeline

A small, complete example of the pipeline conventions: one public data pull,
a documented cleaning chain with a waterfall, pure analysis functions, unit and
data-validation tests, generated exhibits, a jupytext notebook, a LaTeX report,
a ChartBook manifest and CI. Replace the yield-curve example with your own
project and keep the structure.

## Charter
- **Target (one sentence):** a tidy, validated daily panel of zero-coupon
  Treasury yields, plus the 10y-2y term spread.
- **What existing data lacks:** the Fed's CSV is wide, has structural gaps, and
  comes with no tests.
- **What this builds:** a pipeline that pulls, cleans, validates and reports with one command.
- **Who would clone it and why:** anyone who needs a trustworthy yield-curve input for a model.
- **How success is verified:** unit tests on every function. Data-validation tests
  check that the grain is one row per date and maturity, that the 2y and 10y exist
  on every date, that no week passes without data, and that the implausible-value
  filter removes almost nothing.

## Quick start
Prerequisites: conda (or miniforge), and a LaTeX distribution with `latexmk` and
`xelatex` for the report.
```bash
conda create -n yield_curve python=3.12
conda activate yield_curve
pip install -r requirements.txt
cp .env.example .env        # optional: every variable has a default
doit                        # pull -> clean -> test -> exhibits -> notebook -> report -> site
pytest                      # run tests on their own (or: doit test)
```
Change the sample with `END_DATE=2019-12-31` in `.env`, then run `doit`. Only the
tasks that depend on the window rerun.

## Data sources
| Dataset | Provider | Access | Pulled by | License / restrictions |
|---|---|---|---|---|
| GSW zero-coupon yield curve (`feds200628.csv`) | Federal Reserve Board | Public web | `src/pull_fed_yield_curve.py` | Public |

## Outputs
| Output | Produced by | Location |
|---|---|---|
| Tidy panel (date, maturity, yield_pct) | `clean_yield_curve.py` | `_data/yield_curve_tidy.parquet` |
| Filter waterfall | `clean_yield_curve.py` | `_output/yield_curve_waterfall.csv` |
| Test results | `doit test` | `_output/pytest_results.xml` |
| Summary and waterfall tables, spread chart, report macros | `create_exhibits.py` | `_output/*.tex`, `_output/term_spread.png` |
| Data tour notebook | `src/01_data_tour.ipynb.py` | `_output/01_data_tour.html` |
| Report | `reports/report.tex` | `reports/report.pdf` |
| Documentation site | `chartbook build` | `docs/` |

## Repository map
| Path | Purpose |
|---|---|
| `dodo.py` | The task DAG. Run `doit list` to see the tasks |
| `src/settings.py` | The only configuration module (CLI > `.env` > defaults) |
| `src/pull_*.py` | `pull_*` (fetch) and `load_*` (read cache) for each source |
| `src/clean_*.py` | Documented filters → tidy data + waterfall |
| `src/calc_*.py` | Pure analysis functions |
| `src/create_exhibits.py` | Writes every table, figure and number the report uses |
| `src/*.ipynb.py` | Jupytext notebooks, executed by doit |
| `src/test_*.py` | Unit tests (always run) and data-validation tests (run when data exists) |
| `reports/` | LaTeX report that `\input`s generated files |
| `data_manual/` | Irreplaceable hand-made data (committed) |
| `_data/`, `_output/` | Generated. Safe to delete, never committed |
