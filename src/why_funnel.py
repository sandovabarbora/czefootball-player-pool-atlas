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
from src.figstyle import RULE, CREAM, INK, OXBLOOD, PEER_A, PEER_B, use_style

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
    """One rung per stage, drawn as a dot on a zoomed axis rather than a bar
    from zero: the stages differ by tenths (average age 26.0 vs 25.4) and a
    zero-based bar hides exactly that. The home nation is the filled oxblood
    dot with its value written beside it; the two compare peers are open dots
    with theirs; the axis spans only the three values plus a margin, and the
    direction that means "more open pathway" is written under the first rung.
    A missing value is skipped rather than drawn at zero.
    """
    countries = [c["code"] for c in why_funnel["countries"]]
    colors = [OXBLOOD, PEER_A, PEER_B][: len(countries)]
    n = len(STAGE_SPECS)
    fig, axes = plt.subplots(n, 1, figsize=(10.4, 1.15 * n + 0.7))
    fig.patch.set_facecolor(CREAM)

    for row, (ax, (title, extractor, is_pct, unit)) in enumerate(zip(axes, STAGE_SPECS, strict=True)):
        raw = extractor(why_funnel)
        pairs = [(c, col, (v * 100 if is_pct else v))
                 for c, col, v in zip(countries, colors, raw, strict=True) if v is not None]
        vals = [v for _, _, v in pairs]
        lo, hi = (min(vals), max(vals)) if vals else (0.0, 1.0)
        span = (hi - lo) or max(abs(hi), 1.0) * 0.1
        ax.set_xlim(lo - span * 0.45, hi + span * 0.6)
        ax.axhline(0, color=RULE, lw=1.0, zorder=1)
        for i, (code, col, v) in enumerate(pairs):
            home = code == home_code
            ax.scatter([v], [0], s=150 if home else 110, zorder=3, color=col if home else CREAM,
                       edgecolors=col, linewidths=1.8)
            fmt = f"{v:,.1f}"   # always a decimal: the stages differ by tenths
            ax.annotate(f"{code} {fmt}{unit}", xy=(v, 0), xytext=(0, 14 if i % 2 == 0 else -22),
                        textcoords="offset points", ha="center", fontsize=10.5, color=col,
                        fontweight=600 if home else 500)
        ax.set_title(title, fontsize=11.5, color=INK, loc="left", pad=10)
        ax.set_ylim(-1, 1)
        for side in ("top", "right", "bottom", "left"):
            ax.spines[side].set_visible(False)
        ax.set_xticks([]); ax.set_yticks([]); ax.tick_params(length=0)
        ax.set_facecolor(CREAM)

    plt.subplots_adjust(hspace=1.05, left=0.04, right=0.97, top=0.95, bottom=0.03)
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
