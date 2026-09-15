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
FILES = ["atlas_FW.svg", "atlas_MF.svg", "atlas_DF.svg", "intl_cohort_heatmap.svg", "big5_series.svg",
         "league_strength.svg", "league_strength_ppc.svg", "model_comparison.svg"]

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config
from src.utils import season_label

METRICS = season_label(config.seasons()["metrics"])
NT_YEARS = config.nt_years()
ADJ_EN = config.nation()["adjective"]
ADJ_CS = config.nation().get("cs", {}).get("adj_m", "český")
ADJ_CS_PL = config.nation().get("cs", {}).get("adj_pl", "čeští")

T = {
    # scatter atlases
    "Style map (no league multipliers)": "Style mapa (bez ligových násobiček)",
    "Quality-adjusted map": "Kvalitou upravená mapa",
    f"{ADJ_EN} football · Forwards {METRICS}": f"{ADJ_CS.capitalize()} fotbal · Útočníci {METRICS}",
    f"{ADJ_EN} football · Midfielders {METRICS}": f"{ADJ_CS.capitalize()} fotbal · Záložníci {METRICS}",
    f"{ADJ_EN} football · Defenders {METRICS}": f"{ADJ_CS.capitalize()} fotbal · Obránci {METRICS}",
    "corpus": "korpus",
    f"NT {NT_YEARS}": "Reprezentace",   # the years are in the caption; the legend sits at the panel edge
    # heatmap
    "Forwards  ·  median npG+A per 90 (quality-adjusted)": "Útočníci  ·  medián npG+A na 90 (kvalitou upravené)",
    "Midfielders  ·  median npG+A per 90 (quality-adjusted)": "Záložníci  ·  medián npG+A na 90 (kvalitou upravené)",
    "Defenders  ·  median npG+A per 90 (quality-adjusted)": "Obránci  ·  medián npG+A na 90 (kvalitou upravené)",
    f"International cohort benchmark  ·  UEFA top-9 leagues {METRICS}": f"Mezinárodní kohortový benchmark  ·  top-9 ligy UEFA {METRICS}",
    # big5 series (Task 13a exhibit / Task 13b slide 7)
    "Players (≥ 450 min)": "Hráči (≥ 450 min)",
    "Per million population": "Na milion obyvatel",
    "Season start year": "Počáteční rok sezóny",
    # league strength (Task 15)
    "League strength: two estimates": "Síla ligy: dva odhady",
    "m_L  ·  Premier-League-equivalent rate multiplier": "m_L  ·  násobička míry ekvivalentní Premier League",
    "Model median (90% HDI)": "Medián modelu (90% HDI)",
    "UEFA multiplier": "Násobička UEFA",
    "Posterior predictive check": "Posteriorní prediktivní kontrola",
    "npG + A that season": "npG + A tu sezónu",
    "Share of player-seasons": "Podíl hráčských sezón",
    "Observed": "Pozorováno",
    "Replicated (posterior mean)": "Replikováno (posteriorní průměr)",
    # model comparison (Task 16)
    "Model comparison: RMSE by origin season": "Srovnání modelů: RMSE podle cílové sezóny",
    "RMSE (npG+A per 90, quality-adjusted)": "RMSE (npG+A na 90, upravené o kvalitu)",
    "Target season (origin)": "Cílová sezóna (origin)",
    "Persistence": "Persistence",
    "Shrinkage to league mean": "Shrinkage k ligovému průměru",
    "Hierarchical Bayesian": "Hierarchický bayesovský",
    "Gradient boosting": "Gradient boosting",
    "Small MLP": "Malý MLP",
}
CS_GEN = config.nation().get("cs", {}).get("gen", "Česka")
# the PCA caption carries the corpus counts, so it is matched by pattern
CAPTION_EN = re.compile(
    rf"PCA of the five-feature vector \(npG/90, A/90, minutes share, age, cards/90\), (?P<season>\S+)\. "
    rf"Grey: the whole corpus \(n = (?P<corpus>\d+)\); coloured: {re.escape(ADJ_EN)}-eligible players by cluster \(n = (?P<czech>\d+)\)\. "
    rf"Oxblood rings: national-team call-up (?P<nt>[\d–-]+)\.")
CAPTION_CS = ("PCA pětiprvkového vektoru (npG/90, A/90, podíl minut, věk, karty/90), {season}. "
              "Šedě: celý korpus (n = {corpus}); barevně: hráči s příslušností " + CS_GEN + " podle clusteru (n = {czech}). "
              "Oxbloodové kroužky: reprezentační nominace {nt}.")
# the big5_series suptitle carries the season span, so it is matched by pattern too
BIG5_TITLE_EN = re.compile(rf"{re.escape(ADJ_EN)} players in the Big-5 leagues, (?P<start>\S+) → (?P<end>\S+)")
BIG5_TITLE_CS = f"{ADJ_CS_PL.capitalize()} hráči v ligách Big-5, " + "{start} → {end}"
# labels that stay as they are (axis names, cluster codes, cohorts, countries, numbers, surnames,
# and the big5_series point annotations "YYYY/YY: N", identical in both languages)
KEEP = re.compile(
    r"^(PC[12]|C\d|U\d\d|\d\d[-–]\d\d|\d+\+|[A-Z]{3}|n=\d+|—|[-−]?\d+(\.\d+)?|[A-ZÀ-Ž][a-zà-ž]+|"
    r"\d{4}/\d\d: \d+|\d{4}/\d\d|[A-Z]{3}-[\w .]+)$")
# per-string font scale, for a Czech entry that would otherwise leave its panel
SHRINK: dict[str, float] = {}
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
    m = BIG5_TITLE_EN.fullmatch(word)
    if m:
        seen.add("big5_title")
        return BIG5_TITLE_CS.format(**m.groupdict())
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
        # rotate(-90) appears between translate and scale for vertical axis
        # labels (matplotlib's rotated ylabel); the rotation pivots on the
        # already-translated origin, so a plain `transform="rotate(-90 x y)"`
        # on the replacement <text> reproduces the same placement.
        g = re.search(
            r'<g style="fill: (#[0-9a-f]{6})" transform="translate\(([\d.\-]+) ([\d.\-]+)\)'
            r'(?: rotate\((-?[\d.]+)\))? scale\(([\d.]+) -[\d.]+\)">', inner)
        font = re.search(r'xlink:href="#([A-Za-z]+)-[0-9a-f]+"', inner)
        fill, x, y, rot, sc = g.group(1), g.group(2), g.group(3), g.group(4), float(g.group(5)) * SHRINK.get(word, 1.0)
        family = FONT.get(font.group(1), font.group(1)) if font else FONT["HelveticaNeue"]
        esc = cz.replace("&", "&amp;").replace("<", "&lt;")
        rotate_attr = f' transform="rotate({rot} {x} {y})"' if rot else ""
        return (f'<g id="{gid}">\n    <!-- {esc} -->\n    <text x="{x}" y="{y}" font-family="{family}" '
                f'font-size="{sc * 100:.2f}" fill="{fill}" text-anchor="start"{rotate_attr}>{esc}</text>\n   </g>')

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
if "big5_title" not in seen:
    problems.append("big5_series title pattern matched nothing")
if problems:
    print("FAILED:", *problems, sep="\n  ")
    sys.exit(1)
