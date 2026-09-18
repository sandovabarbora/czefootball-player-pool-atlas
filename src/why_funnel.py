"""Figure for `section.why-funnel` (Task 26A): five stacked small multiples,
home nation next to the two compare countries, one bar per country per
stage.

Reuses `src.render._build_why_funnel`'s already-assembled numbers -- no new
computation happens here, only the drawing. Same colour convention as every
other figure in this report (`src.international_benchmark`'s palette): the
home nation's bar is oxblood, the two compare countries navy.

Output: outputs/<NATION>/why_funnel.svg. Labels are English; the Czech
build swaps them via `site/svg_labels.py` (its own `FILES`/`T` entries).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

from src import config
from src.international_benchmark import CREAM, INK, MUTED, NAVY, OXBLOOD, RULE

LOG = logging.getLogger(__name__)

plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["Spectral", "Cambria", "Georgia", "Times New Roman", "DejaVu Serif"]
plt.rcParams["font.sans-serif"] = ["Bricolage Grotesque", "Helvetica Neue", "Arial", "DejaVu Sans"]
plt.rcParams["text.color"] = INK

# (stage title, cell-list extractor, values already on a 0-100 scale?)
STAGE_SPECS: tuple[tuple[str, Any, bool], ...] = (
    ("Share of minutes to young players", lambda wf: [c["value"] for c in wf["stage1"]["share_u21"]], True),
    ("League average age", lambda wf: [c["value"] for c in wf["stage2"]["mean_age"]], False),
    ("Age at first move abroad", lambda wf: [r["age"] for r in wf["stage3"]["rows"]], False),
    ("Sideways moves", lambda wf: [c["value"] for c in wf["stage4"]["sideways"]], True),
    ("Players per million", lambda wf: [c["value"] for c in wf["stage5"]["per_million"]], False),
)


def render_why_funnel_figure(why_funnel: dict, home_code: str, out_path: Path) -> None:
    """`why_funnel`: the context dict `src.render._build_why_funnel` returns
    (`countries` + `stage1`..`stage5`). One horizontal-bar panel per stage,
    one bar per country in `why_funnel["countries"]` (home first, then the
    two compare peers, the order `peer_compare_countries()` already fixes).
    A missing value (a country absent from a source table) draws as a
    zero-width bar rather than raising.
    """
    countries = [c["code"] for c in why_funnel["countries"]]
    n = len(STAGE_SPECS)
    fig, axes = plt.subplots(n, 1, figsize=(6.6, 1.3 * n + 0.7))
    fig.patch.set_facecolor(CREAM)

    for ax, (title, extractor, is_pct) in zip(axes, STAGE_SPECS, strict=True):
        raw_values = extractor(why_funnel)
        values = [(v * 100 if is_pct else v) if v is not None else 0 for v in raw_values]
        colors = [OXBLOOD if c == home_code else NAVY for c in countries]
        y = list(range(len(countries)))
        ax.barh(y, values, color=colors, height=0.55, zorder=2)
        ax.set_yticks(y)
        ax.set_yticklabels(countries, fontsize=9, fontfamily="sans-serif", color=INK)
        ax.invert_yaxis()
        ax.set_title(title, fontsize=10.5, fontfamily="serif", color=INK, loc="left", pad=6)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(RULE)
        ax.tick_params(colors=MUTED, labelsize=8.5)
        ax.set_facecolor(CREAM)

    fig.suptitle("Why the train left", fontsize=13, fontfamily="serif", color=INK, x=0.01, ha="left")
    plt.tight_layout(rect=(0.0, 0.0, 1.0, 0.96))
    plt.savefig(out_path, bbox_inches="tight", format="svg", facecolor=CREAM, edgecolor="none")
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
