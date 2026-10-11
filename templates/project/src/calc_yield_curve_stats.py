"""Analysis of the tidy yield-curve panel: the term spread and summary statistics.

Pure functions only (DataFrame in, DataFrame/Series/float out). Nothing here
reads or writes files, so every function can be unit-tested with synthetic data
(see test_calc_yield_curve_stats.py). create_exhibits.py turns the results into
tables, figures and report numbers.
"""


def calc_term_spread(tidy, long_maturity=10, short_maturity=2):
    """Yield(long_maturity) minus yield(short_maturity) for each date, in percentage points.

    Dates where either maturity is missing are dropped.
    """
    wide = tidy.pivot(index="date", columns="maturity", values="yield_pct")
    spread = (wide[long_maturity] - wide[short_maturity]).dropna()
    spread.name = f"spread_{long_maturity}y_{short_maturity}y"
    return spread


def calc_share_inverted(spread):
    """Fraction of dates on which the spread is negative (an inverted curve)."""
    return float((spread < 0).mean())


def calc_summary_stats(tidy, maturities=(1, 2, 5, 10, 30)):
    """Count, mean, std, min and max of yields for selected maturities, one row each."""
    subset = tidy[tidy["maturity"].isin(maturities)]
    stats = subset.groupby("maturity")["yield_pct"].agg(["count", "mean", "std", "min", "max"])
    stats.index.name = "maturity"
    return stats
