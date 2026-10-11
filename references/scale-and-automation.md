# Scale, Environments, Automation and Collaboration

## Environments and dependencies
- **One environment per project.** Packages installed for one project should not
  be able to break another.
- **Pin exact versions** (`pandas==2.2.3`) in research repos. Floors (`>=`) accept
  any future release, and upgrades change results silently. Real example: a
  `yfinance` release changed the default `auto_adjust` from `False` to `True`,
  so the same code began returning adjusted prices and every downstream return
  changed. Small numerical differences matter too: mean-variance weights are
  very sensitive to their inputs.
- State the Python version in the README (and in `requirements.txt` comments,
  or `requires-python`).
- Let the resolver handle transitive conflicts (for example `wrds` requiring an
  older pandas). Do not hand-edit around them.
- Options:
  - **conda + pip** (course default): `conda create -n proj python=3.12`, then
    `pip install -r requirements.txt`. Regenerate the pins with `pip freeze`, or
    curate them by hand.
  - **uv**: `pyproject.toml` + auto-generated `uv.lock`, run with `uv run doit`.
    PyPI only.
  - **pixi**: `pixi.toml` + `pixi.lock` from conda-forge (non-Python binaries
    such as compilers and system libraries). Define a `[tasks]` entry that calls
    `doit`.
  - `requirements.txt`/`environment.yml` remain the portable interchange
    formats, and CI usually installs from them.

## Medium-sized data (1-100 GB)
| Size | Tool |
|---|---|
| < 1 GB | pandas (or Excel for a quick look) |
| 1-100 GB | **Polars** (lazy), DuckDB, or careful pandas |
| 100 GB + | Spark, Dask, distributed |

pandas is single-core and eager, often needs 2-5× the data size in RAM, and
copies often. Polars is multi-core and lazy, and typically several times faster
with a fraction of the memory.

Lazy-first Polars:
```python
import polars as pl

q = (
    pl.scan_parquet(DATA_DIR / "trace", hive_partitioning=True)   # nothing read yet
      .filter((pl.col("year") == 2024) & (pl.col("price") > 0))  # predicate pushdown
      .select(["cusip_id", "trd_exctn_dt", "price", "volume"])   # projection pushdown
      .group_by(["cusip_id", "trd_exctn_dt"])
      .agg(pl.col("price").mean(), pl.col("volume").sum())
)
print(q.explain())               # confirm filters and projections are pushed down
df = q.collect()                 # or stream: see below
```
- Use `scan_*` instead of `read_*`. Filter and select **before** `.collect()`.
- **Parquet**, partitioned by date when queries filter by date:
  `_data/{dataset}/year=YYYY/month=MM/data.parquet`. Row-group min/max
  statistics and partition directories let the reader skip data it does not
  need. New partitions can be added without rewriting old ones, and partitions
  can be processed in parallel.
- When scanning globs or explicit file lists, pass `hive_partitioning=True`.
  Pass `allow_missing_columns=True` (newer releases: `missing_columns="insert"`) when schemas
  drift across files.
- **Enforce the schema when writing** (for example dates as `pl.Date`, prices and
  volumes as `pl.Float64`). Vendor extracts arrive with inconsistent types.
- For aggregations larger than memory, use the streaming engine
  (`collect(engine="streaming")` in recent Polars, `collect(streaming=True)` in early 1.x) or
  `sink_parquet`. For independent per-period work, iterate month by month to keep
  memory bounded.
- Count rows without loading them: `pl.scan_parquet(...).select(pl.len()).collect()`.
- Convert to pandas only at the edge (scikit-learn, statsmodels, legacy code).
- Spark uses the same ideas (lazy transformations, a DAG, actions trigger
  execution, a pushdown optimizer) at cluster scale.

## Remote machines and HPC (SSH + SLURM)
- Use `~/.ssh/config` host aliases (`Host midway3 / HostName ... / User ...`).
- **Login nodes are for editing, submitting and transferring only.** Run compute
  through the scheduler: `sinteractive` for exploration, `sbatch` for batch
  jobs.
- Storage: code and data in project or scratch space. Scratch is **not
  backed up**. Virtual environments go in home, because they create many small
  files that exhaust file-count quotas elsewhere.
- Use `module load` for system software (Python, TeX, R).
- **Split pulls from processing.** Most compute partitions have no internet.
  Pull (internet) → local Parquet → process anywhere (offline). This also pins
  the run to a fixed snapshot and supports incremental pulls.
- Transfers: `rsync -avzhe ssh src/ host:dest/` for repeated syncs, `scp` for
  one-offs, Globus for tens of GB or more.
- Batch header skeleton:
  ```bash
  #!/bin/bash
  #SBATCH --job-name=clean-trace
  #SBATCH --output=%j_clean-trace.out
  #SBATCH --error=%j_clean-trace.err
  #SBATCH --cpus-per-task=4
  #SBATCH --mem-per-cpu=8000
  #SBATCH --time=06:00:00
  #SBATCH --partition=<partition>
  #SBATCH --account=<account>
  cd $HOME/<repo> && source <env>/bin/activate && doit
  ```
- Run Jupyter on a compute node and reach it through SSH port forwarding
  (`ssh -N -f -L <local>:<node>:<remote> host`).

## CI/CD (GitHub Actions)
- **CI** runs on every push and PR: check out, set up the pinned Python, install
  requirements (with pip caching), run `pytest`. See
  `templates/project/.github/workflows/tests.yml`.
- **CD**, the scheduled rebuild (for example a daily monitor): `on: schedule` +
  `workflow_dispatch`. The job pulls fresh data, runs `doit`, and publishes to
  Pages. Credentials come from repository **secrets**, never from YAML.
- Keep separate workflows for testing, merging main into the deployment branch,
  and scheduled updates. Give Actions write permission only where a workflow
  commits.
- The difference from a scheduler is the trigger. CI/CD runs on **code events**.
  Schedulers and orchestrators run on **clocks or data arrival**.

## cron (single machine, recurring)
```
# m h dom mon dow  command
0 6 * * 1-5  /abs/path/run_pipeline.sh     # weekdays 06:00
```
- Use absolute paths everywhere. Test expressions on crontab.guru. The machine
  must be on, which is why the course prefers GitHub Actions for most recurring
  jobs.
- General practice (not from the course): cron runs with a minimal environment.
  Activate the env inside the script, redirect output to a log
  (`>> logs/run.log 2>&1`), and prevent overlapping runs (`flock -n`).

## Orchestration across projects (Airflow)
`doit` orders steps inside one project. An orchestrator orders many projects.
It adds a cross-project graph, run history, retries with backoff, alerting and
backfill, at the cost of running a scheduler, a metadata database and a
webserver. Know when *not* to use one.
- **Idempotent tasks are mandatory.** A task that appends instead of overwriting
  corrupts its output on retry.
- **Logical date / data interval:** a run for interval *t* uses only information
  known at *t*. That is look-ahead discipline enforced by the scheduler. Watch
  `catchup`, because the scheduler may decide it owes you many runs.
- **Assets (dataset-triggered scheduling):** a consumer such as a report runs when
  all its producers have updated (AND semantics), not at a guessed clock time.
- **Generate DAGs from manifests** (`chartbook.toml`). Each producer DAG runs the
  project's `doit` and then its tests. Nobody hand-writes the wiring.
- When something fails, tell apart (a) a code bug, (b) an expired credential and
  (c) a non-idempotent task. Also tell apart a task that *failed* from one that
  never ran because an upstream failed. After an outage, backfill and confirm
  the result matches a timely run.

## Basic MLOps (models in production)
- **Experiment tracking** (MLflow): for every run, log the parameters, data
  version, code version (git SHA), metrics and artifacts. **Log from inside a
  doit task**, so tracking is part of the pipeline and not a manual step.
- Compare runs only while the **data is held fixed**. Benchmarks vary one thing
  (the method) under one evaluation protocol. In financial series, simple
  baselines (the historical mean) are hard to beat, so always report error
  relative to them.
- **Drift checks**: run the data-validation suite on every scheduled arrival. A
  failing check **stops** the DAG instead of publishing a corrupted forecast.
  Tell apart *input drift* (schema change, unit change, vendor backfill) from
  *model decay* (regime change), and record which one happened.
- Close the loop: extract → clean → validate → transform → model → track →
  publish → monitor → rerun, with no human in the loop, and with a human alerted
  when checks fail.

## Collaboration: Git, issues, PRs
- Use issues for tasks, bugs and design discussion. Use one branch per
  feature or fix, so `main` stays stable.
- A PR has a description of the context and rationale, `fixes #123` to link and
  auto-close the issue, CI attached, and a **reviewer other than the author**.
  Every member both authors and reviews.
- Put refactors in their own PRs, so reviewers can check for regressions in
  isolation.
- Reviewers comment on specific lines, check against these conventions, and
  request changes when needed. Treat review as knowledge sharing.
- History hygiene: no secrets, no `.env`, no licensed raw data, ever. If one
  slips in, rewrite the history and rotate the secret.

## Packaging reusable research code
When code is reused across projects or teams (for example a shared WRDS
connector, portfolio-sort utilities or an option-implied-density library),
make it a package:
- Put metadata and dependencies in `pyproject.toml` (not `setup.py`), with
  optional extras (`[project.optional-dependencies] test = [...]`).
- Use `pip install -e .` (or `hatch shell`) during development. `hatch build`
  produces the sdist and wheel, and `hatch test` runs the tests.
- Use semantic versioning. PyPI never lets you reuse a version number. Try
  TestPyPI first, then publish from a tagged GitHub Actions release (trusted
  publishing).
- Test against a matrix of Python versions in CI. Dependencies break on new
  Python versions (for example `distutils` was removed in 3.12).
- Document with Sphinx from docstrings.
