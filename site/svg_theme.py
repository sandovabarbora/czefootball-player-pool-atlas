"""Recolour the figures in a built site into the current theme.

`src.figstyle` draws new figures in the theme directly. The six figures
whose modules refit a model in `main()` (league strength, model comparison,
series model, youth panel, gap decomposition, export-age model) are not
redrawn for a purely visual change -- a refit would move their numbers and,
for the series model, the forecast the prediction ledger has on record. So
the build maps the cream-paper palette they were drawn with to the theme
here, colour for colour, from `figstyle.LEGACY_TO_THEME`. A figure already
drawn in the theme contains none of the legacy hexes and passes through
unchanged, which makes this idempotent and safe to run on every build.

usage: site/svg_theme.py DOCS_DIR      (recolours DOCS_DIR/*.svg and DOCS_DIR/cs/*.svg)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.figstyle import LEGACY_TO_THEME  # noqa: E402

_HEX = re.compile("|".join(re.escape(k) for k in LEGACY_TO_THEME), re.IGNORECASE)


def recolour(svg: str) -> tuple[str, int]:
    """The SVG text with every legacy colour replaced; and how many were."""
    n = 0

    def swap(m: re.Match) -> str:
        nonlocal n
        n += 1
        return LEGACY_TO_THEME[m.group(0).lower()]

    return _HEX.sub(swap, svg), n


def main(docs: Path) -> None:
    files = sorted(docs.glob("*.svg")) + sorted((docs / "cs").glob("*.svg"))
    total = 0
    for f in files:
        text = f.read_text(encoding="utf-8")
        out, n = recolour(text)
        if n:
            f.write_text(out, encoding="utf-8")
            total += n
    print(f"svg_theme: {len(files)} figures, {total} colours mapped")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
