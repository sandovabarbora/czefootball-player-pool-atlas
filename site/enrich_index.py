"""Site layer over one rendered page (English or Czech — `--lang` picks the strings):

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

Portraits come from site/players.json (fbref_id -> player_key, image); the
template puts `data-player-key` / `data-fbref-id` on every element that can
carry one, so matching is exact. Every substitution asserts its match count
and the script fails loudly when the page changed under it.

usage: enrich_index.py docs/index.html --lang en
       enrich_index.py docs/cs/index.html --lang cs
"""
import argparse
import datetime as _dt
import json
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
P = "" if LANG == "en" else "../"          # asset prefix relative to the page
PLAYERS = json.load(open(Path(__file__).with_name("players.json"), encoding="utf-8"))
BY_KEY = {v["player_key"]: dict(v, fbref_id=k) for k, v in PLAYERS.items()}
SITE = "https://football.datasimply.eu/"
html = SRC.read_text(encoding="utf-8")
fails: list[tuple] = []

S = {
    "en": {
        "nav_aria": "Navigation", "brand": "Czech Football <span>Atlas</span>",
        "nav": [("#summary", "Summary"), ("#pathways", "Pathways"), ("#cards", "Cards"), ("#methodology", "Methodology")],
        "lang_aria": "Language", "contents": "Contents",
        "cast": "{n} player profiles", "in_context": "In context",
        "analog_fold": "{n} nearest analogs and what followed",
        "loadings": "Loadings table", "scenarios": "Scenario table",
    },
    "cs": {
        "nav_aria": "Navigace", "brand": "Český fotbal <span>Atlas</span>",
        "nav": [("#summary", "Shrnutí"), ("#pathways", "Cesty"), ("#cards", "Karty"), ("#methodology", "Metodologie")],
        "lang_aria": "Jazyk", "contents": "Obsah",
        "cast": "{n} profilů hráčů", "in_context": "Souvislosti",
        "analog_fold": "{n} nejbližších analogů a jejich pokračování",
        "loadings": "Tabulka loadings", "scenarios": "Tabulka scénářů",
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

# ---------------------------------------------------------------- Czech page: the translated SVGs sit next to it in docs/cs/
if LANG == "cs":
    sub(r'<img src="\.\./(atlas_[A-Z]{2}\.svg|intl_cohort_heatmap\.svg)"', r'<img src="\1"', 4)

# ---------------------------------------------------------------- top bar
links = "\n".join(f'    <a href="{h}">{l}</a>' for h, l in S["nav"])
switch = ('<span aria-current="page" lang="en">EN</span><a href="cs/" hreflang="cs" lang="cs">CS</a>' if LANG == "en"
          else '<a href="../" hreflang="en" lang="en">EN</a><span aria-current="page" lang="cs">CS</span>')
TOPBAR = f'''<nav class="topbar" aria-label="{S["nav_aria"]}">
  <a class="topbar-brand" href="#top">{S["brand"]}</a>
  <div class="topbar-links">
{links}
  </div>
  <button type="button" class="toc-btn" aria-controls="toc" aria-expanded="false">{S["contents"]}</button>
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
if len(CARDS) != 12:
    fails.append(("cycle cards found", len(CARDS), 12))

# ---------------------------------------------------------------- masthead cast strip
def cast_item(c: dict) -> str:
    p = photo(c["key"])
    if p:
        return f'<img src="{P}{p["image"]}" alt="{c["name"]}" {IMG_ATTRS}>'
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

sub(CARD_RE.pattern, card_repl, 12)

# ---------------------------------------------------------------- analog targets: portrait
def analog_repl(m):
    key, ws = m.group(1), m.group(2)
    p = photo(key)
    img = f'{ws}  <img class="avatar avatar-xl" src="{P}{p["image"]}" alt="" {IMG_ATTRS}>' if p else ""
    return f'<div class="analog-block" data-player-key="{key}">{ws}<div class="analog-target">{img}'

sub(r'<div class="analog-block" data-player-key="([^"]+)">(\s*)<div class="analog-target">', analog_repl, 12)

# ---------------------------------------------------------------- chips: cluster top lists, movers
def top_repl(m):
    names = re.findall(r'<span class="cluster-top-name" data-player-key="([^"]+)">([^<]+)</span>', m.group(1))
    return '<span class="cluster-top">' + "".join(chip(k, n) for k, n in names) + '</span>'

sub(r'<span class="cluster-top">(.*?)</span></span>', top_repl, None, re.S)
sub(r'<td data-player-key="([^"]+)">([^<]+)</td>', lambda m: f'<td>{chip(m.group(1), m.group(2), "sm")}</td>', None)

# ---------------------------------------------------------------- folds
# limitations: each <p><strong>Title.</strong> text</p> -> details, first one open
def lim_fold(m):
    title, text = m.group(1), m.group(2).strip()
    return f'<details class="fold fold-lim"><summary>{title}</summary><p>{text}</p></details>'
sub(r'<p><strong>([^<]+?)\.?</strong>\s*(.*?)</p>', lim_fold, 10, re.S)
sub(r'(<div class="limitations">\s*)<details class="fold fold-lim">', r'\1<details class="fold fold-lim" open>', 1)

# historical analogs: each list folds; the first target stays open
_first = [True]
def analog_fold(m):
    o = ' open' if _first[0] else ''
    _first[0] = False
    n = len(re.findall(r'<li class="analog-row">', m.group(1)))
    return f'<details class="fold analog-fold"{o}><summary>{S["analog_fold"].format(n=n)}</summary>{m.group(1)}</details>'
sub(r'(<ol class="analog-list">.*?</ol>)', analog_fold, 12, re.S)

# cycle cards: analogs fold (stats, clusters, tactical read and trajectory stay visible)
sub(r'<div class="cycle-section">\s*<p class="cycle-section-label">([^<]*)</p>\s*(<ol class="cycle-analogs">.*?</ol>)\s*</div>',
    r'<details class="fold cycle-section"><summary class="cycle-section-label">\1</summary>\2</details>', 12, re.S)

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
    // long paragraphs: clamp with a More / Less toggle (text stays in the DOM)
    const cs = document.documentElement.lang === 'cs';
    const L = cs ? ['Více', 'Méně'] : ['More', 'Less'];
    document.querySelectorAll('.container > p:not(.framing):not(.capita-note):not(.formula):not(.continue):not(.hero-footnote), .container > .muted.small').forEach((p) => {
      const narrow = matchMedia('(max-width: 719px)').matches;
      if (p.textContent.trim().length < (narrow ? 360 : 480)) return;
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
