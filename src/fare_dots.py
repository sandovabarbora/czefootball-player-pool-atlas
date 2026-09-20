"""Slide 5's dot plot (Task 25c): one row per country, a dot at its median
club-minutes share abroad, a thin line for the peer range around it.

Reuses the same numbers as the country bar list it replaces (`pathways.
json`'s `fare` rows, reduced to `fare_min` by `src.render._build_pathways`)
-- no new computation, just a different exhibit for the same figures. The
"peer range" drawn for a row is the min-max of every *other* country's value
(so the row's own dot can sit outside its own line when it is the extreme),
not a fixed band -- descriptive of where each country sits among the rest,
not a ranking.

Output: outputs/<NATION>/fare_dots.svg
"""
from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt

from src import config
from src.figstyle import CREAM, INK, MUTED, OXBLOOD, PEER_A, RULE, strip_chrome, use_style

LOG = logging.getLogger(__name__)
use_style()


def render_fare_dots_figure(rows: list[dict], home_code: str, out_path: Path) -> None:
    """Task 27B6: one row per country, a thin range line spanning every
    *other* row's value, a dot at the row's own median (home nation filled
    oxblood, everyone else a plain navy dot), and the value written in text
    at the right end of each row's line -- no axis-only reading required."""
    n = len(rows)
    fig, ax = plt.subplots(figsize=(10.4, 0.5 * max(n, 1) + 1.1))
    fig.patch.set_facecolor(CREAM)
    # Plotted on a 0-100 scale (not 0-1) so the written value is a plain
    # number -- "(%)" lives once in the axis title, the same convention
    # src.youth_panel's scatter uses.
    values = [r["value"] * 100 for r in rows]

    for i, v in enumerate(values):
        y = n - 1 - i  # first row (highest value) drawn at the top
        others = [ov for j, ov in enumerate(values) if j != i]
        if others:
            lo, hi = min(others), max(others)
            ax.plot([lo, hi], [y, y], color=RULE, lw=2.2, solid_capstyle="round", zorder=2)
        is_home = rows[i]["country"] == home_code
        color = OXBLOOD if is_home else PEER_A
        ax.scatter([v], [y], s=50, color=color, zorder=3, edgecolors=CREAM, linewidths=0.7)
        ax.annotate(
            f"{v:.0f}", xy=(v, y), xytext=(9, 0), textcoords="offset points",
            fontsize=9.5, color=color, va="center", ha="left", fontweight=600,
        )

    ax.set_yticks(range(n))
    # Codes only (not the English/Czech country name) so this label needs no
    # per-country entry in site/svg_labels.py's translation table -- the
    # slide's own HTML around the figure already names every country in
    # prose, in the reader's language.
    ax.set_yticklabels([r["country"] for r in reversed(rows)], color=INK, fontweight=600)
    ax.set_ylim(-0.7, n - 0.3)
    ax.set_xlabel("Median share of club minutes played, exports abroad (%)", color=MUTED)
    ax.set_title("How exports fare", loc="left")
    strip_chrome(ax)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    plt.savefig(out_path, format="svg")
    plt.close(fig)
    LOG.info("wrote %s", out_path)


def main() -> None:
    """Standalone entry point: redraws the figure from the already-built
    `pathways.json` (no new computation) -- `uv run python -m src.fare_dots`."""
    import json

    logging.basicConfig(level=logging.INFO)
    config.ensure_dirs()
    from src.render import _build_pathways

    pw_raw = json.loads((config.PROCESSED_DIR / "pathways.json").read_text(encoding="utf-8"))
    peers_meta = config.peers_meta()
    names = {**{c: v["name"] for c, v in config.countries()["peers"].items()},
             **{c: v["name"] for c, v in peers_meta.items()}}
    pw = _build_pathways(pw_raw, names, list(peers_meta))
    render_fare_dots_figure(pw["fare_min"], config.HOME, config.OUTPUTS_DIR / "fare_dots.svg")


if __name__ == "__main__":
    main()
