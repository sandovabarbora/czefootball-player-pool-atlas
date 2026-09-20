"""Slide 8's slope chart (Task 25c): the six same-definition pathway numbers
(`table.peer-compare`'s first six rows) as normalised positions, one line per
country, so the shape of the comparison reads at a glance instead of row by
row in a table -- the table itself moves into a fold under the chart.

Normalisation is a display convention, not a ranking: each metric's three
raw values are rescaled to [0, 1] independently, with the axis direction
chosen per metric so 1.0 always marks the most open pathway on that metric
(more players per million, more U21 minutes at home, an earlier export age,
fewer sideways moves, a bigger share of an export's club minutes, more of
the squad in the top-9 leagues). A metric missing a value for any of the
three countries is dropped rather than drawn with a gap.

Output: outputs/<NATION>/pathway_slope.svg
"""
from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt

from src.figstyle import CREAM, CREAM_TINT, MUTED, OXBLOOD, PEER_A, PEER_B, strip_chrome, use_style

LOG = logging.getLogger(__name__)
use_style()

# Row keys in `peer_compare["rows"]`'s canonical order (excludes the seventh
# "big5_now" row -- slide 8's own text calls these "the same six numbers").
METRIC_KEYS = ["per_million", "u21_share", "export_age", "sideways", "minutes_share", "wc_top9"]
METRIC_LABELS = {
    "per_million": "Per million",
    "u21_share": "U21 share",
    "export_age": "Export age",
    "sideways": "Sideways",
    "minutes_share": "Minutes share",
    "wc_top9": "WC top-9",
}
# True: higher raw value -> 1.0 ("more open"). False: lower raw value -> 1.0.
METRIC_HIGHER_IS_OPEN = {
    "per_million": True, "u21_share": True, "export_age": False,
    "sideways": False, "minutes_share": True, "wc_top9": True,
}
LINE_COLORS = [OXBLOOD, PEER_A, PEER_B]  # home country first, by construction of peer_compare_countries()


def render_pathway_slope_figure(rows: list[dict], countries: list[str], out_path: Path) -> None:
    """Task 27B5: `rows`: `peer_compare["rows"][:6]`; `countries`:
    `peer_compare["countries"]` ([home, a, b]). Direct country-code labels
    at both ends of each line (no legend); metric names as x-axis ticks; a
    light `CREAM_TINT` band across the full 0-1 range so "worst" and "best"
    read as a range, not just two edge labels."""
    metrics = []
    for key in METRIC_KEYS:
        row = next((r for r in rows if r["key"] == key), None)
        if row is None:
            continue
        by_c = row["by_country"]
        vals = {c: by_c[c]["value"] for c in countries}
        if any(v is None for v in vals.values()):
            continue
        lo, hi = min(vals.values()), max(vals.values())
        norm = {c: (0.5 if hi == lo else (v - lo) / (hi - lo)) for c, v in vals.items()}
        if not METRIC_HIGHER_IS_OPEN[key]:
            norm = {c: 1 - v for c, v in norm.items()}
        metrics.append((key, norm))

    fig, ax = plt.subplots(figsize=(10.4, 5.0))
    fig.patch.set_facecolor(CREAM)
    xs = list(range(len(metrics)))
    ax.axhspan(0, 1, color=CREAM_TINT, zorder=0, lw=0)

    for i, country in enumerate(countries):
        ys = [norm[country] for _key, norm in metrics]
        color = LINE_COLORS[i] if i < len(LINE_COLORS) else MUTED
        # Code only (not the country name) -- see fare_dots.py's matching
        # comment: no per-country entry needed in svg_labels.py this way.
        ax.plot(xs, ys, color=color, lw=2.4 if country == countries[0] else 1.8,
                 marker="o", ms=6, zorder=3)
        left_dx = -9 if len(xs) > 1 else -12
        ax.annotate(country, xy=(xs[0], ys[0]), xytext=(left_dx, 0), textcoords="offset points",
                    fontsize=10, color=color, va="center", ha="right", fontweight=600)
        ax.annotate(country, xy=(xs[-1], ys[-1]), xytext=(9, 0), textcoords="offset points",
                    fontsize=10, color=color, va="center", ha="left", fontweight=600)

    ax.set_xticks(xs)
    ax.set_xticklabels([METRIC_LABELS[key] for key, _norm in metrics])
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["worst of the three", "best of the three"], color=MUTED)
    ax.set_ylim(-0.1, 1.1)
    ax.set_xlim(-0.55, len(xs) - 0.45)
    ax.set_title("Same six numbers, normalised", loc="left")
    strip_chrome(ax)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_visible(False)
    ax.tick_params(length=0)
    plt.savefig(out_path, format="svg")
    plt.close(fig)
    LOG.info("wrote %s", out_path)
