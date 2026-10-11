"""Unit tests for the cleaning filters and the waterfall in clean_yield_curve.py.

Synthetic input is built so that each filter removes a known number of rows.
"""

import numpy as np
import pandas as pd

from clean_yield_curve import (
    clean_yield_curve,
    drop_implausible_yields,
    reshape_to_long,
)


def make_wide():
    """Three dates x two maturities, with one out-of-window date, one NaN and one bad value."""
    index = pd.DatetimeIndex(["1989-12-29", "1990-01-02", "1990-01-03"], name="date")
    return pd.DataFrame(
        {"SVENY02": [8.0, 7.9, 7.8], "SVENY10": [8.1, np.nan, 780.0]},  # 780 = unit error
        index=index,
    )


def test_reshape_to_long_has_one_row_per_date_and_maturity():
    long = reshape_to_long(make_wide())
    assert list(long.columns) == ["date", "maturity", "yield_pct"]
    assert len(long) == 6
    assert not long.duplicated(["date", "maturity"]).any()
    assert set(long["maturity"]) == {2, 10}


def test_drop_implausible_yields_removes_unit_errors_only():
    df = pd.DataFrame({"yield_pct": [-0.1, 5.0, 780.0]})
    assert drop_implausible_yields(df)["yield_pct"].tolist() == [-0.1, 5.0]


def test_waterfall_records_each_filter():
    tidy, waterfall = clean_yield_curve(
        make_wide(), pd.Timestamp("1990-01-01"), pd.Timestamp("1990-12-31")
    )
    # raw 6 rows -> window removes 2 (1989 date) -> NaN removes 1 -> 780% removes 1
    assert waterfall["n_rows"].tolist() == [6, 4, 3, 2]
    assert waterfall["n_removed"].tolist() == [0, 2, 1, 1]
    assert len(tidy) == waterfall["n_rows"].iloc[-1]
