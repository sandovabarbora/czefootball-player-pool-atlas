"""Figure for `section.why-funnel` (Task 26A; redrawn as a ladder in Task
27B1): five stages down the page, each a short horizontal bar per country
(home nation next to the two compare countries) with the number written at
the bar's end and the stage label above -- no box frame, no axis.

Reuses `src.render._build_why_funnel`'s already-assembled numbers -- no new
computation happens here, only the drawing. Same colour convention as every
other figure in this report (`src.figstyle`'s palette): the home nation's
bar is oxblood, the two compare countries navy and slate.

Output: outputs/<NATION>/why_funnel.svg. Labels are English; the Czech
build swaps them via `site/svg_labels.py` (its own `FILES`/`T` entries).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

from src import config
from src.figstyle import CREAM, INK, OXBLOOD, PEER_A, PEER_B, use_style

LOG = logging.getLogger(__name__)
use_style()

# (stage title, cell-list extractor, values already on a 0-100 scale?, unit suffix)
STAGE_SPECS: tuple[tuple[str, Any, bool, str], ...] = (
    ("Share of minutes to young players", lambda wf: [c["value"] for c in wf["stage1"]["share_u21"]], True, " %"),
    ("League average age", lambda wf: [c["value"] for c in wf["stage2"]["mean_age"]], False, ""),
    ("Age at first move abroad", lambda wf: [r["age"] for r in wf["stage3"]["rows"]], False, ""),
    ("Sideways moves", lambda wf: [c["value"] for c in wf["stage4"]["sideways"]], True, " %"),
    ("Players per million", lambda wf: [c["value"] for c in wf["stage5"]["per_million"]], False, ""),
)


def render_why_funnel_figure(why_funnel: dict, home_code: str, out_path: Path) -> None:
    """`why_funnel`: the context dict `src.render._build_why_funnel` returns
    (`countries` + `stage1`..`stage5`). One horizontal-bar rung per stage,
    one bar per country in `why_funnel["countries"]` (home first, then the
    two compare peers, the order `peer_compare_countries()` already fixes),
    the value written at the bar's end instead of read off an axis. A
    missing value (a country absent from a source table) draws as a
    zero-width bar rather than raising.
    """
    countries = [c["code"] for c in why_funnel["countries"]]
    colors = [OXBLOOD, PEER_A, PEER_B][: len(countries)]
    n = len(STAGE_SPECS)
    fig, axes = plt.subplots(n, 1, figsize=(10.4, 1.5 * n + 0.6))
    fig.patch.set_facecolor(CREAM)

    for ax, (title, extractor, is_pct, unit) in zip(axes, STAGE_SPECS, strict=True):
        raw_values = extractor(why_funnel)
        values = [(v * 100 if is_pct else v) if v is not None else 0 for v in raw_values]
        y = list(range(len(countries)))
        ax.barh(y, values, color=colors, height=0.5, zorder=2)
        vmax = max(values) if values else 1
        pad = vmax * 0.045 if vmax else 0.5
        for yi, (v, c) in enumerate(zip(values, colors, strict=True)):
            fmt = f"{v:.1f}" if (is_pct and v < 10) else f"{v:.0f}"
            ax.annotate(f"{fmt}{unit}", xy=(v, yi), xytext=(pad, 0), textcoords="offset points",
                       fontsize=10, color=c, va="center", ha="left", fontweight=600)
        ax.set_yticks(y)
        ax.set_yticklabels(countries, fontsize=9.5, color=INK, fontweight=600)
        ax.invert_yaxis()
        ax.set_title(title, fontsize=11, color=INK, loc="left", pad=8)
        ax.set_xlim(0, vmax * 1.22 if vmax else 1)
        for side in ("top", "right", "bottom", "left"):
            ax.spines[side].set_visible(False)
        ax.set_xticks([])
        ax.tick_params(length=0)
        ax.set_facecolor(CREAM)

    plt.subplots_adjust(hspace=0.85, left=0.07, right=0.96, top=0.98, bottom=0.02)
    plt.savefig(out_path, format="svg")
    plt.close(fig)
    LOG.info("wrote %s", out_path)


def main() -> None:
    """Standalone entry point: redraws the figure from the built context
    (no new computation) -- `uv run python -m src.why_funnel`."""
    logging.basicConfig(level=logging.INFO)
    config.ensure_dirs()
    from src.render import build_context, load_data

    ctx = build_context(load_data(), lang="en")
    render_why_funnel_figure(ctx["why_funnel"], config.HOME, config.OUTPUTS_DIR / "why_funnel.svg")


if __name__ == "__main__":
    main()
