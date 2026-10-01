"""Split the one long report page into a short front page and one page per
question -- the last step of the site layer (site/build.sh), after
enrich_index.py and build_atlas.py.

  index.html            summary: masthead, hero, the question and
                        contribution, the dated teaser, the findings, the
                        metadata block, the facts strip, the brief, how to
                        cite and the change log
  q/<slug>/index.html   one question each: the slide, the evidence from
                        "Explore the data" that belongs to it, previous/next
  this-autumn/          the dated news section with its sources (when the
                        edition has one)
  methodology/          chapter IV whole, and the downloads
  players/              the player atlas (build_atlas.py); atlas/ becomes a
                        redirect to it, keeping the #p/... hash

Nothing is rewritten: every block is cut out of the enriched page as it is
and pasted into its new page; only URLs change (asset paths get the page's
depth, #anchors that moved point at their new page, atlas/ -> players/),
headings/links needed to navigate are added, and each finding's first body
paragraph stays visible on the front page while the rest folds under it.
Old links keep working: the front page carries a map from every id of the
old page to the page it now lives on and forwards #q1, #methodology, ... on
load (GitHub Pages has no server redirects).

Every block of the page must be claimed by a rule below; an unknown block
fails the build, like enrich_index.py's match counts.

usage: split_pages.py <site dir>         (NATION env var, default cze)
"""

from __future__ import annotations

import html as _html
import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

D = Path(sys.argv[1]).resolve()
NATION = os.environ.get("NATION", "cze").lower()
SITE = "https://football.bsandova.com/"
EDITIONS = {"cze": "/", "eng": "/eng/", "ger": "/ger/", "den": "/den/", "nor": "/nor/", "esp": "/esp/"}
ED_ROOT = EDITIONS.get(NATION, f"/{NATION}/")
DOCS = Path(__file__).resolve().parents[1] / "docs"
MARK = '<meta name="atlas-split" content="1">'

# (slug, blocks from the old page) in the order the report told them; the
# explore folds (keyed by their h3 id) follow the slide as its evidence
QUESTIONS = [
    ("why", "why-funnel", ["pathways"]),
    ("per-head", "q1", []),
    ("cohorts", "q2", ["benchmark"]),
    ("youth", "q3", []),
    ("abroad", "q4", []),
    ("leaving-late", "q4b", []),
    ("fare", "q5", []),
    ("national-team", "q6", []),
    ("break", "q7", []),
    ("peers", "q8", []),
    ("goalkeepers", "q8b", []),
    ("gap", "q8c", []),
    ("cards", "q9", []),
    ("changes", "q10", ["trajectories"]),
]
METHOD_FOLDS = ["downloads"]
# folds no page shows: the cluster maps repeat the cards page's interactive
# atlas, the player index repeats its pool list and the players page, and each
# card already carries its analogs. Old links to them go to the players page.
DROPPED_FOLDS = ["clusters", "analogs", "players"]
CARDS_MORE = ('<section class="explore qpage-evidence">\n  <div class="container">\n    '
              '<p class="front-more">The full pool and every player\'s career: <a href="players/">Players</a></p>\n'
              '  </div>\n</section>')
# what to take from it, by position: the question page that holds its evidence
TAKE_TO = ["break", "gap", "youth", "why", "youth"]


# ---------------------------------------------------------------- a tree of offsets over the page
class Node:
    __slots__ = ("tag", "attrs", "start", "open_end", "end", "children", "parent")

    def __init__(self, tag, attrs, start, open_end, parent):
        self.tag, self.attrs, self.start, self.open_end = tag, dict(attrs), start, open_end
        self.end, self.children, self.parent = None, [], parent

    def cls(self) -> list[str]:
        return (self.attrs.get("class") or "").split()

    def find(self, pred):
        for c in self.children:
            if pred(c):
                return c
            hit = c.find(pred)
            if hit:
                return hit
        return None


VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class Tree(HTMLParser):
    def __init__(self, text: str):
        super().__init__(convert_charrefs=False)
        self.text = text
        self.lines = [0]
        for m in re.finditer("\n", text):
            self.lines.append(m.end())
        self.root = Node("#root", {}, 0, 0, None)
        self.stack = [self.root]
        self.feed(text)
        self.close()
        for n in self.stack[1:]:
            n.end = len(text)

    def _off(self):
        line, col = self.getpos()
        return self.lines[line - 1] + col

    def handle_starttag(self, tag, attrs):
        s = self._off()
        n = Node(tag, attrs, s, s + len(self.get_starttag_text()), self.stack[-1])
        self.stack[-1].children.append(n)
        if tag in VOID:
            n.end = n.open_end
        else:
            self.stack.append(n)

    def handle_startendtag(self, tag, attrs):
        s = self._off()
        n = Node(tag, attrs, s, s + len(self.get_starttag_text()), self.stack[-1])
        n.end = n.open_end
        self.stack[-1].children.append(n)

    def handle_endtag(self, tag):
        if not any(n.tag == tag for n in self.stack[1:]):
            return
        e = self.text.index(">", self._off()) + 1
        while self.stack:
            n = self.stack.pop()
            n.end = e
            if n.tag == tag:
                break


def src(n: Node) -> str:
    return TEXT[n.start:n.end]


def inner(n: Node) -> str:
    close = TEXT.rfind("</", n.open_end, n.end)
    return TEXT[n.open_end:close]


def plain(fragment: str) -> str:
    return _html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", fragment))).strip()


# ---------------------------------------------------------------- read the page
index = D / "index.html"
TEXT = index.read_text(encoding="utf-8")
if MARK in TEXT:
    sys.exit(f"{index} is already split -- rebuild it (site/build.sh) before splitting again")
tree = Tree(TEXT)
html_el = tree.root.find(lambda n: n.tag == "html")
head = html_el.find(lambda n: n.tag == "head")
body = html_el.find(lambda n: n.tag == "body")
HTML_OPEN = TEXT[html_el.start:html_el.open_end]
BODY_OPEN = TEXT[body.start:body.open_end]
HEAD = inner(head)
TITLE = plain(re.search(r"<title>(.*?)</title>", HEAD, re.S).group(1))

blocks = {}
acts: dict[str, str] = {}
scripts: list[str] = []
pending_act = None
unclaimed = []
for n in body.children:
    c, i = n.cls(), n.attrs.get("id")
    if n.tag == "div" and "act" in c:
        pending_act = src(n)
        continue
    if n.tag == "section" and "slide" in c and i and i.startswith("q"):
        blocks[i] = n
        if pending_act:
            acts[i] = pending_act
            pending_act = None
        continue
    key = {("nav", "topbar"): "topbar", ("nav", "toc-sticky"): "toc", ("a", "skip-link"): "skip",
           ("header", "report-header"): "masthead", ("section", "hero"): "hero", ("section", "take"): "take",
           ("section", "quickread"): "quickread", ("section", "why-funnel"): "why-funnel",
           ("section", "autumn"): "autumn", ("section", "for-federation"): "for-federation",
           ("section", "brief"): "brief", ("section", "explore"): "explore",
           ("aside", "chapter-divider"): "chapter", ("section", "methodology"): "methodology",
           ("section", "close"): "close", ("section", "contribution"): "contribution",
           ("section", "colophon"): "colophon", ("section", "citelog"): "citelog"}
    k = next((v for (t, cl), v in key.items() if n.tag == t and cl in c), None)
    if k:
        blocks[k] = n
    elif n.tag == "footer":
        blocks["footer"] = n
    elif n.tag == "script":
        scripts.append(src(n))
    else:
        unclaimed.append(TEXT[n.start:n.open_end])
if unclaimed:
    sys.exit(f"split_pages: blocks no rule claims: {unclaimed}")
for need in ("topbar", "hero", "masthead", "explore", "methodology", "footer"):
    if need not in blocks:
        sys.exit(f"split_pages: the page has no {need} block")

# the explore section's folds, by the id of the h3 each one opens with
explore = blocks["explore"]
ex_container = explore.find(lambda n: n.tag == "div" and "container" in n.cls())
FOLDS: dict[str, str] = {}
EXPLORE_H2 = None
for n in ex_container.children:
    if n.tag == "h2":
        EXPLORE_H2 = src(n)
    elif n.tag == "details":
        h3 = n.find(lambda x: x.tag == "h3" and x.attrs.get("id"))
        if not h3:
            sys.exit("split_pages: an explore fold without an h3 id")
        FOLDS[h3.attrs["id"]] = src(n)
    else:
        sys.exit(f"split_pages: unexpected block in explore: {TEXT[n.start:n.open_end]}")
claimed = {f for _, _, fs in QUESTIONS for f in fs} | set(METHOD_FOLDS) | set(DROPPED_FOLDS)
if set(FOLDS) - claimed:
    sys.exit(f"split_pages: explore folds no page claims: {sorted(set(FOLDS) - claimed)}")

# ---------------------------------------------------------------- labels from the old page itself
topbar = blocks["topbar"]
BRAND = inner(topbar.find(lambda n: n.tag == "a" and "topbar-brand" in n.cls()))
TOP_LABELS = {plain(inner(a)): a.attrs.get("href") for a in topbar.find(lambda n: "topbar-links" in n.cls()).children if a.tag == "a"}
TOC_LABELS: dict[str, str] = {}
METHOD_TOC = ""
if "toc" in blocks:
    toc = blocks["toc"]
    for a in re.finditer(r'<a href="#([^"]+)">(.*?)</a>', src(toc)):
        TOC_LABELS.setdefault(a.group(1), plain(a.group(2)))
    m = re.search(r'<details class="toc-method">.*?</details>', src(toc), re.S)
    METHOD_TOC = m.group(0) if m else ""

questions = []   # dicts: slug, sid, title, label, html
for slug, sid, folds in QUESTIONS:
    if sid not in blocks:
        continue
    b = src(blocks[sid])
    h2 = re.search(r"<h2[^>]*>(.*?)</h2>", b, re.S)
    title = plain(h2.group(1)) if h2 else slug
    questions.append({"slug": slug, "sid": sid, "title": title, "label": TOC_LABELS.get(sid, title),
                      "folds": [f for f in folds if f in FOLDS]})
HAS_AUTUMN = "autumn" in blocks


# ---------------------------------------------------------------- navigation (the one new piece of markup)
def topbar_html(rel: str, current: str, switch_path: str = "", toc: bool = False) -> str:
    def a(href, label, key):
        cur = ' aria-current="page"' if key == current else ""
        return f'<a href="{href}"{cur}>{label}</a>'
    here = ' aria-current="page"'
    qs = "\n".join(
        f'        <li><a href="{rel}q/{q["slug"]}/"{here if current == "q/" + q["slug"] else ""}>{_html.escape(q["label"])}</a></li>'
        for q in questions)
    q_open = " data-current" if current.startswith("q/") else ""
    links = [a(rel or "./", "Summary", "summary"),
             f'<details class="topbar-q"{q_open}>\n      <summary>Questions</summary>\n      <ol class="topbar-q-list">\n{qs}\n      </ol>\n    </details>']
    if HAS_AUTUMN:
        links.append(a(f"{rel}this-autumn/", "This autumn", "this-autumn"))
    links += [a(f"{rel}methodology/", "Methodology", "methodology"), a(f"{rel}players/", "Players", "players")]
    if "Nations" in TOP_LABELS:
        links.append(a(TOP_LABELS["Nations"], "Nations", "nations"))
    built = [c for c, r in EDITIONS.items() if c == NATION or (DOCS / r.strip("/") / "index.html").exists()]
    # the same page in another edition, when every edition has it
    switch = " · ".join(
        f'<span aria-current="page">{c.upper()}</span>' if c == NATION else f'<a href="{EDITIONS[c]}{switch_path}">{c.upper()}</a>'
        for c in built)
    joined = "\n    ".join(links)
    toc_btn = '\n  <button type="button" class="toc-btn" aria-controls="toc" aria-expanded="false">Contents</button>' if toc else ""
    return f'''<nav class="topbar" aria-label="Navigation">
  <a class="topbar-brand" href="{rel or './'}">{BRAND}</a>
  <button type="button" class="menu-btn" aria-controls="site-menu" aria-expanded="false">Menu</button>{toc_btn}
  <div class="topbar-links" id="site-menu">
    {joined}
    <p class="menu-switch" aria-label="Atlas">{switch}</p>
  </div>
  <div class="atlas-switch" aria-label="Atlas">
    {switch}
  </div>
</nav>'''


NAV_JS = """<script>
  (() => {
    // phone: the menu button opens the links as a panel; desktop: the
    // Questions list closes on a click elsewhere or on Escape
    const btn = document.querySelector('.menu-btn'), menu = document.getElementById('site-menu');
    if (btn && menu) {
      const set = (open) => { document.body.classList.toggle('menu-open', open); btn.setAttribute('aria-expanded', String(open)); };
      btn.addEventListener('click', () => set(!document.body.classList.contains('menu-open')));
      document.addEventListener('keydown', (e) => { if (e.key === 'Escape') set(false); });
    }
    const q = document.querySelector('.topbar-q');
    if (q) {
      if (matchMedia('(max-width: 719px)').matches) q.open = true;
      document.addEventListener('click', (e) => { if (!matchMedia('(max-width: 719px)').matches && !q.contains(e.target)) q.open = false; });
      document.addEventListener('keydown', (e) => { if (e.key === 'Escape') q.open = false; });
    }
  })();
</script>"""


# ---------------------------------------------------------------- where every id of the old page now lives
PAGES: dict[str, list[str]] = {}   # page path ("" = front) -> html fragments of its body


def ids(fragment: str) -> list[str]:
    return re.findall(r'\sid="([^"]+)"', fragment)


def rewrite(fragment: str, rel: str, here: str, where: dict[str, str]) -> str:
    """Asset and page URLs for a page `rel` deep; #anchors that moved go to their page."""
    def fix_url(u: str) -> str:
        if not u or re.match(r"^(?:[a-z]+:|/|#|\?|data:)", u):
            return u
        if u == "./":   # the edition's front page
            return rel or u
        if u == "atlas/" or u.startswith("atlas/"):
            u = "players/" + u[len("atlas/"):]
        return rel + u

    def fix_attr(m):
        name, q, val = m.group(1), m.group(2), m.group(3)
        if name == "href" and val.startswith("#") and len(val) > 1:
            target = where.get(val[1:])
            if target is not None and target != here:
                return f'{name}={q}{rel}{target}{val}{q}' if (rel + target) else f'{name}={q}./{val}{q}'
            return m.group(0)
        if name == "srcset":
            return f'{name}={q}' + ", ".join(fix_url(p.strip().split(" ")[0]) + (" " + " ".join(p.strip().split(" ")[1:]) if " " in p.strip() else "")
                                             for p in val.split(",")) + q
        return f'{name}={q}{fix_url(val)}{q}'

    def fix_tag(m):
        tag = m.group(0)
        tag = re.sub(r'\b(href|src|srcset|data-pool-src)=(")([^"]*)"', fix_attr, tag)
        tag = re.sub(r"url\('([^']+)'\)", lambda u: f"url('{fix_url(u.group(1))}')", tag)
        return tag

    return re.sub(r"<(?:a|img|source|link|script|figure|div|ol|article|span)\b[^>]*>", fix_tag, fragment)


# ---------------------------------------------------------------- the pages' bodies
FOOTER = src(blocks["footer"])
SKIP = '<a class="skip-link" href="#main">Skip to content</a>' if "skip" in blocks else ""


def pager(i: int, rel: str) -> str:
    prev_q = questions[i - 1] if i > 0 else None
    next_q = questions[i + 1] if i + 1 < len(questions) else None
    parts = []
    parts.append(f'<a class="qpager-prev" href="{rel}q/{prev_q["slug"]}/"><span class="qpager-dir">← Previous</span> {_html.escape(prev_q["title"])}</a>' if prev_q else '<span class="qpager-prev"></span>')
    home = rel or "./"
    parts.append(f'<a class="qpager-home" href="{home}">Back to the summary</a>')
    parts.append(f'<a class="qpager-next" href="{rel}q/{next_q["slug"]}/"><span class="qpager-dir">Next →</span> {_html.escape(next_q["title"])}</a>' if next_q else '<span class="qpager-next"></span>')
    return '<nav class="qpager container" aria-label="Questions">\n  ' + "\n  ".join(parts) + "\n</nav>"


# question pages
for i, q in enumerate(questions):
    path = f'q/{q["slug"]}/'
    frag = []
    frag.append(f'<div class="qpage-head container"><p class="qpage-crumb"><a href="./">Summary</a> · Question {i + 1} of {len(questions)}</p></div>')
    if q["sid"] in acts:
        frag.append(acts[q["sid"]])
    frag.append(src(blocks[q["sid"]]))
    if q["folds"]:
        folds = "\n".join(re.sub(r'^(\s*)<details class="fold">', r'\1<details class="fold" open>', FOLDS[f], count=1) for f in q["folds"])
        frag.append(f'<section class="explore qpage-evidence">\n  <div class="container">\n    {EXPLORE_H2 or ""}\n    {folds}\n  </div>\n</section>')
    if q["slug"] == "cards":
        frag.append(CARDS_MORE)
    frag.append(pager(i, ""))  # rewrite() adds the page depth
    PAGES[path] = frag

# this autumn
if HAS_AUTUMN:
    PAGES["this-autumn/"] = ['<div class="qpage-head container"><p class="qpage-crumb"><a href="./">Summary</a></p></div>', src(blocks["autumn"])]

# methodology
meth = []
if METHOD_TOC:
    items = re.search(r"<summary>(.*?)</summary>\s*(<ol>.*</ol>)", METHOD_TOC, re.S)
    meth.append('<nav class="toc-sticky" aria-label="Report contents" id="toc">\n'
                + re.search(r'<button type="button" class="toc-toggle".*?</button>', src(blocks["toc"]), re.S).group(0)
                + f'\n  <p class="toc-heading">Contents</p><ol>\n    <li>{items.group(1)}\n      {items.group(2)}\n    </li>\n  </ol>\n</nav>')
if "chapter" in blocks:
    meth.append(src(blocks["chapter"]))
meth.append(src(blocks["methodology"]))
dl = [FOLDS[f] for f in METHOD_FOLDS if f in FOLDS]
if dl:
    meth.append('<section class="explore">\n  <div class="container">\n    ' + "\n".join(dl) + "\n  </div>\n</section>")
PAGES["methodology/"] = meth

# the front page
front = [src(blocks["masthead"]), src(blocks["hero"])]
if "contribution" in blocks:
    front.append(src(blocks["contribution"]))
if HAS_AUTUMN:
    au = src(blocks["autumn"])
    asof = re.search(r'<p class="autumn-asof">.*?</p>', au, re.S)
    lede = re.search(r'<p class="autumn-lede">.*?</p>', au, re.S)
    h2 = plain(re.search(r"<h2[^>]*>(.*?)</h2>", au, re.S).group(1))
    front.append('<section class="autumn-teaser" id="autumn-teaser">\n  <div class="container">\n'
                 f'    <p class="close-kicker">{h2}</p>\n    {asof.group(0) if asof else ""}\n    {lede.group(0) if lede else ""}\n'
                 f'    <p class="pool-link"><a href="this-autumn/">Read this autumn →</a></p>\n  </div>\n</section>')
if "take" in blocks:
    t = src(blocks["take"])
    items = re.findall(r'<div class="nx-take"><p class="nx-take-n">(\d+)</p><div>(<p class="nx-take-head">.*?</p>)((?:<p class="nx-take-body">.*?</p>)*)</div></div>', t, re.S)
    if len(items) != t.count('class="nx-take"'):
        sys.exit("split_pages: could not read every finding")
    slugs = {q["slug"] for q in questions}
    lis = []
    for k, (num, head_p, bodies) in enumerate(items):
        paras = re.findall(r'<p class="nx-take-body">.*?</p>', bodies, re.S)
        first = paras[0] if paras else ""
        # the supporting number: the first figure of the first body paragraph, set bold in place
        first = (re.sub(r'(?<![\d/])(×\d+(?:\.\d+)?|\d+(?:\.\d+)?\s?%|\d+\.\d+)(?![\d/])', r'<strong class="finding-num">\1</strong>', first, count=1)
                 if first else first)
        more = ""
        if len(paras) > 1:
            more = '<details class="fold finding-more"><summary>More on this</summary>' + "".join(paras[1:]) + "</details>"
        dest = TAKE_TO[k] if k < len(TAKE_TO) and TAKE_TO[k] in slugs else questions[0]["slug"]
        lis.append(f'<li class="finding"><p class="finding-n">{num}</p><div>{head_p}{first}{more}'
                   f'<p class="finding-link"><a href="q/{dest}/">Read the evidence →</a></p></div></li>')
    kicker = re.search(r'<p class="close-kicker">.*?</p>', t, re.S).group(0)
    line = re.search(r'<p class="close-line take-line">.*?</p>', t, re.S)
    # `for-federation`: the retired block's anchor lands on the findings (old links keep working)
    front.append('<section class="take" id="take">\n  <span id="for-federation"></span>\n  <div class="container">\n    ' + kicker
                 + '\n    <ol class="findings">\n      ' + "\n      ".join(lis) + "\n    </ol>\n    "
                 + (line.group(0) if line else "") + "\n  </div>\n</section>")
if "colophon" in blocks:
    front.append(src(blocks["colophon"]))
if "quickread" in blocks:
    front.append(src(blocks["quickread"]))
qlist = "\n".join(f'      <li><a href="q/{q["slug"]}/">{_html.escape(q["title"])}</a></li>' for q in questions)
front.append('<section class="front-index" id="questions">\n  <div class="container">\n    <p class="close-kicker">Every question</p>\n'
             f'    <ol class="front-q">\n{qlist}\n    </ol>\n    <p class="front-more">'
             + ('<a href="this-autumn/">This autumn</a> · ' if HAS_AUTUMN else "")
             + '<a href="methodology/">Methodology</a> · <a href="players/">Players</a></p>\n  </div>\n</section>')
for k in ("brief", "citelog", "close"):
    if k in blocks:
        front.append(src(blocks[k]))
PAGES[""] = front

# every id of the old page -> its new page
WHERE: dict[str, str] = {}
for path, frags in PAGES.items():
    for f in frags:
        for i_ in ids(f):
            WHERE.setdefault(i_, path)
old_ids = set(ids(TEXT[body.start:body.end]))
for f in DROPPED_FOLDS:
    for i_ in ids(FOLDS[f]):
        WHERE.setdefault(i_, "players/")
for i_ in old_ids - set(WHERE):
    WHERE[i_] = ""          # nav-only ids (toc, skip link) land on the front page
# the old contents' own ids (the toc) are not content
for gone in ("toc",):
    WHERE.pop(gone, None)


# ---------------------------------------------------------------- head per page
def head_for(path: str, rel: str, title: str, desc: str | None) -> str:
    h = HEAD
    h = re.sub(r'(<(?:link|script)\b[^>]*\b(?:href|src)=")(?![a-z]+:|/|#)([^"]+)"', lambda m: f'{m.group(1)}{rel}{m.group(2)}"', h)
    h = re.sub(r"<title>.*?</title>", f"<title>{_html.escape(title)}</title>", h, count=1, flags=re.S)
    if desc:
        h = re.sub(r'<meta name="description" content="[^"]*">', f'<meta name="description" content="{_html.escape(desc, quote=True)}">', h, count=1)
    url = SITE + ED_ROOT.lstrip("/") + path
    h = re.sub(r'\s*<link rel="alternate" hreflang="[^"]*" href="[^"]*">', "", h)
    h = re.sub(r'\s*<link rel="canonical" href="[^"]*">', "", h)
    h = h.replace('<meta name="viewport"', f'<link rel="canonical" href="{url}">\n  {MARK}\n  <meta name="viewport"', 1)
    return h


def redirect_js() -> str:
    pages = sorted({p for p in WHERE.values()})
    idx = {p: n for n, p in enumerate(pages)}
    table = {i_: idx[p] for i_, p in sorted(WHERE.items()) if p}
    return ("<script>\n  // the report used to be one page: an old #anchor that now lives on its own page goes there\n"
            "  (() => {\n"
            f"    const P = {json.dumps(pages)}, M = {json.dumps(table, ensure_ascii=False, separators=(',', ':'))};\n"
            "    const go = () => {\n      const h = decodeURIComponent(location.hash.slice(1));\n"
            "      if (h && h in M && !document.getElementById(h)) location.replace(P[M[h]] + location.search + location.hash);\n    };\n"
            "    go();\n    addEventListener('hashchange', go);\n  })();\n</script>")


def write(path: str, frags: list[str], title: str, current: str, desc: str | None = None, switch_path: str | None = None):
    rel = "../" * path.count("/")
    body_html = "\n\n".join(rewrite(f, rel, path, WHERE) for f in frags)
    head_html = head_for(path, rel, title, desc)
    if path == "":   # after the charset, which must sit in the first 1024 bytes
        head_html = head_html.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n  ' + redirect_js().replace("\n", "\n  "), 1)
    out = (f"<!DOCTYPE html>\n{HTML_OPEN}\n<head>{head_html}</head>\n{BODY_OPEN}\n"
           f"{topbar_html(rel, current, path if switch_path is None else switch_path, toc=current == 'methodology' and bool(METHOD_TOC))}\n\n{SKIP}\n\n"
           f'<main id="main" class="page page-{(current.split("/")[0] or "summary")}">\n{body_html}\n</main>\n\n'
           f"{rewrite(FOOTER, rel, path, WHERE)}\n\n" + "\n\n".join(scripts) + f"\n\n{NAV_JS}\n</body>\n</html>\n")
    dest = D / path / "index.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(out, encoding="utf-8")
    return dest


written = []
for q in questions:
    a = re.search(r'<p class="slide-a">(.*?)</p>', src(blocks[q["sid"]]), re.S)
    written.append(write(f'q/{q["slug"]}/', PAGES[f'q/{q["slug"]}/'], f'{q["title"]} · {TITLE}', f'q/{q["slug"]}',
                         desc=plain(a.group(1)) if a else None))
if HAS_AUTUMN:
    written.append(write("this-autumn/", PAGES["this-autumn/"], f"This autumn · {TITLE}", "this-autumn", switch_path=""))
written.append(write("methodology/", PAGES["methodology/"], f"Methodology · {TITLE}", "methodology"))
written.append(write("", PAGES[""], TITLE, "summary"))

# a stale question page from an earlier build whose question is gone
for old in (D / "q").glob("*/index.html"):
    if old.parent.name not in {q["slug"] for q in questions}:
        old.unlink()
        old.parent.rmdir()

# ---------------------------------------------------------------- players/: the atlas page's top bar, and atlas/ forwarding to it
players = D / "players" / "index.html"
if players.exists():
    p = players.read_text(encoding="utf-8")
    p, n_bar = re.subn(r'<nav class="topbar".*?</nav>', lambda m: topbar_html("../", "players", "players/"), p, count=1, flags=re.S)
    if n_bar != 1:
        sys.exit("split_pages: players/index.html has no top bar")
    p = re.sub(r'<link rel="canonical" href="[^"]*">', f'<link rel="canonical" href="{SITE}{ED_ROOT.lstrip("/")}players/">', p, count=1)
    # its links into the old one-page report go to the page that now holds the anchor
    p = re.sub(r'href="\.\./#([^"]+)"', lambda m: f'href="../{WHERE.get(m.group(1), "")}#{m.group(1)}"', p)
    if NAV_JS not in p:
        p = p.replace("</body>", NAV_JS + "\n</body>", 1)
    players.write_text(p, encoding="utf-8")
    atlas = D / "atlas" / "index.html"
    atlas.parent.mkdir(parents=True, exist_ok=True)
    atlas.write_text(f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Players</title>
  <link rel="canonical" href="{SITE}{ED_ROOT.lstrip("/")}players/">
  <meta http-equiv="refresh" content="0; url=../players/">
  <script>location.replace('../players/' + location.search + location.hash);</script>
</head>
<body><p><a href="../players/">Players</a></p></body>
</html>
''', encoding="utf-8")
    written.append(players)

# the pool list is a sidecar the cards page fetches; its career links now go to players/
rows = D / "pool_rows.html"
if rows.exists():
    r = rows.read_text(encoding="utf-8")
    rows.write_text(r.replace('href="atlas/', f'href="{ED_ROOT}players/'), encoding="utf-8")

# the cross-nation page (root site only) gets the same top bar
nations = D / "nations" / "index.html"
if nations.exists():
    nx = nations.read_text(encoding="utf-8")
    nx, n_bar = re.subn(r'<nav class="topbar".*?</nav>', lambda m: topbar_html("../", "nations", ""), nx, count=1, flags=re.S)
    if n_bar == 1:
        if NAV_JS not in nx:
            nx = nx.replace("</body>", NAV_JS + "\n</body>", 1)
        nations.write_text(nx, encoding="utf-8")

print(f"split {index}: {len(questions)} questions, {len(written)} pages, {len(WHERE)} anchors mapped")
