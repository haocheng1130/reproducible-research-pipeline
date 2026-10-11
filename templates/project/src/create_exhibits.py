"""Write every exhibit the report uses into _output/.

- summary_table.tex      : summary statistics by maturity (LaTeX tabular)
- waterfall_table.tex    : filter waterfall from the cleaning step (validation exhibit)
- term_spread.png        : 10y-2y term spread over time
- stats.tex              : \\newcommand macros for every number quoted in the text

The report \\input's these files, so no number in it is typed by hand.

    python ./src/create_exhibits.py
"""

import pandas as pd
from matplotlib import pyplot as plt

import calc_yield_curve_stats
import clean_yield_curve
from settings import config

OUTPUT_DIR = config("OUTPUT_DIR")


def plot_term_spread(spread):
    """Line chart of the term spread with a zero line. Returns the figure; does not save."""
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(spread.index, spread.values, linewidth=0.8)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_ylabel("10y minus 2y (percentage points)")
    ax.set_xlabel("")
    fig.tight_layout()
    return fig


def format_summary_table(stats):
    """LaTeX tabular for the summary statistics (booktabs rules, 2 decimals)."""
    table = stats.rename(columns=str.capitalize).copy()
    table["Count"] = table["Count"].astype("int64")
    table.index.name = "Maturity (years)"
    return table.to_latex(float_format="%.2f")


def format_waterfall_table(waterfall):
    """LaTeX tabular for the cleaning waterfall, with % removed as a readable column."""
    table = waterfall.copy()
    table["pct_removed"] = (100 * table["pct_removed"]).map(
        lambda x: "" if pd.isna(x) else f"{x:.1f}"
    )
    table["step"] = table["step"].str.replace("_", " ", regex=False)
    table = table.rename(columns={
        "step": "Step", "n_rows": "Rows", "n_unique_date": "Dates",
        "n_removed": "Removed", "pct_removed": "Removed (\\%)",
    })
    return table.to_latex(index=False)


def write_latex_macros(stats, path):
    """Write {name: value} as \\newcommand macros. Names must be letters only."""
    for name in stats:
        if not name.isalpha():
            raise ValueError(f"LaTeX macro names must be letters only: {name!r}")
    lines = [f"\\newcommand{{\\{name}}}{{{value}}}" for name, value in stats.items()]
    path.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    tidy = clean_yield_curve.load_yield_curve_tidy()
    waterfall = clean_yield_curve.load_yield_curve_waterfall()
    spread = calc_yield_curve_stats.calc_term_spread(tidy)
    summary = calc_yield_curve_stats.calc_summary_stats(tidy)

    (OUTPUT_DIR / "summary_table.tex").write_text(format_summary_table(summary))
    (OUTPUT_DIR / "waterfall_table.tex").write_text(format_waterfall_table(waterfall))

    fig = plot_term_spread(spread)
    fig.savefig(OUTPUT_DIR / "term_spread.png", dpi=200)
    plt.close(fig)

    write_latex_macros(
        {
            "SampleStart": tidy["date"].min().strftime("%B %Y"),
            "SampleEnd": tidy["date"].max().strftime("%B %Y"),
            "NumDates": f"{tidy['date'].nunique():,}",
            "MeanSpread": f"{spread.mean():.2f}",
            "ShareInverted": f"{100 * calc_yield_curve_stats.calc_share_inverted(spread):.1f}",
        },
        OUTPUT_DIR / "stats.tex",
    )
