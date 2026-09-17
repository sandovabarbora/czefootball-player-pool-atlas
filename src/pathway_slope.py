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

from src import config
from src.international_benchmark import CREAM, INK, MUTED, NAVY, OXBLOOD, RULE

LOG = logging.getLogger(__name__)

plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["Spectral", "Cambria", "Georgia", "Times New Roman", "DejaVu Serif"]
plt.rcParams["font.sans-serif"] = ["Bricolage Grotesque", "Helvetica Neue", "Arial", "DejaVu Sans"]
plt.rcParams["text.color"] = INK

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
LINE_COLORS = [OXBLOOD, NAVY, MUTED]  # home country first, by construction of peer_compare_countries()


def render_pathway_slope_figure(rows: list[dict], countries: list[str], out_path: Path) -> None:
    """`rows`: `peer_compare["rows"][:6]`; `countries`: `peer_compare["countries"]`
    ([home, a, b])."""
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

    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    fig.patch.set_facecolor(CREAM)
    xs = list(range(len(metrics)))
    for i, country in enumerate(countries):
        ys = [norm[country] for _key, norm in metrics]
        color = LINE_COLORS[i] if i < len(LINE_COLORS) else MUTED
        # Code only (not the country name) -- see fare_dots.py's matching
        # comment: no per-country entry needed in svg_labels.py this way.
        ax.plot(xs, ys, color=color, lw=2.2, marker="o", ms=5.5, zorder=3, label=country)

    ax.set_xticks(xs)
    ax.set_xticklabels([METRIC_LABELS[key] for key, _norm in metrics], fontsize=9.5,
                       fontfamily="sans-serif", color=INK)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["worst of the three", "best of the three"], fontsize=9,
                       fontfamily="sans-serif", color=MUTED)
    ax.set_ylim(-0.08, 1.08)
    ax.set_title("Same six numbers, normalised: worst to best of the three countries, per metric",
                fontsize=12, fontfamily="serif", color=INK, pad=12, loc="left")
    ax.tick_params(colors=MUTED, labelsize=9)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(RULE)
    ax.grid(axis="x", color=RULE, lw=0.6, alpha=0.6)
    ax.set_facecolor(CREAM)
    legend = ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=3, frameon=False, fontsize=9.5)
    for text in legend.get_texts():
        text.set_fontfamily("sans-serif")
    plt.tight_layout()
    plt.savefig(out_path, bbox_inches="tight", format="svg", facecolor=CREAM, edgecolor="none")
    plt.close(fig)
    LOG.info("wrote %s", out_path)
