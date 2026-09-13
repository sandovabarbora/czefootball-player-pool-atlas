"""Czech labels for the matplotlib atlas SVGs: docs/*.svg (English) -> docs/cs/*.svg.

matplotlib writes every text as a group of glyph paths preceded by an
`<!-- original text -->` comment. The titles, legend entries and captions
listed in T are replaced with real <text> elements (same position, size and
colour; every title in these figures is left-anchored), and any glyph <defs>
the removed groups owned are re-attached globally so the remaining path-text
(player names, tick labels, cell values) keeps rendering.

Every English string in T must be found in at least one SVG, and every
non-numeric label longer than a surname must have an entry — the script fails
loudly otherwise, so a re-rendered figure cannot ship half-translated.

usage: svg_labels.py docs
"""
import re
import sys
from pathlib import Path

DOCS = Path(sys.argv[1])
FILES = ["atlas_FW.svg", "atlas_MF.svg", "atlas_DF.svg", "intl_cohort_heatmap.svg"]

T = {
    # scatter atlases
    "Style map (no league multipliers)": "Style mapa (bez ligových násobiček)",
    "Quality-adjusted map": "Kvalitou upravená mapa",
    "Czech football · Forwards 2024/25": "Český fotbal · Útočníci 2024/25",
    "Czech football · Midfielders 2024/25": "Český fotbal · Záložníci 2024/25",
    "Czech football · Defenders 2024/25": "Český fotbal · Obránci 2024/25",
    "corpus": "korpus",
    "NT 2024–26": "Reprezentace 2024–26",
    # heatmap
    "Forwards  ·  median npG+A per 90 (quality-adjusted)": "Útočníci  ·  medián npG+A na 90 (kvalitou upravené)",
    "Midfielders  ·  median npG+A per 90 (quality-adjusted)": "Záložníci  ·  medián npG+A na 90 (kvalitou upravené)",
    "Defenders  ·  median npG+A per 90 (quality-adjusted)": "Obránci  ·  medián npG+A na 90 (kvalitou upravené)",
    "International cohort benchmark  ·  UEFA top-9 leagues 2024/25": "Mezinárodní kohortový benchmark  ·  top-9 ligy UEFA 2024/25",
    "Cell: player count and median npG+A per 90. Rows ordered by per-capita rank (top first); highlighted row = CZE.":
        "Buňka: počet hráčů a medián npG+A na 90. Řádky seřazené podle pořadí na milion obyvatel (nejvyšší nahoře); zvýrazněný řádek = CZE.",
}
# the PCA caption carries the corpus counts, so it is matched by pattern
CAPTION_EN = re.compile(
    r"PCA of the five-feature vector \(npG/90, A/90, minutes share, age, cards/90\), (?P<season>\S+)\. "
    r"Grey: the whole corpus \(n = (?P<corpus>\d+)\); coloured: Czech-eligible players by cluster \(n = (?P<czech>\d+)\)\. "
    r"Oxblood rings: national-team call-up (?P<nt>[\d–-]+)\.")
CAPTION_CS = ("PCA pětiprvkového vektoru (npG/90, A/90, podíl minut, věk, karty/90), {season}. "
              "Šedě: celý korpus (n = {corpus}); barevně: hráči s českou příslušností podle clusteru (n = {czech}). "
              "Oxbloodové kroužky: reprezentační nominace {nt}.")
# labels that stay as they are (axis names, cluster codes, cohorts, countries, numbers, surnames)
KEEP = re.compile(r"^(PC[12]|C\d|U\d\d|\d\d[-–]\d\d|\d\d\+|[A-Z]{3}|n=\d+|—|[-−]?\d+(\.\d+)?|[A-ZÀ-Ž][a-zà-ž]+)$")
# a longer Czech legend entry gets a slightly smaller face so it stays inside the left panel
SHRINK = {"NT 2024–26": 0.85}
FONT = {"Georgia": "Georgia, 'Times New Roman', serif",
        "HelveticaNeue": "'Helvetica Neue', Helvetica, Arial, sans-serif",
        "DejaVuSans": "'DejaVu Sans', Arial, sans-serif"}

seen: set[str] = set()
untranslated: list[str] = []


def czech(word: str) -> str | None:
    if word in T:
        seen.add(word)
        return T[word]
    m = CAPTION_EN.fullmatch(word)
    if m:
        seen.add("caption")
        return CAPTION_CS.format(**m.groupdict())
    return None


def convert(src: str, name: str) -> str:
    def repl(m):
        gid, inner = m.group(1), m.group(2)
        c = re.search(r"<!--\s*(.*?)\s*-->", inner, re.S)
        if not c:
            return m.group(0)
        word = c.group(1)
        cz = czech(word)
        if cz is None:
            if not KEEP.fullmatch(word):
                untranslated.append(f"{name}: {word[:60]}")
            return m.group(0)
        g = re.search(r'<g style="fill: (#[0-9a-f]{6})" transform="translate\(([\d.\-]+) ([\d.\-]+)\) scale\(([\d.]+) -[\d.]+\)">', inner)
        font = re.search(r'xlink:href="#([A-Za-z]+)-[0-9a-f]+"', inner)
        fill, x, y, sc = g.group(1), g.group(2), g.group(3), float(g.group(4)) * SHRINK.get(word, 1.0)
        family = FONT.get(font.group(1), font.group(1)) if font else FONT["HelveticaNeue"]
        esc = cz.replace("&", "&amp;").replace("<", "&lt;")
        return (f'<g id="{gid}">\n    <!-- {esc} -->\n    <text x="{x}" y="{y}" font-family="{family}" '
                f'font-size="{sc * 100:.2f}" fill="{fill}" text-anchor="start">{esc}</text>\n   </g>')

    out = re.sub(r'<g id="(text_\d+)">(.*?)</g>\s*</g>', repl, src, flags=re.S)
    ids = set(re.findall(r'<path id="([^"]+)"', out))
    refs = set(re.findall(r'xlink:href="#([^"]+)"', out))
    defs = []
    for mid in sorted(refs - ids):
        m = re.search(rf'<path id="{re.escape(mid)}".*?"/>', src, flags=re.S)
        if m:
            defs.append(m.group(0))
    if defs:
        block = "<defs>\n" + "\n".join(defs) + "\n</defs>\n"
        out = re.sub(r"(<svg[^>]*>\s*)", lambda m: m.group(1) + block, out, count=1)
    return out


(DOCS / "cs").mkdir(exist_ok=True)
for name in FILES:
    src = (DOCS / name).read_text(encoding="utf-8")
    (DOCS / "cs" / name).write_text(convert(src, name), encoding="utf-8")
    print("labelled cs/" + name)

unused = sorted(set(T) - seen)
problems = []
if untranslated:
    problems.append("untranslated labels: " + "; ".join(untranslated))
if unused:
    problems.append("T entries not found in any SVG: " + "; ".join(unused))
if "caption" not in seen:
    problems.append("PCA caption pattern matched nothing")
if problems:
    print("FAILED:", *problems, sep="\n  ")
    sys.exit(1)
