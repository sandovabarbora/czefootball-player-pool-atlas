"""Site layer over one rendered page (English or the home nation's language —
`--lang` picks the strings; only the home nation `cze` has a `cs` page):

- head: Space Grotesk + JetBrains Mono, modern.css, hreflang alternates,
  KaTeX, atlas.js (cache-busted with ?v=)
- top bar with brand, section links, Contents button and the EN/CS switch
- masthead cast strip (the card players' portraits)
- hero: posterised cut-out of the first card player with a portrait; the
  sublead folds under the tiles
- player cards: visual header (portrait or monogram, position glyph, club tag)
- avatar chips in cluster top lists and movers tables; analog target portraits
- folds: limitations, analog lists, card analog sections, appendix tables
- cluster accordion; mobile contents panel; clamps; player-index search

Portraits come from site/players.<NATION>.json (fbref_id -> player_key,
image; NATION env var, default "cze"); the template puts `data-player-key` /
`data-fbref-id` on every element that can carry one, so matching is exact.
Every substitution asserts its match count and the script fails loudly when
the page changed under it.

usage: enrich_index.py docs/index.html --lang en
       enrich_index.py docs/cs/index.html --lang cs
       NATION=eng enrich_index.py docs/eng/index.html --lang en
"""
import argparse
import datetime as _dt
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("page", type=Path)
ap.add_argument("--lang", choices=("en", "cs"), required=True)
args = ap.parse_args()

SRC: Path = args.page
LANG: str = args.lang
NATION = os.environ.get("NATION", "cze").lower()
P = "" if LANG == "en" else "../"          # asset prefix relative to the page
_PLAYERS_PATH = Path(__file__).with_name(f"players.{NATION}.json")
# A nation without a photo run yet (no fetch_photos output) still builds --
# chip()/photo() already fall back to initials-only monograms for any key
# missing from PLAYERS, so an empty dict here just means every player does.
PLAYERS = json.load(open(_PLAYERS_PATH, encoding="utf-8")) if _PLAYERS_PATH.exists() else {}
BY_KEY = {v["player_key"]: dict(v, fbref_id=k) for k, v in PLAYERS.items()}
SITE = "https://football.datasimply.eu/"
# Home-nation words the site layer needs outside the report's own i18n
# (this script runs standalone -- see the module docstring). Reads
# config/nations/<NATION>.yaml directly rather than importing src.config so
# `python site/enrich_index.py ...` keeps working from any cwd with NATION set.
_NATION_YAML = Path(__file__).resolve().parent.parent / "config" / "nations" / f"{NATION}.yaml"
if _NATION_YAML.exists():
    import yaml as _yaml
    _nation_cfg = _yaml.safe_load(_NATION_YAML.read_text(encoding="utf-8"))
else:
    _nation_cfg = {"adjective": "Czech", "cs": {"adj_m": "Český"}}
ADJ_EN = _nation_cfg["adjective"]
ADJ_CS = _nation_cfg.get("cs", {}).get("adj_m", "Český").capitalize()
html = SRC.read_text(encoding="utf-8")
fails: list[tuple] = []

S = {
    "en": {
        "nav_aria": "Navigation", "brand": f"{ADJ_EN} Football <span>Atlas</span>",
        "nav": [("#summary", "Summary"), ("#pathways", "Pathways"), ("#q9", "Cards"), ("#methodology", "Methodology")],
        "lang_aria": "Language", "contents": "Contents",
        "cast": "{n} player profiles", "in_context": "In context",
        "analog_fold": "{n} nearest analogs and what followed",
        "loadings": "Loadings table", "scenarios": "Scenario table",
        "full_card": "Full card",
        # roster-tile plain-language metric labels (task 12; matches
        # metric.prod / metric.prod.short in src/i18n.py — duplicated here
        # since this script runs standalone, without the report's i18n)
        "metric_short": "G+A / 90 adj.",
        "metric_long": "goals + assists per 90, league-adjusted",
        "no_trend": "—",
    },
    "cs": {
        "nav_aria": "Navigace", "brand": f"{ADJ_CS} fotbal <span>Atlas</span>",
        "nav": [("#summary", "Shrnutí"), ("#pathways", "Cesty"), ("#q9", "Karty"), ("#methodology", "Metodologie")],
        "lang_aria": "Jazyk", "contents": "Obsah",
        "cast": "{n} profilů hráčů", "in_context": "Souvislosti",
        "analog_fold": "{n} nejbližších analogů a jejich pokračování",
        "loadings": "Tabulka loadings", "scenarios": "Tabulka scénářů",
        "full_card": "Celá karta",
        "metric_short": "G+A / 90 upr.",
        "metric_long": "góly + asistence na 90 min, upravené o ligu",
        "no_trend": "—",
    },
}[LANG]


def ascii_(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def initials(name: str) -> str:
    parts = name.split()
    return ascii_("".join(p[0] for p in parts[:2])).upper()


def photo(key: str) -> dict | None:
    return BY_KEY.get(key)


IMG_ATTRS = ('loading="lazy" decoding="async" '
             'onerror="this.closest(\'.pchip\')?.classList.add(\'pchip-mono\'); this.remove()"')
# cast strip portraits sit above the fold (in the masthead), so they load eager
CAST_IMG_ATTRS = IMG_ATTRS.replace('loading="lazy"', 'loading="eager"')


def chip(key: str, name: str, size: str = "") -> str:
    p = photo(key)
    cls = "pchip" + (f" pchip-{size}" if size else "")
    if p:
        return (f'<span class="{cls}"><img class="pchip-img" src="{P}{p["image"]}" alt="" {IMG_ATTRS}>'
                f'<span class="pchip-initials" aria-hidden="true">{initials(name)}</span>'
                f'<span class="pchip-name">{name}</span></span>')
    return (f'<span class="{cls} pchip-mono"><span class="pchip-initials" aria-hidden="true">{initials(name)}</span>'
            f'<span class="pchip-name">{name}</span></span>')


def sub(pat, repl, want, flags=0):
    """Substitute and record a failure unless exactly `want` matches (want=None: at least one)."""
    global html
    html, n = re.subn(pat, repl, html, flags=flags)
    if (want is None and n == 0) or (want is not None and n != want):
        fails.append((pat[:70], n, want))
    return n


# ---------------------------------------------------------------- head
sub(r'<link href="https://fonts\.googleapis\.com/css2\?family=Spectral[^"]*" rel="stylesheet">',
    '<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">',
    1)
sub(rf'<link rel="stylesheet" href="{re.escape(P)}style\.css">',
    f'<link rel="stylesheet" href="{P}style.css">\n  <link rel="stylesheet" href="{P}modern.css">\n'
    f'  <link rel="alternate" hreflang="en" href="{SITE}">\n'
    f'  <link rel="alternate" hreflang="cs" href="{SITE}cs/">\n'
    f'  <link rel="alternate" hreflang="x-default" href="{SITE}">\n'
    '  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.11/katex.min.css">\n'
    '  <script defer src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.11/katex.min.js" onload="window.renderTex && window.renderTex()"></script>\n'
    f'  <script defer src="{P}atlas.js"></script>',
    1)

# ---------------------------------------------------------------- cs/ page: the translated SVGs sit next to it in docs/cs/
if LANG == "cs":
    # youth_panel.svg and gap_decomposition.svg (Task 20) each appear twice
    # (slide 3's fold / slide 8c, and again in the chapter IV methodology
    # section), hence 6 + 2 + 2 = 10 expected matches; export_age_model.svg
    # (Task 23) also twice → 12. league_strength.svg, league_strength_ppc.svg,
    # model_comparison.svg and series_model.svg (Tasks 15/16/19, chapter IV)
    # each appear once → 16 (Task 24: these four were already translated by
    # svg_labels.py -- T/FILES already covered them -- but this rewrite
    # never listed them, so the cs page kept linking the English copy one
    # directory up).
    sub(r'<img src="\.\./(atlas_[A-Z]{2}\.svg|intl_cohort_heatmap\.svg|big5_series\.svg|gk_export_age\.svg|'
        r'youth_panel\.svg|gap_decomposition\.svg|export_age_model\.svg|league_strength\.svg|'
        r'league_strength_ppc\.svg|model_comparison\.svg|series_model\.svg|fare_dots\.svg|'
        r'pathway_slope\.svg|why_funnel\.svg)"',
        r'<img src="\1"', 19)

# ---------------------------------------------------------------- top bar
links = "\n".join(f'    <a href="{href}">{label}</a>' for href, label in S["nav"])
# EN/CS: only the home nation `cze` has a `cs` page (site/build.sh skips the
# CS pass for any other NATION) -- the toggle is EN-only there.
if NATION == "cze":
    switch = ('<span aria-current="page" lang="en">EN</span><a href="cs/" hreflang="cs" lang="cs">CS</a>' if LANG == "en"
              else '<a href="../" hreflang="en" lang="en">EN</a><span aria-current="page" lang="cs">CS</span>')
else:
    switch = '<span aria-current="page" lang="en">EN</span>'
# Atlas switch: which home nation this run is ("CZE · ENG"), current nation
# plain, the other(s) linking to their published root (docs/ for cze, docs/
# <nation>/ for any other -- see site/build.sh); root-relative so it works
# from any page depth (index.html or cs/index.html).
ATLAS_ROOTS = {"cze": "/", "eng": "/eng/"}
atlas_switch = " · ".join(
    f'<span aria-current="page">{code.upper()}</span>' if code == NATION
    else f'<a href="{root}">{code.upper()}</a>'
    for code, root in ATLAS_ROOTS.items()
)
TOPBAR = f'''<nav class="topbar" aria-label="{S["nav_aria"]}">
  <a class="topbar-brand" href="#top">{S["brand"]}</a>
  <div class="topbar-links">
{links}
  </div>
  <button type="button" class="toc-btn" aria-controls="toc" aria-expanded="false">{S["contents"]}</button>
  <div class="atlas-switch" aria-label="Atlas">
    {atlas_switch}
  </div>
  <div class="lang-switch" aria-label="{S["lang_aria"]}">
    {switch}
  </div>
</nav>
'''
sub(r'<body>\n', '<body id="top">\n' + TOPBAR, 1)

# ---------------------------------------------------------------- cards on the page (order of appearance)
CARD_RE = re.compile(
    r'<article class="cycle-card" id="card-(?P<fid>[^"]*)" data-player-key="(?P<key>[^"]+)" data-fbref-id="[^"]*" '
    r'data-rule="[^"]*" data-pos="(?P<pos>[A-Z]+)" data-club="(?P<club>[^"]*)">(?P<ws1>\s*)<header class="cycle-card-head">'
    r'(?P<ws2>\s*)<h4 class="cycle-card-name">(?P<name>[^<]+)</h4>')
CARDS = [m.groupdict() for m in CARD_RE.finditer(html)]
# One card per position group per showcase rule (currently 5 rules, 3 groups);
# a rule can miss a group (e.g. no player meets it), so the count is a range,
# not a fixed number.
if not (12 <= len(CARDS) <= 18):
    fails.append(("cycle cards found", len(CARDS), "12-15"))

# ---------------------------------------------------------------- masthead cast strip
def cast_item(c: dict) -> str:
    p = photo(c["key"])
    if p:
        return f'<img src="{P}{p["image"]}" alt="{c["name"]}" {CAST_IMG_ATTRS}>'
    return f'<span class="cast-mono" aria-label="{c["name"]}">{initials(c["name"])}</span>'

cast_html = (f'\n    <a class="cast" href="#cards">\n      <span class="cast-stack">{"".join(cast_item(c) for c in CARDS)}</span>\n'
             f'      <span class="cast-caption" data-short="{S["cast"].format(n=len(CARDS))}">{S["cast"].format(n=len(CARDS))}</span>\n    </a>\n')
sub(r'(<dl class="masthead-meta">.*?</dl>\n)', lambda m: m.group(1) + cast_html, 1, re.S)

# ---------------------------------------------------------------- hero: cut-out + sublead fold; drop the in-page TOC list
_first_photo = next((photo(c["key"]) for c in CARDS if photo(c["key"])), None)
if _first_photo:
    sub(r'<section class="hero" id="summary">',
        f'<section class="hero" id="summary">\n  <img class="hero-cutout" src="{P}{_first_photo["image"]}" alt="" aria-hidden="true" decoding="async" onerror="this.remove()">', 1)
sub(r'<p class="hero-sublead">(.*?)</p>',
    lambda m: f'<details class="fold fold-hero"><summary>{S["in_context"]}</summary>\n        <p class="hero-sublead">{m.group(1)}</p>\n        </details>',
    1, re.S)
sub(r'\s*<details class="toc-mobile" open>.*?</details>', '', 1, re.S)

# ---------------------------------------------------------------- cycle cards: visual header
def card_repl(m):
    d = m.groupdict()
    p = photo(d["key"])
    ws1, ws2 = d["ws1"], d["ws2"]
    if p:
        media = f'{ws2}<img class="cycle-card-mug" src="{P}{p["image"]}" alt="" {IMG_ATTRS}>'
        cls = 'cycle-card-visual'
        style = f' style="--hero: url(\'{P}{p["image"]}\')"'
    else:
        media = f'{ws2}<span class="cycle-card-monogram" aria-hidden="true">{initials(d["name"])}</span>'
        cls = 'cycle-card-visual cycle-card-visual-mono'
        style = ''
    visual = (f'{ws1}<div class="{cls}"{style}>{media}'
              f'{ws2}<span class="cycle-card-pos" aria-hidden="true">{d["pos"]}</span>'
              f'{ws2}<span class="cycle-card-team">{d["club"]}</span>'
              f'{ws1}</div>')
    head = m.group(0).split(ws1 + '<header class="cycle-card-head">')[0]
    return f'{head}{visual}{ws1}<header class="cycle-card-head">{ws2}<h4 class="cycle-card-name">{d["name"]}</h4>'

sub(CARD_RE.pattern, card_repl, len(CARDS))

# ---------------------------------------------------------------- gk cards: visual header (task 24)
# gk-card (slide 8b / roster) is deliberately outside the cycle-card tile
# system (see templates/report.html.j2's gk_card_article comment) but reuses
# the same cycle-card-head/-name/-mug/-monogram/-pos/-team sub-component
# classes, so it gets the same portrait/monogram chip the outfield cards'
# own visual header uses above -- just inserted directly (no tile-toggle
# wrapper, since a GK card is never collapsed behind a tile). The *outer*
# container is its own "gk-card-visual" class rather than "cycle-card-visual"
# (docs/modern.css mirrors the latter's rules onto it) -- test_site_build.py
# counts 'class="cycle-card-visual"' 1:1 against the cycle-tile/"Full card"
# toggle count, and a gk-card visual header has neither of those.
GK_CARD_RE = re.compile(
    r'<article class="gk-card" id="gk-card-[^"]*" data-player-key="(?P<key>[^"]+)" '
    r'data-pos="(?P<pos>[A-Z]+)" data-club="(?P<club>[^"]*)">(?P<ws1>\s*)<header class="cycle-card-head">'
    r'(?P<ws2>\s*)<h4 class="cycle-card-name">(?P<name>[^<]+)</h4>')
GK_CARDS = [m.groupdict() for m in GK_CARD_RE.finditer(html)]
if GK_CARDS and not (1 <= len(GK_CARDS) <= 2):
    fails.append(("gk cards found", len(GK_CARDS), "1-2"))


def gk_card_repl(m):
    d = m.groupdict()
    p = photo(d["key"])
    ws1, ws2 = d["ws1"], d["ws2"]
    if p:
        media = f'{ws2}<img class="cycle-card-mug" src="{P}{p["image"]}" alt="" {IMG_ATTRS}>'
        cls = 'gk-card-visual'
        style = f' style="--hero: url(\'{P}{p["image"]}\')"'
    else:
        media = f'{ws2}<span class="cycle-card-monogram" aria-hidden="true">{initials(d["name"])}</span>'
        cls = 'gk-card-visual gk-card-visual-mono'
        style = ''
    visual = (f'{ws1}<div class="{cls}"{style}>{media}'
              f'{ws2}<span class="cycle-card-pos" aria-hidden="true">{d["pos"]}</span>'
              f'{ws2}<span class="cycle-card-team">{d["club"]}</span>'
              f'{ws1}</div>')
    head = m.group(0).split(ws1 + '<header class="cycle-card-head">')[0]
    return f'{head}{visual}{ws1}<header class="cycle-card-head">{ws2}<h4 class="cycle-card-name">{d["name"]}</h4>'


sub(GK_CARD_RE.pattern, gk_card_repl, len(GK_CARDS))

# ---------------------------------------------------------------- cycle cards: compact tile (task 10)
# One roster tile per card, inserted as the article's first child; the rest of
# the card (visual header, stats, cluster, tactical read, trajectory, analogs)
# is the "card body" and stays hidden (docs/modern.css) until the tile's
# button opens it. The tile reads its stat and trajectory straight out of the
# markup already rendered for the card body, rather than recomputing anything.
TILE_ARTICLE_RE = re.compile(
    r'(<article class="cycle-card" id="card-[^"]*" data-player-key="(?P<key>[^"]+)" data-fbref-id="[^"]*" '
    r'data-rule="[^"]*" data-pos="(?P<pos>[A-Z]+)" data-club="(?P<club>[^"]*)">)(?P<body>.*?)(?=</article>)',
    re.S)
_STAT_Q_RE = re.compile(r'<dd>([^<]+)</dd>')
_TRAJ_RE = re.compile(
    r'<span class="cycle-traj-arrow"[^>]*>([^<]*)</span>\s*'
    r'<span class="cycle-traj-dir">([^<]+)</span>\s*'
    r'<span class="cycle-traj-delta">([^<]+)</span>')
_NAME_RE = re.compile(r'<h4 class="cycle-card-name">([^<]+)</h4>')


def tile_repl(m: re.Match) -> str:
    open_tag, body, d = m.group(1), m.group("body"), m.groupdict()
    name_m = _NAME_RE.search(body)
    name = name_m.group(1) if name_m else ""
    p = photo(d["key"])
    if p:
        mug = f'<img class="tile-mug" src="{P}{p["image"]}" alt="" {IMG_ATTRS}>'
    else:
        mug = f'<span class="tile-mono" aria-hidden="true">{initials(name)}</span>'
    # "0.49 NPG+A/90 Q" -> the number in the figure style + a plain (not
    # mono) short label, long form in the tooltip (task 12)
    q_m = _STAT_Q_RE.search(body)
    stat = (f'<span class="tile-stat"><span class="tile-stat-figure">{q_m.group(1)}</span>'
            f'<span class="tile-stat-label" title="{S["metric_long"]}">{S["metric_short"]}</span></span>'
            if q_m else "")
    # "Δ -0.198 npG+A/90 declining" -> arrow + word + value, house style "—"
    # when the card has no trajectory (task 12 / carry-over from task 10)
    traj_m = _TRAJ_RE.search(body)
    if traj_m:
        arrow, direction, delta = traj_m.groups()
        traj = f'<span class="tile-traj">{arrow} {direction} &middot; {delta} {S["metric_short"]}</span>'
    else:
        traj = f'<span class="tile-traj tile-traj-none">{S["no_trend"]}</span>'
    tile = (f'<div class="cycle-tile">{mug}'
            f'<span class="tile-name">{name}</span>'
            f'<span class="tile-meta">'
            f'<span class="tile-club">{d["club"]}</span>'
            f'<span class="tile-pos">{d["pos"]}</span>'
            f'</span>'
            f'<span class="tile-numbers">{stat}{traj}</span>'
            f'<button type="button" class="tile-more" aria-expanded="false">{S["full_card"]}</button>'
            f'</div>')
    return open_tag + tile + body


sub(TILE_ARTICLE_RE.pattern, tile_repl, len(CARDS), re.S)

# ---------------------------------------------------------------- analog targets: portrait
def analog_repl(m):
    key, ws = m.group(1), m.group(2)
    p = photo(key)
    img = f'{ws}  <img class="avatar avatar-xl" src="{P}{p["image"]}" alt="" {IMG_ATTRS}>' if p else ""
    return f'<div class="analog-block" data-player-key="{key}">{ws}<div class="analog-target">{img}'

sub(r'<div class="analog-block" data-player-key="([^"]+)">(\s*)<div class="analog-target">', analog_repl, len(CARDS))

# ---------------------------------------------------------------- chips: cluster top lists, movers
def top_repl(m):
    names = re.findall(r'<span class="cluster-top-name" data-player-key="([^"]+)">([^<]+)</span>', m.group(1))
    return '<span class="cluster-top">' + "".join(chip(k, n) for k, n in names) + '</span>'

_n_top_lists = len(re.findall(r'<span class="cluster-top">', html))
_n_mover_cells = len(re.findall(r'<td data-player-key="', html))
if _n_top_lists < 12 or _n_mover_cells < 6:
    fails.append(("chip targets (top lists, mover cells)", (_n_top_lists, _n_mover_cells), ">=(12, 6)"))
sub(r'<span class="cluster-top">(.*?)</span></span>', top_repl, _n_top_lists, re.S)
sub(r'<td data-player-key="([^"]+)">([^<]+)</td>', lambda m: f'<td>{chip(m.group(1), m.group(2), "sm")}</td>', _n_mover_cells)

# ---------------------------------------------------------------- squad face grid (Task 25b): portrait or monogram per tile
def squad_repl(m):
    key, name = m.group(1), m.group(2)
    p = photo(key)
    if p:
        return f'<img class="squad-portrait" src="{P}{p["image"]}" alt="" {IMG_ATTRS}><span class="squad-name">{name}</span>'
    return f'<span class="squad-mono" aria-hidden="true">{initials(name)}</span><span class="squad-name">{name}</span>'

_n_squad = len(re.findall(r'<span class="squad-name" data-player-key="', html))
if _n_squad:
    sub(r'<span class="squad-name" data-player-key="([^"]+)">([^<]+)</span>', squad_repl, _n_squad)

# ---------------------------------------------------------------- folds
# limitations: each <p><strong>Title.</strong> text</p> -> details, first one open
def lim_fold(m):
    title, text = m.group(1), m.group(2).strip()
    return f'<details class="fold fold-lim"><summary>{title}</summary><p>{text}</p></details>'
sub(r'<p><strong>([^<]+?)\.?</strong>\s*(.*?)</p>', lim_fold, 11, re.S)
sub(r'(<div class="limitations">\s*)<details class="fold fold-lim">', r'\1<details class="fold fold-lim" open>', 1)

# historical analogs: each list folds; the first target stays open
_first = [True]
def analog_fold(m):
    o = ' open' if _first[0] else ''
    _first[0] = False
    n = len(re.findall(r'<li class="analog-row">', m.group(1)))
    return f'<details class="fold analog-fold"{o}><summary>{S["analog_fold"].format(n=n)}</summary>{m.group(1)}</details>'
sub(r'(<ol class="analog-list">.*?</ol>)', analog_fold, len(CARDS), re.S)

# cycle cards: analogs fold (stats, clusters, tactical read and trajectory stay visible)
sub(r'<div class="cycle-section">\s*<p class="cycle-section-label">([^<]*)</p>\s*(<ol class="cycle-analogs">.*?</ol>)\s*</div>',
    r'<details class="fold cycle-section"><summary class="cycle-section-label">\1</summary>\2</details>', len(CARDS), re.S)

# appendix tables
sub(r'(<table class="loadings-table">.*?</table>)', rf'<details class="fold fold-table"><summary>{S["loadings"]}</summary>\1</details>', 1, re.S)
sub(r'(<table class="sensitivity-table">.*?</table>)', rf'<details class="fold fold-table"><summary>{S["scenarios"]}</summary>\1</details>', 1, re.S)

# ---------------------------------------------------------------- clusters: accordion — header + photo chips visible, body folded
def cluster_acc(m):
    dt, dd = m.group(1), m.group(2).rstrip()
    i = dd.find('<span class="cluster-top">')
    body, top = (dd[:i], dd[i:]) if i >= 0 else (dd, "")
    return ('<details class="cluster"><summary class="cluster-head">' + dt.strip() + top +
            '</summary><div class="cluster-body">' + body.strip() + '</div></details>')
def cluster_list(m):
    inner, n = re.subn(r'<dt>(.*?)</dt>\s*<dd>(.*?)</dd>', cluster_acc, m.group(2), flags=re.S)
    if n < 2:
        fails.append(("cluster-list entries", n, ">=2"))
    return '<div class="cluster-list"' + m.group(1) + '>' + inner + '</div>'
sub(r'<dl class="cluster-list"([^>]*)>(.*?)</dl>', cluster_list, 3, re.S)

# ---------------------------------------------------------------- behaviour
JS = """<script>
  window.renderTex = () => {
    document.querySelectorAll('[data-tex]').forEach(el => {
      try { katex.render(el.dataset.tex, el, { displayMode: true, throwOnError: false }); el.classList.add('formula-tex'); } catch (e) {}
    });
  };
  if (window.katex) window.renderTex();
  (() => {
    // contents panel on narrow screens
    const btn = document.querySelector('.toc-btn'), toc = document.getElementById('toc');
    if (btn && toc) {
      const set = (open) => { document.body.classList.toggle('toc-open', open); btn.setAttribute('aria-expanded', String(open)); };
      btn.addEventListener('click', () => set(!document.body.classList.contains('toc-open')));
      toc.addEventListener('click', (e) => { if (e.target.closest('a')) set(false); });
      document.addEventListener('keydown', (e) => { if (e.key === 'Escape') set(false); });
    }
    // long paragraphs: clamp with a More / Less toggle (text stays in the DOM);
    // chapter ledes (p.framing.lede) always clamp to two lines regardless of
    // length, so every chapter opens with a fast-scan preview
    const cs = document.documentElement.lang === 'cs';
    const L = cs ? ['Více', 'Méně'] : ['More', 'Less'];
    const clampCandidates = [
      ...document.querySelectorAll('.container > p:not(.framing):not(.capita-note):not(.formula):not(.continue):not(.hero-footnote):not(.slide-a):not(.slide-how), .container > .muted.small'),
      ...document.querySelectorAll('.container > p.framing.lede'),
    ];
    clampCandidates.forEach((p) => {
      const lede = p.classList.contains('lede');
      const narrow = matchMedia('(max-width: 719px)').matches;
      if (!lede && p.textContent.trim().length < (narrow ? 360 : 480)) return;
      p.classList.add('clamp');
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'clamp-btn'; b.textContent = L[0]; b.setAttribute('aria-expanded', 'false');
      b.addEventListener('click', () => { const open = p.classList.toggle('clamp-open'); b.textContent = open ? L[1] : L[0]; b.setAttribute('aria-expanded', String(open)); });
      p.after(b);
    });
    // player index: filter rows by name (no library)
    const q = document.getElementById('player-search');
    const table = document.querySelector('.player-index-table');
    if (q && table) {
      const rows = [...table.querySelectorAll('tbody tr[data-name]')];
      const count = document.querySelector('.player-index-count');
      const fold = table.closest('details');
      const ascii = (s) => s.normalize('NFKD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();
      q.addEventListener('input', () => {
        const needle = ascii(q.value.trim());
        let shown = 0;
        rows.forEach((r) => { const hit = !needle || r.dataset.name.includes(needle); r.hidden = !hit; if (hit) shown++; });
        if (count) count.textContent = shown;
        if (fold && needle) fold.open = true;
      });
    }
  })();
  (() => {
    document.querySelectorAll('.capita').forEach((capita) => {
      if (!('IntersectionObserver' in window)) return;
      capita.dataset.animate = '';
      const io = new IntersectionObserver((entries) => {
        if (entries.some(e => e.isIntersecting)) { capita.dataset.animate = 'in'; io.disconnect(); }
      }, { threshold: 0.3 });
      io.observe(capita);
    });
    const links = [...document.querySelectorAll('.toc-sticky a[href^="#"]')];
    const targets = links.map(a => document.getElementById(a.hash.slice(1))).filter(Boolean);
    if (targets.length) {
      const byId = new Map(links.map(a => [a.hash.slice(1), a]));
      let current = null, ticking = false;
      const update = () => {
        ticking = false;
        const line = 96;
        let best = null;
        for (const t of targets) { if (t.getBoundingClientRect().top <= line) best = t; else break; }
        const id = best ? best.id : null;
        if (id === current) return;
        current = id;
        links.forEach(a => a.removeAttribute('aria-current'));
        if (id) byId.get(id)?.setAttribute('aria-current', 'true');
      };
      addEventListener('scroll', () => { if (!ticking) { ticking = true; requestAnimationFrame(update); } }, { passive: true });
      update();
    }
  })();
</script>
</body>"""
sub(r'</body>', lambda m: JS, 1)

# ---------------------------------------------------------------- cache-busting stamp on our own assets
_v = _dt.datetime.now().strftime("%Y%m%d%H%M")
for _a in ("style.css", "modern.css", "atlas.js"):
    html = html.replace(f'"{P}{_a}"', f'"{P}{_a}?v={_v}"')

SRC.write_text(html, encoding="utf-8")
if fails:
    print("FAILED:", *fails, sep="\n  ")
    sys.exit(1)
print(f"ok ({LANG}): {len(CARDS)} cards, {sum(1 for c in CARDS if photo(c['key']))} with portraits")
