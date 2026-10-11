"""Turn the raw GSW pull into a tidy panel: one row per (date, maturity).

Every filter is a convention. Each one below is a separate function whose
docstring gives its purpose and threshold. The chain records a waterfall
(rows before and after each step), which is saved to _output/ and shown in the
report, so a reader can see exactly what each choice removed.

Inputs:  _data/fed_yield_curve.parquet   (from pull_fed_yield_curve.py)
Outputs: _data/yield_curve_tidy.parquet
         _output/yield_curve_waterfall.csv

    python ./src/clean_yield_curve.py
"""

from functools import partial

import pandas as pd

import pull_fed_yield_curve
from settings import config

DATA_DIR = config("DATA_DIR")
OUTPUT_DIR = config("OUTPUT_DIR")
START_DATE = config("START_DATE")
END_DATE = config("END_DATE")


def reshape_to_long(wide):
    """Wide SVENYxx columns -> long (date, maturity, yield_pct), maturity in years.

    >>> wide = pd.DataFrame({"SVENY01": [1.0], "SVENY10": [2.0]},
    ...                     index=pd.DatetimeIndex(["2020-01-02"], name="date"))
    >>> reshape_to_long(wide)
            date  maturity  yield_pct
    0 2020-01-02         1        1.0
    1 2020-01-02        10        2.0
    """
    long = wide.reset_index().melt(id_vars="date", var_name="series", value_name="yield_pct")
    long["maturity"] = long["series"].str.replace("SVENY", "", regex=False).astype("int64")
    long = long.sort_values(["date", "maturity"]).reset_index(drop=True)
    return long[["date", "maturity", "yield_pct"]]


def restrict_to_sample_window(df, start_date, end_date):
    """Keep observations inside [start_date, end_date] (START_DATE/END_DATE in settings)."""
    return df[(df["date"] >= start_date) & (df["date"] <= end_date)]


def drop_missing_yields(df):
    """Drop maturities the Fed did not estimate on that date (NaN yields).

    Missingness is structural (long maturities start later), not a data error,
    so the rows are dropped rather than imputed.
    """
    return df.dropna(subset=["yield_pct"])


def drop_implausible_yields(df, lower=-2.0, upper=20.0):
    """Drop yields outside [lower, upper] percent.

    Threshold rationale: US Treasury zero-coupon yields since 1961 sit well
    inside this band, so anything outside it signals a unit or parsing error.
    """
    return df[df["yield_pct"].between(lower, upper)]


def apply_filter_chain(df, filters, entity_col="date"):
    """Apply (name, func) filters in order. Return the cleaned df and a waterfall table."""
    rows = [("raw", len(df), df[entity_col].nunique())]
    for name, func in filters:
        df = func(df)
        rows.append((name, len(df), df[entity_col].nunique()))
    waterfall = pd.DataFrame(rows, columns=["step", "n_rows", f"n_unique_{entity_col}"])
    waterfall["n_removed"] = (-waterfall["n_rows"].diff()).fillna(0).astype("int64")
    waterfall["pct_removed"] = waterfall["n_removed"] / waterfall["n_rows"].shift(1)
    return df.reset_index(drop=True), waterfall


def clean_yield_curve(wide, start_date, end_date):
    """Run the full cleaning chain on the raw wide pull."""
    filters = [
        ("restrict_to_sample_window", partial(restrict_to_sample_window,
                                              start_date=start_date, end_date=end_date)),
        ("drop_missing_yields", drop_missing_yields),
        ("drop_implausible_yields", drop_implausible_yields),
    ]
    return apply_filter_chain(reshape_to_long(wide), filters)


def load_yield_curve_tidy(data_dir=DATA_DIR):
    """Load the tidy panel written by this module."""
    return pd.read_parquet(data_dir / "yield_curve_tidy.parquet")


def load_yield_curve_waterfall(output_dir=OUTPUT_DIR):
    """Load the filter waterfall written by this module."""
    return pd.read_csv(output_dir / "yield_curve_waterfall.csv")


if __name__ == "__main__":
    raw = pull_fed_yield_curve.load_fed_yield_curve()
    tidy, waterfall = clean_yield_curve(raw, START_DATE, END_DATE)
    tidy.to_parquet(DATA_DIR / "yield_curve_tidy.parquet")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    waterfall.to_csv(OUTPUT_DIR / "yield_curve_waterfall.csv", index=False)
