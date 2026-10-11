"""Unit tests for calc_yield_curve_stats.py.

Tiny synthetic panels with answers you can check by hand. No data files, no
network, so these run anywhere, including CI.
"""

import pandas as pd
import pytest

from calc_yield_curve_stats import (
    calc_share_inverted,
    calc_summary_stats,
    calc_term_spread,
)


def make_tidy(rows):
    """Build a tidy panel from (date, maturity, yield_pct) tuples."""
    df = pd.DataFrame(rows, columns=["date", "maturity", "yield_pct"])
    df["date"] = pd.to_datetime(df["date"])
    return df


def test_term_spread_is_long_minus_short():
    # Arrange: a normal curve on day 1 and an inverted curve on day 2
    tidy = make_tidy([
        ("2020-01-02", 2, 1.0), ("2020-01-02", 10, 3.0),
        ("2020-01-03", 2, 4.0), ("2020-01-03", 10, 3.5),
    ])
    # Act
    spread = calc_term_spread(tidy)
    # Assert
    assert spread.tolist() == pytest.approx([2.0, -0.5])


def test_term_spread_drops_dates_missing_a_maturity():
    tidy = make_tidy([
        ("2020-01-02", 2, 1.0), ("2020-01-02", 10, 3.0),
        ("2020-01-03", 2, 4.0),  # no 10y on this date
    ])
    spread = calc_term_spread(tidy)
    assert list(spread.index) == [pd.Timestamp("2020-01-02")]


def test_share_inverted_counts_only_negative_spreads():
    spread = pd.Series([1.0, -0.5, 0.0, -0.1])
    # Zero is flat, not inverted: 2 of 4 are negative
    assert calc_share_inverted(spread) == pytest.approx(0.5)


def test_summary_stats_one_row_per_requested_maturity():
    tidy = make_tidy([
        ("2020-01-02", 1, 1.0), ("2020-01-03", 1, 3.0),
        ("2020-01-02", 7, 9.9),  # not requested, must be excluded
    ])
    stats = calc_summary_stats(tidy, maturities=(1,))
    assert list(stats.index) == [1]
    assert stats.loc[1, "count"] == 2
    assert stats.loc[1, "mean"] == pytest.approx(2.0)
    assert stats.loc[1, "max"] == pytest.approx(3.0)
