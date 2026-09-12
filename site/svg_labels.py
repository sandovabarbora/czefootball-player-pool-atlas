"""English labels for the matplotlib atlas SVGs: docs/cs/*.svg -> docs/*.svg.

matplotlib writes text as glyph paths; the titles/captions listed in T are
replaced with real <text> elements (left-anchored, same position/size/colour),
and any glyph <defs> the removed groups owned are re-attached globally so the
remaining path-text (player names, tick labels) keeps rendering.
"""
import re
import sys
from pathlib import Path

DOCS = Path(sys.argv[1])

T = {
    "Style mapa (bez ligových násobiček)": "Style map (without league multipliers)",
    "Kvalitou upravená mapa": "Quality-adjusted map",
    "Český hokej · Útočníci 2025/26": "Czech Hockey · Forwards 2025/26",
    "Český hokej · Obránci 2025/26": "Czech Hockey · Defensemen 2025/26",
    "PCA projekce z čtyřrozměrného vektoru (G/GP, A/GP, PIM/GP, věk). Oxbloodové kroužky vyznačují MS 24/25 účast. "
    "Šipky znázorňují trajektorii 2024/25 → 2025/26; směr arrow head ukazuje pohyb.":
        "PCA projection of a four-dimensional vector (G/GP, A/GP, PIM/GP, age). Oxblood rings mark WC 24/25 participation. "
        "Arrows show the 2024/25 → 2025/26 trajectory; the arrowhead points in the direction of movement.",
    "Útočníci  ·  medián bodů na zápas": "Forwards  ·  median points per game",
    "Obránci  ·  medián bodů na zápas": "Defensemen  ·  median points per game",
    "Mezinárodní cohort benchmark  ·  NHL 2025/26": "International cohort benchmark  ·  NHL 2025/26",
    "Buňka: počet hráčů a medián bodů na zápas. Vyznačená řada = Česko.":
        "Cell: number of players and median points per game. Highlighted row = Czechia.",
}
FONT = {"Georgia": "Georgia, 'Times New Roman', serif",
        "HelveticaNeue": "'Helvetica Neue', Helvetica, Arial, sans-serif",
        "DejaVuSans": "'DejaVu Sans', Arial, sans-serif"}


def convert(src: str) -> str:
    def repl(m):
        gid, inner = m.group(1), m.group(2)
        cps = re.findall(r'#([A-Za-z]+)-([0-9a-f]+)"', inner)
        if not cps:
            return m.group(0)
        word = "".join(chr(int(c, 16)) for _, c in cps)
        if word not in T:
            return m.group(0)
        g = re.search(r'<g style="fill: (#[0-9a-f]{6})" transform="translate\(([\d.\-]+) ([\d.\-]+)\) scale\(([\d.]+) -[\d.]+\)">', inner)
        fill, x, y, sc = g.group(1), g.group(2), g.group(3), float(g.group(4))
        esc = T[word].replace("&", "&amp;").replace("<", "&lt;")
        return (f'<g id="{gid}">\n    <!-- {esc} -->\n    <text x="{x}" y="{y}" font-family="{FONT.get(cps[0][0], cps[0][0])}" '
                f'font-size="{sc * 100:.2f}" fill="{fill}" text-anchor="start">{esc}</text>\n   </g>')

    out = re.sub(r'<g id="(text_\d+)">(.*?)</g>\s*</g>', repl, src, flags=re.S)
    ids = set(re.findall(r'<path id="([^"]+)"', out))
    refs = set(re.findall(r'xlink:href="#([^"]+)"', out))
    defs = []
    for mid in sorted(refs - ids):
        m = re.search(r'<path id="%s".*?"/>' % re.escape(mid), src, flags=re.S)
        if m:
            defs.append(m.group(0))
    if defs:
        block = "<defs>\n" + "\n".join(defs) + "\n</defs>\n"
        out = re.sub(r"(<svg[^>]*>\s*)", lambda m: m.group(1) + block, out, count=1)
    return out


for name in ["atlas_forwards.svg", "atlas_defense.svg", "intl_cohort_heatmap.svg"]:
    src = (DOCS / "cs" / name).read_text(encoding="utf-8")
    (DOCS / name).write_text(convert(src), encoding="utf-8")
    print("labelled", name)
