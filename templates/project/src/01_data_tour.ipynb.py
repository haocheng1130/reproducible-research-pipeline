# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.18.1
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # 01. A Tour of the Cleaned Yield Curve
#
# This notebook tours the data and results. It computes nothing new: the logic
# lives in `clean_yield_curve.py` and `calc_yield_curve_stats.py`, where it is
# unit-tested. `doit` executes this file and saves an HTML copy in `_output/`.

# %%
import calc_yield_curve_stats
import clean_yield_curve

# %% [markdown]
# ## What the cleaning removed
#
# Each row is one filter, applied in order. The cleaning step only produces
# tidy data, and this table shows exactly what each convention cost.

# %%
waterfall = clean_yield_curve.load_yield_curve_waterfall()
waterfall

# %% [markdown]
# ## The tidy panel
#
# One row per (date, maturity). Yields are zero-coupon, continuously
# compounded, in percent.

# %%
tidy = clean_yield_curve.load_yield_curve_tidy()
tidy.tail(10)

# %%
calc_yield_curve_stats.calc_summary_stats(tidy)

# %% [markdown]
# ## The 10y-2y term spread
#
# A negative spread means an inverted curve.

# %%
spread = calc_yield_curve_stats.calc_term_spread(tidy)
spread.plot(figsize=(8, 4), title="10y minus 2y zero-coupon yield (pp)")

# %%
calc_yield_curve_stats.calc_share_inverted(spread)
