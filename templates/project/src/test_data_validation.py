"""Data-validation tests: check the real, cleaned data against independent knowledge.

These need the pulled data, so they are skipped when it is absent (for example
in CI). `doit` runs them after cleaning and before any exhibit is published.
Thresholds are set in advance, and the reason for each is written next to it.
"""

import pandas as pd
import pytest

from settings import config

DATA_DIR = config("DATA_DIR")
OUTPUT_DIR = config("OUTPUT_DIR")
TIDY_PATH = DATA_DIR / "yield_curve_tidy.parquet"
WATERFALL_PATH = OUTPUT_DIR / "yield_curve_waterfall.csv"

pytestmark = pytest.mark.skipif(
    not TIDY_PATH.exists(), reason="cleaned data not built yet (run `doit`)"
)

# Business days only; the longest routine gap is a holiday weekend (4 days).
# A week with no data would be an unexplained break.
MAX_GAP_DAYS = 7
# Fraction of raw rows the implausible-yield filter may remove. It targets
# unit/parsing errors, which should be rare. More than this means the data changed.
MAX_SHARE_IMPLAUSIBLE = 0.001


@pytest.fixture(scope="module")
def tidy():
    return pd.read_parquet(TIDY_PATH)


def test_grain_is_one_row_per_date_and_maturity(tidy):
    assert not tidy.duplicated(["date", "maturity"]).any()


def test_dtypes_set_by_pull_and_clean(tidy):
    assert pd.api.types.is_datetime64_any_dtype(tidy["date"])
    assert pd.api.types.is_integer_dtype(tidy["maturity"])
    assert pd.api.types.is_float_dtype(tidy["yield_pct"])


def test_no_unexplained_gaps_in_coverage(tidy):
    gaps = tidy["date"].drop_duplicates().sort_values().diff().dt.days
    assert gaps.max() <= MAX_GAP_DAYS


def test_benchmark_maturities_present_on_every_date(tidy):
    # The 2y and 10y yields drive the term spread, so neither may be missing.
    counts = tidy[tidy["maturity"].isin([2, 10])].groupby("date").size()
    assert counts.eq(2).all()
    assert len(counts) == tidy["date"].nunique()


def test_implausible_filter_removes_almost_nothing():
    waterfall = pd.read_csv(WATERFALL_PATH).set_index("step")
    removed = waterfall.loc["drop_implausible_yields", "n_removed"]
    assert removed <= MAX_SHARE_IMPLAUSIBLE * waterfall.loc["raw", "n_rows"]


# Pattern for reconciliation with a second source (needs a second pull):
# def test_gsw_10y_close_to_fred_dgs10(tidy):
#     # GSW zero-coupon vs FRED par/constant-maturity: different concepts,
#     # so require high correlation and a bounded mean gap, decided in advance.
#     merged = ...
#     assert merged["gsw"].corr(merged["fred"]) > 0.99
#     assert (merged["gsw"] - merged["fred"]).abs().mean() < 0.25
