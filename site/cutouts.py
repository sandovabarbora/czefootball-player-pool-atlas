"""Player cut-outs from the licensed portraits (background removed locally).

The cards and the hero want the player on a flat panel, the way graphics
departments cut players out of photos. The public "render" sites do that
from Getty and club photography with no licence; this does it from the
Wikimedia Commons portraits the site already credits, on this machine, with
`rembg` (an open-source segmentation model, no upload). For each portrait
in docs/img/players/<id>.jpg a docs/img/players/<id>-cut.png is written
with a transparent background; `site/enrich_index.py` uses the cut-out
where it exists and the plain portrait where it does not.

usage: python site/cutouts.py [--all]      (default: every league portrait + the card and hero players)
The full set (~1000 portraits) takes ~20 minutes; the cards take seconds.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from PIL import Image
from rembg import new_session, remove

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PLAYERS = DOCS / "img" / "players"


def wanted_ids(nation: str) -> set[str]:
    """Portrait ids used by cards and the hero in the built page of `nation`."""
    page = DOCS / ("index.html" if nation == "cze" else f"{nation}/index.html")
    if not page.exists():
        return set()
    html = page.read_text(encoding="utf-8")
    return set(re.findall(r'img/players/([0-9a-f]{8})(?:-cut\.png|\.jpg)"[^>]*class="(?:cycle-card-mug|hero-cutout)"', html)) | \
        set(re.findall(r'class="(?:cycle-card-mug|hero-cutout)"[^>]*src="[^"]*img/players/([0-9a-f]{8})', html))


def cut(src: Path, session) -> Path:
    out = src.with_name(src.stem + "-cut.png")
    if out.exists() and out.stat().st_mtime >= src.stat().st_mtime:
        return out
    img = Image.open(src).convert("RGBA")
    result = remove(img, session=session)
    result.save(out, optimize=True)
    return out


def main() -> None:
    every = "--all" in sys.argv
    ids = None if every else (wanted_ids("cze") | wanted_ids("eng"))
    session = new_session("u2net")
    done = 0
    for src in sorted(PLAYERS.glob("*.jpg")):
        league = src.stem.endswith("-league")
        if ids is not None and not league and src.stem not in ids:
            continue
        cut(src, session)
        done += 1
    print(f"cutouts: {done} portraits")


if __name__ == "__main__":
    main()
