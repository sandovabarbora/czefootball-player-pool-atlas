"""Harvard-style reference list: `config/refs.yaml` in, formatted citations
out (Task 15).

`config/refs.yaml` is a flat list of entries (see its own header comment for
the field shapes: journal article by default, `type: book` or `type:
report` for the other two shapes this report cites). Every entry was
verified before being added -- its `doi` resolves (`curl -sI
https://doi.org/<doi>` -> 30x) or its `url` does (-> 200); nothing here was
invented. `format_harvard` renders one entry as a reference-list line;
`in_text` renders the same entry as an author-date parenthetical
("(Efron and Morris, 1975)") for use next to the sentence describing that
method.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src import config

_EN_DASH = "–"


def load_refs(path: Path | None = None) -> list[dict[str, Any]]:
    """Load `config/refs.yaml` (a list of reference dicts)."""
    path = path or (config.CONFIG_DIR / "refs.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return list(data)


def refs_by_key(refs: list[dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    """`{key: entry}`, for template lookups by citation key."""
    refs = refs if refs is not None else load_refs()
    return {r["key"]: r for r in refs}


def _format_authors(authors: list[str], et_al: bool = False) -> str:
    """'A' | 'A and B' | 'A, B and C' | 'A et al.' (Harvard's comma-joined,
    "and"-before-last list; `et_al` forces the truncated form for a source
    with more authors than are worth spelling out)."""
    if et_al:
        return f"{authors[0]} et al."
    if len(authors) == 1:
        return authors[0]
    return ", ".join(authors[:-1]) + " and " + authors[-1]


def _format_vol_issue(volume: Any, issue: Any) -> str | None:
    if volume is None:
        return None
    return f"{volume}({issue})" if issue else f"{volume}"


def _format_pages(pages: Any) -> str | None:
    """A hyphenated range ("311-319") renders as "pp. 311-319" (en dash); a
    single article id ("1143", "e1516") renders bare, no "pp." prefix."""
    if pages is None:
        return None
    s = str(pages)
    if "-" in s:
        lo, hi = s.split("-", 1)
        return f"pp. {lo}{_EN_DASH}{hi}"
    return s


def format_harvard(ref: dict[str, Any]) -> str:
    """One Harvard-style reference-list line for `ref` (an entry from
    `load_refs()`, or an equivalently-shaped hand-built dict in tests)."""
    authors = _format_authors(ref["authors"], ref.get("et_al", False))
    year, title = ref["year"], ref["title"]
    rtype = ref.get("type", "article")

    if rtype == "book":
        parts = f"{authors} ({year}) {title}."
        if ref.get("edition"):
            parts += f" {ref['edition']} edn."
        if ref.get("place") and ref.get("publisher"):
            parts += f" {ref['place']}: {ref['publisher']}."
        return parts

    if rtype == "report":
        parts = f"{authors} ({year}) {title}."
        if ref.get("series"):
            number = f", {ref['number']}" if ref.get("number") else ""
            parts += f" {ref['series']}{number}."
        if ref.get("url"):
            accessed = f" (Accessed: {ref['accessed']})" if ref.get("accessed") else ""
            parts += f" Available at: {ref['url']}{accessed}."
        return parts

    # article (default)
    parts = f"{authors} ({year}) '{title}', {ref['container']}"
    vol_issue = _format_vol_issue(ref.get("volume"), ref.get("issue"))
    if vol_issue:
        parts += f", {vol_issue}"
    pages = _format_pages(ref.get("pages"))
    if pages:
        parts += f", {pages}"
    return parts + "."


def in_text_multi(refs: list[dict[str, Any]]) -> str:
    """One parenthesis for several sources: "(Kharrat, McHale and Peña, 2020; Hvattum, 2019)"."""
    return "(" + "; ".join(in_text(r)[1:-1] for r in refs) + ")"


def in_text(ref: dict[str, Any]) -> str:
    """Author-date parenthetical, e.g. "(Efron and Morris, 1975)" or
    "(Abril-Pla et al., 2023)" for a source with more than three authors or
    `et_al: true`."""
    surnames = [a.split(",")[0].strip() for a in ref["authors"]]
    year = ref["year"]
    if ref.get("et_al") or len(surnames) > 3:
        return f"({surnames[0]} et al., {year})"
    if len(surnames) == 1:
        return f"({surnames[0]}, {year})"
    if len(surnames) == 2:
        return f"({surnames[0]} and {surnames[1]}, {year})"
    return f"({', '.join(surnames[:-1])} and {surnames[-1]}, {year})"


def link_target(ref: dict[str, Any]) -> str:
    """The URL a reference-list entry's title should link to: the DOI's
    canonical resolver if there is one, else the entry's own `url`."""
    if ref.get("doi"):
        return f"https://doi.org/{ref['doi']}"
    return ref.get("url", "")


def harvard_list(refs: list[dict[str, Any]] | None = None) -> list[dict[str, str]]:
    """Alphabetical (by first author's surname) reference list, each entry
    `{key, citation, href}` for the template's `#references` section."""
    refs = refs if refs is not None else load_refs()
    ordered = sorted(refs, key=lambda r: r["authors"][0].split(",")[0].strip().lower())
    return [{"key": r["key"], "citation": format_harvard(r), "href": link_target(r)} for r in ordered]
