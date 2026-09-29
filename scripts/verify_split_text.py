"""Content freeze check for the page split (site/split_pages.py): the visible
text of the old one-page report (plus its player atlas page) against the
union of the visible text of every page the split writes.

Text is compared block by block -- the text of each block-level element
(p, li, h1-h6, td, th, summary, figcaption, ...), inline markup flattened,
whitespace collapsed -- so a sentence that moved to another page, or got a
<strong> around one of its numbers, still counts as the same sentence.

  lost   = old blocks found on no new page         (must be only old nav labels)
  added  = new blocks that were not in the old page (must be only nav labels)

usage: verify_split_text.py <old dir> <new dir>
  old dir: holds the old index.html and atlas/index.html
  new dir: the split site (index.html, q/*/, this-autumn/, methodology/, players/)
exits 1 when anything outside the allowed labels was lost or added.
"""

from __future__ import annotations

import html
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

BLOCK = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th", "dt", "dd", "summary", "figcaption",
         "caption", "label", "button", "option", "blockquote", "pre", "div", "section", "header", "footer",
         "nav", "main", "aside", "article", "figure", "details", "ul", "ol", "dl", "table", "tr", "thead",
         "tbody", "body", "select", "text", "title"}
SKIP = {"script", "style", "noscript", "head"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

# navigation the split adds, and the old one-page navigation it replaces
NAV_NEW = {"Menu", "Questions", "Summary", "This autumn", "Methodology", "Players", "Nations", "Contents",
           "Every question", "Read the evidence →", "Read this autumn →", "More on this", "Back to the summary",
           "Previous", "Next", "← Previous", "Next →", "This autumn · Methodology · Players", "Methodology · Players",
           "Skip to content"}
NAV_OLD = {"Pathways", "Cards", "Contents", "Explore the data"}


class Blocks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[list[str]] = [[]]
        self.skip = 0
        self.out: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in SKIP:
            self.skip += 1
        elif tag in BLOCK and tag not in VOID:
            self.stack.append([])

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if tag in SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in BLOCK and len(self.stack) > 1:
            self._flush(self.stack.pop())

    def handle_data(self, data):
        if not self.skip:
            self.stack[-1].append(data)

    def _flush(self, parts):
        t = re.sub(r"\s+", " ", "".join(parts)).strip()
        if t:
            self.out.append(t)

    def close(self):
        super().close()
        while self.stack:
            self._flush(self.stack.pop())


def blocks(path: Path) -> set[str]:
    p = Blocks()
    p.feed(path.read_text(encoding="utf-8"))
    p.close()
    return set(p.out)


def pages(d: Path, split: bool) -> list[Path]:
    if not split:
        return [d / "index.html", d / "atlas" / "index.html"]
    out = [d / "index.html", d / "methodology" / "index.html", d / "players" / "index.html"]
    out += sorted((d / "q").glob("*/index.html"))
    if (d / "this-autumn" / "index.html").exists():
        out.append(d / "this-autumn" / "index.html")
    return out


def main(old_dir: Path, new_dir: Path) -> int:
    old = set().union(*(blocks(p) for p in pages(old_dir, False)))
    new_pages = pages(new_dir, True)
    new = set().union(*(blocks(p) for p in new_pages))
    lost = sorted(old - new)
    added = sorted(new - old)
    # a question page's pager and crumb carry the question titles as labels
    q_titles = {html.unescape(m) for p in new_pages for m in re.findall(r'<h2 class="slide-q">(.*?)</h2>', p.read_text(encoding="utf-8"))}

    def only_labels(t: str, labels: set[str]) -> bool:
        for lab in sorted(labels, key=len, reverse=True):
            t = t.replace(lab, " ")
        return not t.replace("·", " ").strip()

    def is_nav(t: str) -> bool:
        if t in NAV_NEW or only_labels(t, NAV_NEW):
            return True
        if re.fullmatch(r"Summary · Question \d+ of \d+", t):
            return True
        titles = q_titles | {"Why the train left"}
        pager = re.fullmatch(r"(?:← Previous (.+?) )?Back to the summary(?: Next → (.+))?", t)
        if pager and all(g is None or g in titles for g in pager.groups()):
            return True
        if re.fullmatch(r"[A-Z]{3}(?: · [A-Z]{3})*", t):   # the edition switch
            return True
        return False

    bad_added = [t for t in added if not is_nav(t)]
    bad_lost = [t for t in lost if not only_labels(t, NAV_OLD | NAV_NEW)]
    print(f"old: {len(old)} text blocks on {len(pages(old_dir, False))} pages; new: {len(new)} on {len(new_pages)} pages")
    print(f"lost: {len(lost)} ({len(bad_lost)} outside the old navigation); added: {len(added)} ({len(bad_added)} outside the new navigation)")
    for t in lost:
        print(("  LOST  " if t in bad_lost else "  lost (old nav)  ") + t[:160])
    for t in added:
        print(("  ADDED " if t in bad_added else "  added (nav)  ") + t[:160])
    return 1 if bad_added or bad_lost else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
