"""Structural upgrades to docs/index.html (Czech source):
- topbar with language switch, modern.css link, hreflang alternates
- NHL headshots / action shots on player cards, briefs, analog targets
- avatar chips in cluster top lists + movers tables
- masthead cast strip
Runs BEFORE translate_index.py.
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

SRC = Path(sys.argv[1])
PLAYERS = json.load(open(Path(__file__).with_name("players.json")))
html = SRC.read_text(encoding="utf-8")
fails = []

# players with a current NHL photo (skip stale pre-2024 mugs)
USE = {"David Pastrnak", "Martin Necas", "Pavel Zacha", "Tomas Hertl", "Jiri Kulich", "Filip Chytil",
       "Adam Klapka", "Radek Faksa", "Tomas Nosek", "Ondrej Palat", "David Kampf", "Filip Hronek",
       "Radko Gudas", "David Jiricek", "Karel Vejmelka"}


def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z ]", "", s.lower()).strip()


BY_KEY = {norm(k): v for k, v in PLAYERS.items() if k in USE}


def player(name: str):
    return BY_KEY.get(norm(name.replace("*", "")))


def slug(name: str) -> str:
    return norm(name).replace(" ", "-")


def initials(name: str) -> str:
    parts = name.replace("*", "").split()
    return "".join(p[0] for p in parts[:2]).upper()


IMG_ATTRS = 'loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="this.closest(\'.pchip\')?.classList.add(\'pchip-mono\'); this.remove()"'


def chip(name: str, size: str = "") -> str:
    p = player(name)
    cls = "pchip" + (f" pchip-{size}" if size else "")
    if p:
        return (f'<span class="{cls}"><img class="pchip-img" src="{p["headshot"]}" alt="" {IMG_ATTRS}>'
                f'<span class="pchip-initials" aria-hidden="true">{initials(name)}</span>'
                f'<span class="pchip-name">{name}</span></span>')
    return (f'<span class="{cls} pchip-mono"><span class="pchip-initials" aria-hidden="true">{initials(name)}</span>'
            f'<span class="pchip-name">{name}</span></span>')


def sub(pat, repl, want, flags=0):
    global html
    html, n = re.subn(pat, repl, html, flags=flags)
    if n != want:
        fails.append((pat[:60], n, want))


# ---------------------------------------------------------------- head
sub(r'<link href="https://fonts\.googleapis\.com/css2\?family=Spectral[^"]*" rel="stylesheet">',
    '<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">',
    1)
sub(r'<link rel="stylesheet" href="style\.css">',
    '<link rel="stylesheet" href="style.css">\n  <link rel="stylesheet" href="modern.css">\n'
    '  <link rel="alternate" hreflang="en" href="https://hockey.datasimply.eu/">\n'
    '  <link rel="alternate" hreflang="cs" href="https://hockey.datasimply.eu/cs/">\n'
    '  <link rel="alternate" hreflang="x-default" href="https://hockey.datasimply.eu/">',
    1)


# ---------------------------------------------------------------- KaTeX for the methodology formulas
sub(r'  <link rel="stylesheet" href="modern.css">',
    '  <link rel="stylesheet" href="modern.css">\n'
    '  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.11/katex.min.css">\n'
    '  <script defer src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.11/katex.min.js" onload="window.renderTex && window.renderTex()"></script>', 1)
sub(r'<p class="formula">\s*shrunk_rate = \(počet_eventů \+ K × cohort_medián\) / \(player_GP \+ K\), &nbsp; K = 10\s*</p>',
    '<p class="formula" data-tex="\\\\text{shrunk rate} = \\\\dfrac{\\\\text{počet eventů} + K \\\\cdot \\\\text{medián kohorty}}{\\\\text{GP hráče} + K},\\\\qquad K = 10">shrunk_rate = (počet_eventů + K × cohort_medián) / (player_GP + K), &nbsp; K = 10</p>', 1)
sub(r'(<h3 id="nasobicky">[^<]*</h3>)',
    r'\1\n    <p class="formula" data-tex="\\text{P/GP}_{\\text{quality}} = \\text{P/GP}_{\\text{shrunk}} \\times m_{\\text{liga}}">P/GP_quality = P/GP_shrunk × m_liga</p>', 1)


# ---------------------------------------------------------------- interactive atlases
sub(r'<figure class="figure-bleed">(\s*)<img src="intl_cohort_heatmap.svg"', r'<figure class="figure-bleed" data-atlas="heatmap">\1<img src="intl_cohort_heatmap.svg"', 1)
sub(r'<figure class="figure-bleed">(\s*)<img src="atlas_forwards.svg"', r'<figure class="figure-bleed" data-atlas="forwards">\1<img src="atlas_forwards.svg"', 1)
sub(r'<figure class="figure-bleed">(\s*)<img src="atlas_defense.svg"', r'<figure class="figure-bleed" data-atlas="defense">\1<img src="atlas_defense.svg"', 1)
sub(r'(<h3 id="cluster-archetypy">[^<]*</h3>\s*)<dl class="cluster-list">', r'\1<dl class="cluster-list" data-atlas-clusters="forwards">', 1)
sub(r'(<h3 id="cluster-obranci">[^<]*</h3>\s*)<dl class="cluster-list">', r'\1<dl class="cluster-list" data-atlas-clusters="defense">', 1)
sub(r'(onload="window.renderTex && window.renderTex\(\)"></script>)', r'\1\n  <script defer src="atlas.js"></script>', 1)

# ---------------------------------------------------------------- topbar (Czech is current; translate script swaps)
TOPBAR = '''<nav class="topbar" aria-label="Navigace">
  <a class="topbar-brand" href="#top">Český hokej <span>Atlas</span></a>
  <div class="topbar-links">
    <a href="#shrnuti">Shrnutí</a>
    <a href="#ai-vrstva">AI vrstva</a>
    <a href="#metodologie">Metodologie</a>
  </div>
  <div class="lang-switch" aria-label="Jazyk">
    <a href="../" hreflang="en" lang="en">EN</a><span aria-current="page" lang="cs">CS</span>
  </div>
</nav>
'''
sub(r'<body>\n', '<body id="top">\n' + TOPBAR, 1)

# ---------------------------------------------------------------- masthead cast strip
CAST = ["David Pastrňák", "Martin Nečas", "Filip Hronek", "Pavel Zacha", "Jiří Kulich", "David Jiříček"]
cast_imgs = "".join(
    f'<img src="{player(n)["headshot"]}" alt="{n}" {IMG_ATTRS}>' for n in CAST)
cast_html = f'''
    <a class="cast" href="#cyklus-dashboard">
      <span class="cast-stack">{cast_imgs}</span>
      <span class="cast-caption">Profily šesti hráčů: Pastrňák, Nečas, Hronek, Zacha, Kulich, Jiříček</span>
    </a>
'''
sub(r'(<dl class="masthead-meta">.*?</dl>\n)', lambda m: m.group(1) + cast_html, 1, re.S)


# ---------------------------------------------------------------- hero: asterisk rule + posterised cut-out
sub(r'<span class="hero-num-figure">1,38</span>',
    '<span class="hero-num-figure">1,38<span class="ast" aria-hidden="true">*</span></span>', 1)
sub(r'(\s*)<dl class="hero-meta">',
    lambda m: (m.group(1) + '<p class="hero-footnote">* 15 hráčů s birth_country = CZE na soupiskách NHL 2025/26 '
               '(NHL Stats API) ÷ 10,9 M obyvatel (odhad 2024); peer země počítány stejně. '
               '<a href="#metodologie">Metodologie</a>.</p>' + m.group(1) + '<dl class="hero-meta">'), 1)
_pasta = player("David Pastrňák")
sub(r'<section class="hero" id="shrnuti">',
    f'<section class="hero" id="shrnuti">\n  <img class="hero-cutout" src="{_pasta["headshot"]}" alt="" aria-hidden="true" decoding="async" referrerpolicy="no-referrer" onerror="this.remove()">', 1)


# ---------------------------------------------------------------- Nečas card (data: docs/cards/martin-necas.json + docs/briefs/martin-necas.md)
NECAS_CARD = """<article class="cycle-card">
        <header class="cycle-card-head">
          <h4 class="cycle-card-name">Martin Nečas</h4>
          <p class="cycle-card-meta">
            F &middot; věk 27 &middot; NHL
             &middot; MS 24/25 ×2
          </p>
        </header>
        <dl class="cycle-stats">
          <div><dt>P/GP quality</dt><dd>1,18</dd></div>
          <div><dt>z-score</dt><dd>+6,41</dd></div>
          <div><dt>GP / P</dt><dd>78 / 100</dd></div>
        </dl>
        <div class="cycle-cluster">
          <span class="cycle-cluster-row">
            <span class="cycle-cluster-tag">style</span>
            <span class="cycle-cluster-pill">C0</span>
            <span class="cycle-cluster-label">Top-six skórující</span>
          </span>
          <span class="cycle-cluster-row">
            <span class="cycle-cluster-tag">quality</span>
            <span class="cycle-cluster-pill">C3</span>
            <span class="cycle-cluster-label">EU veteráni</span>
          </span>
        </div>
        <div class="cycle-section">
          <p class="cycle-section-label">Tactical read</p>
          <p class="cycle-tactical">Shooting-heavy top-six profil. Statistický otisk konzistentní s hráči, kteří generují vlastní střelu z controlled-entry situations a drží PP1 minutáž. Reprezentační kontext: hráči tohoto clusteru typicky nesou ofenzivní zatížení první lajny.</p>
        </div>
        <div class="cycle-section">
          <p class="cycle-section-label">Trajektorie 24/25 &rarr; 25/26</p>
          <p class="cycle-traj">
            <span class="cycle-traj-delta">Δ +0,204 P/GP</span>
            <span class="cycle-traj-dir">improving</span>
            <span class="cycle-traj-detail">79 GP &rarr; 78 GP</span>
          </p>
        </div>
        <div class="cycle-section">
          <p class="cycle-section-label">LLM brief excerpt</p>
          <p class="cycle-brief-excerpt">Nečas spadá do style clusteru C0 (Top-six skórující) s extrémní pozicí na produkční ose — PCA style souřadnice (5.46, -0.04), quality (8.52, -0.27) ho řadí mezi nejvyhraněnější skórující profily v korpusu. Quality-adjusted P/GP 1.175 (G/GP 0.454, A/GP 0.721) s cross-league z-score +6.414 znamená více než šest směrodatných odchylek nad…</p>
        </div>
      </article>
      """
# place it right after Pastrňák's card
sub(r'(<article class="cycle-card">\s*<header class="cycle-card-head">\s*<h4 class="cycle-card-name">David Pastrňák</h4>.*?</article>\s*)',
    lambda m: m.group(1) + NECAS_CARD, 1, re.S)

# ---------------------------------------------------------------- cycle cards
def card_repl(m):
    ws1, ws2, name = m.group(1), m.group(2), m.group(3)
    p = player(name)
    if not p:
        return m.group(0)
    visual = (f'{ws1}<div class="cycle-card-visual" style="--hero: url(\'{p["hero"]}\')">'
              f'{ws2}<img class="cycle-card-mug" src="{p["headshot"]}" alt="" {IMG_ATTRS}>'
              f'{ws2}<span class="cycle-card-jersey" aria-hidden="true">{p["number"]}</span>'
              f'{ws2}<span class="cycle-card-team">{p["team"]}</span>'
              f'{ws1}</div>')
    return (f'<article class="cycle-card" id="card-{slug(name)}">{visual}'
            f'{ws1}<header class="cycle-card-head">{ws2}<h4 class="cycle-card-name">{name}</h4>')

sub(r'<article class="cycle-card">(\s*)<header class="cycle-card-head">(\s*)<h4 class="cycle-card-name">([^<]+)</h4>',
    card_repl, 6)

# ---------------------------------------------------------------- llm brief heads
def brief_repl(m):
    ws, name = m.group(1), m.group(2)
    p = player(name)
    img = (f'{ws}<img class="avatar avatar-lg" src="{p["headshot"]}" alt="" {IMG_ATTRS}>' if p else "")
    return f'<header class="llm-brief-head">{img}{ws}<div class="llm-brief-headtext">{ws}<h4 class="llm-brief-title">{name}</h4>'

sub(r'<header class="llm-brief-head">(\s*)<h4 class="llm-brief-title">([^<]+)</h4>', brief_repl, 2)
sub(r'(<p class="llm-brief-meta-line">[^<]*</p>)(\s*)</header>', r'\1\2</div>\2</header>', 2)

# ---------------------------------------------------------------- analog targets
def analog_repl(m):
    ws, label, name = m.group(1), m.group(2), m.group(3)
    p = player(name)
    img = (f'{ws}<img class="avatar avatar-xl" src="{p["headshot"]}" alt="" {IMG_ATTRS}>' if p else "")
    return f'<div class="analog-target">{img}{ws}<p class="analog-label">{label}</p>{ws}<p class="analog-name">{name}</p>'

sub(r'<div class="analog-target">(\s*)<p class="analog-label">([^<]+)</p>\s*<p class="analog-name">([^<]+)</p>',
    analog_repl, 5)

# ---------------------------------------------------------------- cluster top lists -> chips
def top_repl(m):
    names = [n.strip() for n in m.group(1).split(",")]
    return '<span class="cluster-top">' + "".join(chip(n) for n in names) + '</span>'

sub(r'<span class="cluster-top">([^<]+)</span>', top_repl, 10)

# ---------------------------------------------------------------- movers tables -> chips
def mover_repl(m):
    return f'{m.group(1)}<td>{chip(m.group(2), "sm")}</td>{m.group(3)}'

sub(r'(<tr>\s*)<td>([A-Za-zÀ-ž ]+)</td>(\s*<td class="muted">)', mover_repl, 5)


# ---------------------------------------------------------------- behaviour: bar reveal + active TOC
JS = """<script>
  window.renderTex = () => {
    document.querySelectorAll('[data-tex]').forEach(el => {
      try { katex.render(el.dataset.tex, el, { displayMode: true, throwOnError: false }); el.classList.add('formula-tex'); } catch (e) {}
    });
  };
  if (window.katex) window.renderTex();
  (() => {
    const capita = document.querySelector('.capita');
    if (capita && 'IntersectionObserver' in window) {
      capita.dataset.animate = '';
      const io = new IntersectionObserver((entries) => {
        if (entries.some(e => e.isIntersecting)) { capita.dataset.animate = 'in'; io.disconnect(); }
      }, { threshold: 0.3 });
      io.observe(capita);
    }
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

SRC.write_text(html, encoding="utf-8")
if fails:
    print("FAILED:", *fails, sep="\n  ")
    sys.exit(1)
print("ok")
