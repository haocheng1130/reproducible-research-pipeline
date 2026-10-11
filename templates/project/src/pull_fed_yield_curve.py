"""Pull the Federal Reserve's GSW zero-coupon Treasury yield curve.

Source: Gurkaynak, Sack and Wright (2007), "The U.S. Treasury Yield Curve: 1961
to the Present", estimated and published by the Federal Reserve Board:
https://www.federalreserve.gov/data/yield-curve-tables/feds200628.csv
(documentation: https://www.federalreserve.gov/data/nominal-yield-curve.htm)

Access: public, no credentials.
Grain: one row per business day. Columns SVENY01..SVENY30 are zero-coupon
yields for maturities of 1..30 years, in percent, continuously compounded.
Quirk: long maturities are not estimated in the early part of the sample, so
those cells are missing. The cleaning step handles this, not this file.

Run directly, or through `doit pull:fed_yield_curve`:

    python ./src/pull_fed_yield_curve.py
"""

from io import BytesIO

import pandas as pd
import requests

from settings import config

DATA_DIR = config("DATA_DIR")


def pull_fed_yield_curve():
    """Download the full GSW history and return SVENY01..SVENY30 as float64.

    Pulls only. Saving happens in the `__main__` block.
    """
    url = "https://www.federalreserve.gov/data/yield-curve-tables/feds200628.csv"
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    df = pd.read_csv(BytesIO(response.content), skiprows=9, index_col=0, parse_dates=True)
    cols = ["SVENY" + str(i).zfill(2) for i in range(1, 31)]
    df = df[cols].astype("float64")
    df.index.name = "date"
    return df


def load_fed_yield_curve(data_dir=DATA_DIR):
    """Load the cached pull from `data_dir`. Never pulls; run this module first."""
    return pd.read_parquet(data_dir / "fed_yield_curve.parquet")


if __name__ == "__main__":
    df = pull_fed_yield_curve()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(DATA_DIR / "fed_yield_curve.parquet")
