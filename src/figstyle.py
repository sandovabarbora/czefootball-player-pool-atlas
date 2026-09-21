"""Task 27 part A: the single source of matplotlib figure style, imported by
every module that calls `savefig` (`big5_series, export_age_model, fare_dots,
feature_eda, gap_decomposition, goalkeepers, international_benchmark,
league_strength, model_comparison, pathway_slope, render, series_model,
why_funnel, youth_panel`).

The palette below is a pre-converted sRGB approximation of the page's own
tokens (`templates/style.css`'s `:root` -- `--navy-700`, `--oxblood-700`,
`--cream-50/100/200`, `--rule`, `--ink`) -- matplotlib cannot parse `oklch()`,
so these are hand-picked hex values that sit close to the same colours
rendered in the browser. Every figure module should import its colours from
here, not redefine or re-derive them.

Call `use_style()` once, at import time, in every module before a figure is
built -- it only sets `matplotlib.rcParams`, so calling it more than once
(e.g. because two figure modules are imported in the same process) is
harmless.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

import matplotlib as mpl
import matplotlib.font_manager as fm
from matplotlib.colors import LinearSegmentedColormap

LOG = logging.getLogger(__name__)

# =============================================================================
# Palette
# =============================================================================

# Concrete register (2026-09-21), from bsandova.com: concrete dark ground,
# chalk text, hairlines, one acid accent for the home nation. The names
# NAVY / OXBLOOD / CREAM are kept from the cream-paper original so every
# figure module still reads; they name roles now, and the page's CSS tokens
# (templates/style.css) carry the same values.
NAVY         = "#F2F2EE"   # --navy-700  -- PEER_A, the first comparison country ("hot")
NAVY_DEEP    = "#D6FF3A"   # the bright end of the sequential ramp (acid)
OXBLOOD      = "#D6FF3A"   # --oxblood-700 -- HOME, the home nation, always (acid)
OXBLOOD_TINT = "#3F4A12"   # a dark wash of acid -- level bands, not lines
SLATE        = "#7E7E78"   # PEER_B, the second comparison country
INK          = "#DCDCD6"   # --ink -- text, ticks, axis labels (chalk)
MUTED        = "#7E7E78"   # secondary series, muted labels
CORPUS       = "#3A3A36"   # background corpus / "everyone else"
RULE         = "#3A3A36"   # --rule -- spines, hairlines, dividers
GRID         = "#262624"   # the y-grid only
CREAM        = "#161616"   # --cream-50 -- figure/axes background (the page ground)
CREAM_TINT   = "#1F1F1F"   # --cream-100

# Sequencer colours (the author's site) for marks that need more than two
# categories -- tiers, clusters -- never for the home-vs-peer contrast.
SEQ_ORANGE = "#FF6A3D"
SEQ_MINT   = "#7ED9A6"
SEQ_VIOLET = "#B78CFF"

# Named per the brief's own convention (`HOME`/`PEER_A`/`PEER_B`), aliasing
# the hex constants above so a figure can say `figstyle.HOME` and mean it.
HOME = OXBLOOD
PEER_A = NAVY
PEER_B = SLATE

# Sequential ramp ground -> acid, for heatmaps ("more production/count =
# more visual weight"; on a dark ground weight is light, not dark).
CMAP_NAVY = LinearSegmentedColormap.from_list(
    "ground_to_acid",
    [
        (0.00, CREAM_TINT),
        (0.30, "#3A3A36"),
        (0.55, "#6B7A2E"),
        (0.80, "#A7CC32"),
        (1.00, NAVY_DEEP),
    ],
    N=256,
)

# The cream-paper palette every figure was drawn with before this theme,
# mapped to its replacement. `site/svg_theme.py` applies this to the SVGs
# at build time, so a figure whose model was not refitted (and therefore
# was not redrawn) still ships in the theme; a figure drawn with the
# constants above contains none of these keys and passes through unchanged.
LEGACY_TO_THEME: dict[str, str] = {
    "#1f3a5f": NAVY, "#162a44": NAVY_DEEP, "#9c3a2a": OXBLOOD, "#f1ddd7": OXBLOOD_TINT,
    "#5b7290": SLATE, "#2a261f": INK, "#8a857b": MUTED, "#d4cfc3": CORPUS,
    "#c8c2b7": RULE, "#ece6d8": GRID, "#fdfbf6": CREAM, "#efe9dc": CREAM_TINT,
    "#000000": INK,
    # the cluster palette of the atlases (src/render.py), in sequencer colours
    "#7e8eaa": "#DCDCD6", "#b08968": SEQ_ORANGE, "#7a5c63": SEQ_VIOLET, "#5e7e64": SEQ_MINT,
    "#7e6678": "#E3A0FF", "#3d6b6e": "#7ED9D9", "#806b53": "#FFB07A",
    # the cream-to-navy heatmap ramp stops
    "#c4c3bc": "#3A3A36",
}

# =============================================================================
# Fonts
# =============================================================================

# Preference order. Hanken Grotesk is installed system-wide on the machine
# this report is built on (verified below via `font_manager`, not assumed);
# Avenir Next is the next closest grotesque sans if it is ever missing;
# DejaVu Sans is matplotlib's own bundled fallback so a figure never
# silently renders in Bitstream Vera or another guess.
_SANS_STACK = ["Hanken Grotesk", "Avenir Next", "DejaVu Sans"]


def _resolve_sans() -> list[str]:
    """Only keep stack entries `font_manager` can actually resolve on this
    machine -- `findfont` degrades to DejaVu Sans without raising, so an
    unresolvable name earlier in the list would otherwise go unnoticed."""
    available = {f.name for f in fm.fontManager.ttflist}
    resolved = [name for name in _SANS_STACK if name in available]
    if not resolved:
        LOG.warning("none of %s installed; falling back to DejaVu Sans", _SANS_STACK)
        return ["DejaVu Sans"]
    if resolved[0] != _SANS_STACK[0]:
        LOG.info("preferred font %r unavailable; using %r", _SANS_STACK[0], resolved[0])
    return [*resolved, "DejaVu Sans"]


# =============================================================================
# Sizing -- natural SVG width should already match the content column
# (~1080px) so nothing relies on CSS shrinking a 6pt-labelled figure down.
# =============================================================================

FIG_DPI = 100
FIG_WIDTH_IN = 10.4  # at FIG_DPI: natural SVG width ~1040px


def figsize(aspect: float, width_in: float = FIG_WIDTH_IN) -> tuple[float, float]:
    """`(width_in, width_in * aspect)`; `aspect` is height/width, e.g. 0.55
    for a wide chart or 1.3 for a tall stack of small multiples."""
    return (width_in, round(width_in * aspect, 3))


def use_style() -> None:
    """Set matplotlib rcParams for every figure in the report: sans family,
    base size 11 / title 13 semibold / tick 10, no top or right spines, left
    and bottom spines in `RULE`, y-grid only (0.6px, `GRID`), figure/axes
    background `CREAM`, tight bbox on save, 1.2 line width, marker size 5,
    frameless legends. Idempotent -- safe to call from every module at
    import time."""
    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": _resolve_sans(),
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.titleweight": 600,
        "axes.labelsize": 10,
        "axes.labelcolor": INK,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "xtick.color": INK,
        "ytick.color": INK,
        "legend.fontsize": 10,
        "legend.frameon": False,
        "text.color": INK,
        "axes.edgecolor": RULE,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": True,
        "axes.spines.bottom": True,
        "axes.grid": False,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "figure.facecolor": CREAM,
        "axes.facecolor": CREAM,
        "savefig.facecolor": CREAM,
        "savefig.edgecolor": "none",
        "savefig.bbox": "tight",
        "savefig.dpi": FIG_DPI,
        "figure.dpi": FIG_DPI,
        "lines.linewidth": 1.2,
        "lines.markersize": 5,
        "axes.unicode_minus": True,
    })


# =============================================================================
# Helpers -- shared by every reworked figure so the same visual grammar
# (direct labels, one callout at a time, hairline chrome) doesn't get
# reinvented per module.
# =============================================================================


def strip_chrome(ax) -> None:
    """Top/right spines off; left/bottom in `RULE`; ticks pulled from `INK`;
    axes background `CREAM`. Call once per axes after the data is plotted."""
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(RULE)
        ax.spines[side].set_linewidth(0.9)
    ax.tick_params(colors=INK, length=3.5)
    ax.set_facecolor(CREAM)


def y_grid_only(ax) -> None:
    """A hairline y-grid only (`GRID`, 0.6px), drawn behind the data; no
    x-grid -- the brief's "no decoration" rule for anything that isn't the
    axis a reader needs to compare against."""
    ax.grid(axis="y", color=GRID, lw=0.6, zorder=0)
    ax.set_axisbelow(True)


def label_right(ax, series_end_points: Sequence[tuple[float, float, str, str]], dx: int = 8) -> None:
    """Direct labels at the right edge of each series, instead of a legend.
    `series_end_points`: `(x, y, text, color)` per series -- typically that
    series' last plotted point and its country code."""
    for x, y, text, color in series_end_points:
        ax.annotate(
            text, xy=(x, y), xytext=(dx, 0), textcoords="offset points",
            fontsize=10, color=color, va="center", ha="left", fontweight=600,
            annotation_clip=False,
        )


def annotate_point(ax, x: float, y: float, text: str, dx: int = 0, dy: int = 12,
                    color: str = INK, ha: str = "center") -> None:
    """One callout at `(x, y)`: a short leader line (`RULE`) to `text`. The
    convention every reworked Task 27 figure uses for peak/low/last/break
    markers instead of a caption doing the explaining."""
    ax.annotate(
        text, xy=(x, y), xytext=(dx, dy), textcoords="offset points",
        ha=ha, va="bottom" if dy >= 0 else "top", fontsize=9.5, color=color,
        fontweight=600,
        arrowprops={"arrowstyle": "-", "color": RULE, "lw": 1.0, "shrinkA": 0, "shrinkB": 4},
    )


def legend_row(ax, handles=None, labels=None, **kwargs):
    """A frameless legend as a single horizontal row under the title --
    reserved for figures where *marks* (tier/cluster colours), not series,
    need a key; every series chart uses `label_right` instead."""
    kwargs.setdefault("loc", "upper center")
    kwargs.setdefault("bbox_to_anchor", (0.5, -0.14))
    kwargs.setdefault("ncol", len(labels) if labels else 3)
    kwargs.setdefault("frameon", False)
    if handles is not None and labels is not None:
        return ax.legend(handles, labels, **kwargs)
    return ax.legend(**kwargs)


def pct_axis(ax, axis: str = "y") -> None:
    """Format `axis` ('x' or 'y') ticks as whole-number percentages; values
    are given on a 0-1 scale."""
    from matplotlib.ticker import FuncFormatter

    fmt = FuncFormatter(lambda v, _pos: f"{v * 100:.0f} %")
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def season_axis(ax, seasons: Sequence[str], axis: str = "x", step: int = 1) -> None:
    """Tick a season-start-year axis with `season_label`-formatted values
    (e.g. "2014/15"), thinned to every `step`-th season."""
    from src.utils import season_label

    years = [int(s[:4]) for s in seasons]
    ticks = years[::step]
    labels = [season_label(s) for s in seasons[::step]]
    target = ax.xaxis if axis == "x" else ax.yaxis
    target.set_ticks(ticks)
    target.set_ticklabels(labels)
