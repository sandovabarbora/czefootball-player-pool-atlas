"""Recolour the figures in a built site into the current theme.

`src.figstyle` draws new figures in the theme directly. The six figures
whose modules refit a model in `main()` (league strength, model comparison,
series model, youth panel, gap decomposition, export-age model) are not
redrawn for a purely visual change -- a refit would move their numbers and,
for the series model, the forecast the prediction ledger has on record. So
the build maps the palette they were drawn with (cream paper, then the
dark concrete register) to the theme here, colour for colour, from `figstyle.LEGACY_TO_THEME`. A figure already
drawn in the theme contains none of the legacy hexes and passes through
unchanged, which makes this idempotent and safe to run on every build.

usage: site/svg_theme.py DOCS_DIR      (recolours DOCS_DIR/*.svg and DOCS_DIR/cs/*.svg)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.figstyle import LEGACY_TO_THEME, MUTED, OXBLOOD, SEQ_MINT, SEQ_ORANGE, SEQ_VIOLET  # noqa: E402

_HEX = re.compile("|".join(re.escape(k) for k in LEGACY_TO_THEME), re.IGNORECASE)


def recolour(svg: str) -> tuple[str, int]:
    """The SVG text with every legacy colour replaced; and how many were."""
    n = 0

    def swap(m: re.Match) -> str:
        nonlocal n
        n += 1
        return LEGACY_TO_THEME[m.group(0).lower()]

    return _HEX.sub(swap, svg), n


# Per-figure fixes the colour-for-colour map cannot make. In the gap
# decomposition the U21 channel was chalk on the dark ground and maps to ink,
# so its bar would hide the black whiskers drawn over it, and export age was
# acid, which on white would read as the home nation. Both become the channel
# colours of the interactive chart (charts.js): violet and teal. The concrete
# register also used acid as a plain accent where no nation is marked (a
# replicate, a reference multiplier, a weight curve, two models); on white the
# held green means the home nation only, so those take grey or a category hue.
FIGURE_OVERRIDES: dict[str, list[tuple[str, str]]] = {
    "gap_decomposition.svg": [
        ("fill: #111111; stroke: #ffffff; stroke-width: 0.7", f"fill: {SEQ_VIOLET}; stroke: #ffffff; stroke-width: 0.7"),
        ("fill: #111111; stroke: #111111; stroke-linejoin: miter", f"fill: {SEQ_VIOLET}; stroke: {SEQ_VIOLET}; stroke-linejoin: miter"),
        (OXBLOOD, SEQ_MINT),
    ],
    "league_strength_ppc.svg": [(OXBLOOD, MUTED)],
    "league_strength.svg": [(OXBLOOD, MUTED)],
    "eda_shrinkage.svg": [(OXBLOOD, SEQ_ORANGE)],
    # the persistence baseline was rule-on-ground, faint by design; its label
    # has to stay readable on white
    "model_comparison.svg": [
        (OXBLOOD, SEQ_VIOLET),
        ("stroke-dashoffset: 0; stroke: #d9d9d5", "stroke-dashoffset: 0; stroke: #b5b5b0"),
        ('style="stroke: #d9d9d5"', 'style="stroke: #b5b5b0"'),
        ("fill: #d9d9d5; stroke: #d9d9d5", "fill: #b5b5b0; stroke: #b5b5b0"),
        ('<g style="fill: #d9d9d5" transform', '<g style="fill: #666666" transform'),
    ],
}


def override(name: str, svg: str) -> tuple[str, int]:
    """The SVG text with this figure's overrides applied; and how many were."""
    n = 0
    for old, new in FIGURE_OVERRIDES.get(name, []):
        n += svg.count(old)
        svg = svg.replace(old, new)
    return svg, n


def main(docs: Path) -> None:
    files = sorted(docs.glob("*.svg")) + sorted((docs / "cs").glob("*.svg"))
    total = 0
    for f in files:
        text = f.read_text(encoding="utf-8")
        out, n = recolour(text)
        out, k = override(f.name, out) if f.parent == docs else (out, 0)   # never the cs/ draft
        n += k
        if n:
            f.write_text(out, encoding="utf-8")
            total += n
    print(f"svg_theme: {len(files)} figures, {total} colours mapped")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
