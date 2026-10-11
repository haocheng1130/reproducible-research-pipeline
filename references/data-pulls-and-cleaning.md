# Data Pulls and Cleaning

## The pull/load module

One file per external source: `pull_<source>.py`. Sources that are almost always
merged may share a file (for example `pull_CRSP_Compustat.py`), so that the merge
is written once and reused.

```python
"""Pull the Federal Reserve's GSW zero-coupon Treasury yield curve.

Source: Gurkaynak, Sack and Wright (2007), published daily by the Fed at
https://www.federalreserve.gov/data/yield-curve-tables/feds200628.csv
Units: continuously compounded zero-coupon yields, in percent.
Identifiers/quirks: one row per business day; columns SVENY01..SVENY30 are
maturities in years; early years have missing long maturities.
"""
from io import BytesIO

import pandas as pd
import requests

from settings import config

DATA_DIR = config("DATA_DIR")


def pull_fed_yield_curve():
    """Download the full GSW yield-curve history and return SVENY01..SVENY30."""
    url = "https://www.federalreserve.gov/data/yield-curve-tables/feds200628.csv"
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    df = pd.read_csv(BytesIO(response.content), skiprows=9, index_col=0, parse_dates=True)
    cols = ["SVENY" + str(i).zfill(2) for i in range(1, 31)]
    return df[cols].astype("float64")


def load_fed_yield_curve(data_dir=DATA_DIR):
    """Load the cached yield curve from DATA_DIR. Run this module first to create it."""
    return pd.read_parquet(data_dir / "fed_yield_curve.parquet")


if __name__ == "__main__":
    df = pull_fed_yield_curve()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(DATA_DIR / "fed_yield_curve.parquet")
```

The rules this example encodes:
- **`pull_` only pulls.** It returns a DataFrame and does not save, print or plot.
- **`load_` only loads.** It never pulls when the file is missing. A
  `FileNotFoundError` is the correct behavior, because a hidden network call
  inside a "load" makes runs unpredictable.
- **Save in `__main__`.** `doit` runs `python src/pull_x.py`, and other modules
  `import pull_x` and call `pull_x.load_x()`.
- **The pull owns dtypes.** Dates, floats, categoricals and identifier strings
  (keep leading zeros on CUSIPs and GVKEYs) are fixed here. Downstream code
  assumes correct dtypes and does not cast defensively.
- **Documentation goes in the docstring.** Record the vendor table names, links
  to the data manuals, variable descriptions (a `description_<table> = {col:
  meaning}` dict is a good habit), units, frequency, and known quirks.
- Import heavy optional clients (`import wrds`) *inside* the function. That
  way the cached-data path works without them installed or configured.

## SQL habits (WRDS/Postgres and similar)
- Select only the columns you need, and filter in `WHERE` (dates, share codes,
  exchange codes, formats). Do not pull whole tables and filter in pandas.
- Comment each `WHERE` clause with its meaning, for example
  `indfmt='INDL' -- industrial format`, `datafmt='STD' -- standardized`.
- Parameterize dates from `settings` (`START_DATE`, `END_DATE`), not literals.
- Know the identifiers. CRSP uses `PERMNO` (tickers change and get reused),
  Compustat uses `GVKEY`, and bonds use `CUSIP`. Links between them come from
  link tables with validity date ranges, so join **as of** a date.
- CRSP has moved to the CIZ/v2 format (for example `crspm.msf_v2`,
  `mthret` with delisting returns included). Note in the docstring which format
  the code uses.
- Close connections. Keep the query text in the repo even when a cached extract
  is used.
- Never interpolate untrusted user input into SQL. For internal parameter lists,
  build them from typed values (`str(int(p))`).

## Cleaning: every filter is a convention
Thresholds such as "drop trades under $10,000", "price cap $1,000" or "drop
trades larger than 50% of the offering amount" are judgment calls, not facts.
Treat them so:

1. **One function per filter**, named for what it does:
   `drop_trades_below_min_dollar_volume(df, min_dollar_volume=10_000)`.
2. **The docstring states the purpose, the threshold and its source** (a paper,
   vendor guidance or your own rationale).
3. **Apply filters in a declared, ordered chain.** Order matters because each
   filter receives the previous one's output.
4. **Record a waterfall.** For each step record rows before and after, rows
   removed, % removed, and unique entities. Save it to `_output/` and show it in
   the report or notebook. A validation test checks that each filter removes
   roughly the expected share.
5. **Prefer flags to deletion during exploration.** Add `flag_<rule>` columns and
   filter at the end. That makes "what breaks without this filter?" easy to
   answer.
6. **Use only ex-ante information.** A filter may use only information available
   when the decision is made (portfolio formation date, forecast origin).

A waterfall pattern:
```python
def apply_filter_chain(df, filters):
    """Apply (name, func) filters in order; return cleaned df and a waterfall table."""
    rows = [("raw", len(df))]
    for name, func in filters:
        df = func(df)
        rows.append((name, len(df)))
    waterfall = pd.DataFrame(rows, columns=["step", "n_rows"])
    waterfall["n_removed"] = -waterfall["n_rows"].diff().fillna(0).astype(int)
    waterfall["pct_removed"] = waterfall["n_removed"] / waterfall["n_rows"].shift(1)
    return df, waterfall
```

## Merges
- Before a merge, assert key uniqueness on the side that should be unique:
  `assert not right.duplicated(keys).any()`.
- Use `validate="one_to_one"`/`"many_to_one"` in `pd.merge`, and check
  `len(out)` against expectations.
- Calendar alignment: different tables date the same period differently (last
  trading day vs first calendar day). Align on a period (`to_period("M")`), not
  on raw dates.
- Record the match rate (share of rows matched) in the waterfall.

## Point-in-time discipline
- Accounting data becomes usable only after it is reported. Lag fundamentals,
  for example by the standard 6-month rule in Fama-French-style sorts.
- Use breakpoints and universes as of the formation date. Use index membership
  with start and end dates, not today's constituents (survivorship bias).
- A forecast for date *t* uses only information known at *t*. This also holds
  inside scheduled pipelines (Airflow "data interval") and backfills.
- Vendors revise and backfill history. Store pull dates, or keep dated
  snapshots, when results must be reproducible to the number.

## Dataset documentation (per output dataframe)
Every tidy dataset you hand to analysis gets a short doc (in `chartbook.toml` or
`docs_src/dataframes/<name>.md`) that covers:
- grain (one row per what?) and primary key
- columns with units
- sources and providers, access type, license and restrictions, how it is pulled
- date column, frequency, and coverage start and end
- known gaps and quirks, and the filters applied (with a link to the waterfall)
