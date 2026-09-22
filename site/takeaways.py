"""The "what to take from it" block, rendered once from outputs/nations/
nations.json (src.nations_compare.takeaways) for a home nation -- used by
the report's site layer (enrich_index.py) and the nations page
(build_nations.py), so both carry the same statements as static HTML."""

from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIONS_JSON = ROOT / "outputs" / "nations" / "nations.json"


def load(home_code: str) -> list[dict]:
    if not NATIONS_JSON.exists():
        return []
    data = json.loads(NATIONS_JSON.read_text(encoding="utf-8"))
    return (data.get("takeaways") or {}).get(home_code, [])


def render(items: list[dict]) -> str:
    return "".join(
        f'<div class="nx-take"><p class="nx-take-n">{i + 1}</p><div>'
        f'<p class="nx-take-head">{html.escape(it["head"])}</p>'
        + "".join(f'<p class="nx-take-body">{html.escape(p.strip())}</p>' for p in it["body"].split("\n\n") if p.strip()) + '</div></div>'
        for i, it in enumerate(items))
