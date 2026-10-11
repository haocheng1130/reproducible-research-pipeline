# Testing and Validation

A pipeline has three kinds of checks. Keep them apart, because they answer
different questions and run in different places.

| Kind | Question | Inputs | Runs in CI? |
|---|---|---|---|
| **Unit test** | Does this function compute what it claims? | Tiny synthetic data with known answers | **Yes, always** |
| **Data-validation test** | Is the data itself trustworthy? | Real pulled or cleaned data, checked against independent knowledge | Only if the data is available. Otherwise skip |
| **Replication test** | Does the result match the target (paper, vendor, authors' series)? | Pipeline output vs reference numbers, within a pre-set tolerance | Only if the data is available. Otherwise skip |

"The difference between noticing bad data yourself and having a customer
notice it for you." Wire all three into the build (`doit` runs pytest before
publishing) and into CI (GitHub Actions on every push and PR).

## Unit tests
Properties of a good test: **specific** (one behavior), **isolated** (no network,
no big setup), **repeatable**, **readable**, and **comprehensive** (typical and edge
cases).

- Use the **Arrange-Act-Assert** structure.
- The name says the behavior: `test_gmv_with_uncorrelated_assets`, not `test_1`.
- Hand-checkable answers: with uncorrelated assets the GMV weights are
  proportional to 1/variance, so `diag(0.01, 0.04) → [0.8, 0.2]`.
- **Property tests** catch what point tests miss. For example, the GMV
  portfolio's variance ≤ that of 500 random fully-invested portfolios, and the
  tangency portfolio's Sharpe ratio ≥ every random portfolio's.
- **Cross-method agreement**: the numerical optimizer matches the closed form
  when shorts are allowed.
- **Monotonicity and constraints**: adding a constraint can only raise the
  minimum variance, and no-short weights are ≥ 0 and sum to 1.
- **Expected failures**: `with pytest.raises(RuntimeError): ...` for infeasible
  inputs.
- Compare floats with `np.isclose`/`np.allclose(atol=...)` or `pytest.approx`.
  Never use `==` on floats from computation.
- Test SQL logic without credentials: run the `WHERE` clause against a small
  in-memory database (sqlite/duckdb) built from a handful of rows. HW1 grades
  Compustat/CCM queries this way.

```python
import numpy as np
from port_opt import find_global_minimum_variance_portfolio

def test_gmv_with_uncorrelated_assets():
    # Arrange
    Sigma = np.diag([0.01, 0.04])
    # Act
    w = find_global_minimum_variance_portfolio(Sigma)
    # Assert: weights ∝ 1/variance
    assert np.allclose(w, [0.8, 0.2], atol=1e-4)
```

**Doctests** document and test at once. Run them with `pytest --doctest-modules`.
```python
def weighted_average(data_col, weight_col, data):
    """Weighted average of `data_col` using `weight_col` as weights.

    >>> df = pd.DataFrame({"rate": [2, 3, 2], "amt": [100, 200, 100]})
    >>> weighted_average("rate", "amt", df)
    2.5
    """
```

## Data-validation tests
Check the data against things you know **independently** of the pipeline.

| Check | Examples |
|---|---|
| **Reconciliation with a second source** | CRSP total market cap vs the S&P 500 index level. TAQ volume vs CRSP daily volume. Your series vs the authors' posted series. Your rebuilt order book vs the vendor's book. GSW 10y vs FRED DGS10 |
| **Identities** | Portfolio weights sum to 1. Put-call parity. Assets = liabilities + equity. Index return = weighted constituent returns |
| **Filter waterfall** | Each filter removes roughly the expected share. A filter that suddenly removes 0% or 90% is a red flag |
| **Coverage through time** | No unexplained gaps or level breaks. Counts per month/day are stable. Plot them |
| **Keys and grain** | `(id, date)` unique. No duplicate tickers per date |
| **Schema and dtypes** | Required columns exist. Dates are dates. Identifiers keep leading zeros |
| **Ranges and units** | Prices > 0. Yields in a plausible band. Returns not in percent when decimals are expected. Detect a factor-of-100 unit change |
| **Benchmarks** | Cleaned panel aggregated to month-end correlates highly with an open-source benchmark (e.g., OSBAP for bonds) within tolerance |

The course rubric also requires that validation results are **visible**: build
at least one table and one figure of the checks, each with a caption stating
what the check found and what it means for trusting the results.

```python
import pytest
from settings import config
DATA_DIR = config("DATA_DIR")
TIDY = DATA_DIR / "yield_curve_tidy.parquet"

pytestmark = pytest.mark.skipif(not TIDY.exists(), reason="data not pulled (run `doit`)")

def test_one_row_per_date_and_maturity():
    df = pd.read_parquet(TIDY)
    assert not df.duplicated(["date", "maturity"]).any()

def test_no_unexplained_gaps():
    dates = pd.read_parquet(TIDY)["date"].drop_duplicates().sort_values()
    assert dates.diff().dt.days.max() <= 7     # holiday weekends are 4 days; a week is unexplained

def test_benchmark_maturities_present_on_every_date():
    df = pd.read_parquet(TIDY)
    counts = df[df["maturity"].isin([2, 10])].groupby("date").size()
    assert counts.eq(2).all()

# Do not re-assert a cleaning filter's own threshold on its output (e.g. the
# yield band the filter enforces): that always passes. Test the waterfall share
# instead, or check an independent fact.
```

## Replication tests
- **Set the tolerance before you look at results**, and write the reason next to
  it (data vintage differences, sample period, rounding in the paper).
- Compare at the level the paper reports (for example the mean monthly SMB
  return, or a correlation ≥ 0.95 with the Ken French series), not raw rows.
- When a result does not replicate, the test fails and you document why. Do not
  loosen the tolerance until it passes.

```python
# Tolerance chosen ex ante: CRSP vintage + breakpoint data differ from FF's library.
CORR_MIN = 0.95
MEAN_ABS_DIFF_MAX = 0.001   # 10 bp per month

@pytest.mark.skipif(not FF_FILE.exists(), reason="requires WRDS pull")
def test_smb_matches_ken_french():
    ours, theirs = load_aligned_smb()
    assert ours.corr(theirs) >= CORR_MIN
    assert (ours - theirs).abs().mean() <= MEAN_ABS_DIFF_MAX
```

## CI rules
- CI runs `pytest` on every push and PR (see `templates/project/.github/workflows/tests.yml`).
- Tests that need credentials or pulled data **skip** in CI with `skipif`
  (data file missing, or `WRDS_USERNAME` empty). Everything else must run and
  pass, on small samples if needed.
- A red CI blocks merging. Do not merge "temporarily red" work.

## What makes a test well motivated (and what doesn't)
- ✔ Each test has a purpose you can state in one sentence: the bug or data
  problem it would catch.
- ✘ Tautologies: running the code and asserting it equals its own saved output
  ("golden files") with no independent reasoning.
- ✘ Repetitive tests that check the same behavior with different numbers.
- ✘ Tests with `print` and no `assert`.
- ✘ Editing provided tests to make them pass. The tests are the spec.

## Literate unit tests (optional style)
For onboarding-heavy domains (identifier crosswalks, settlement logic, bond
cleaning), the template's style rules suggest a test file that is **also a
notebook**. It uses jupytext percent cells with long narrative markdown (domain
context, why the scenario matters, expected input→output), `scenario_*()`
helpers that build synthetic data, display cells that show input and output, and
plain `def test_*()` functions that pytest discovers. Plots render only in
notebook mode, and every figure is closed with `plt.close(fig)`.
