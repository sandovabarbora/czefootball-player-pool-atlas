"""Template render tests.

The template renders offline from a small hand-written fixture context (no
parquet, no network). A second test renders the real context when
data/processed/ is present (skipped otherwise) so the two context shapes
cannot drift apart unnoticed.
"""

from __future__ import annotations

import re

import pytest
from jinja2 import Environment, FileSystemLoader

from src import config
from src.render import GROUPS, build_context, build_context_from_fixtures, load_data

SECTION_IDS = (
    "summary", "benchmark", "observations", "clusters", "trajectories", "pathways",
    "cards", "analogs", "methodology", "multipliers", "shrinkage", "pca-loadings",
    "sensitivity", "limitations", "reproducibility", "photo-credits",
)


def _render(ctx: dict) -> str:
    env = Environment(loader=FileSystemLoader(str(config.TEMPLATES_DIR)), autoescape=False)
    return env.get_template("report.html.j2").render(**ctx)


def _check(html: str, groups: list[str]) -> None:
    assert '<html lang="en">' in html
    assert 'class="hero-num-figure"' in html and "*" in html
    for cls in ("capita-row", "cohort-table", "cluster-list", "cycle-card", "analog-block", "limitations"):
        assert f'class="{cls}' in html, cls
    for sid in SECTION_IDS:
        assert f'id="{sid}"' in html, sid
    assert 'data-atlas="heatmap"' in html
    for grp in groups:
        assert f'data-atlas="{grp.lower()}"' in html, grp
        assert f'data-atlas-clusters="{grp.lower()}"' in html, grp
    assert "data-tex=" in html
    assert 'data-fbref-id="' in html and 'data-player-key="' in html
    # nothing leaked from the template engine, no None/nan in visible text
    assert "{{" not in html and "{%" not in html
    no_tex = re.sub(r'data-tex="[^"]*"', "", html)  # KaTeX sources legitimately contain "}}"
    assert "}}" not in no_tex
    text = re.sub(r"<[^>]+>", " ", html)
    assert not re.search(r"\bNone\b", text)
    assert "nan" not in text.split()


def test_template_renders_with_fixture_context():
    ctx = build_context_from_fixtures()
    html = _render(ctx)
    _check(html, ctx["groups"])


@pytest.mark.skipif(not (config.PROCESSED_DIR / "per_capita.parquet").exists(),
                    reason="data/processed not present")
def test_template_renders_with_real_context():
    ctx = build_context(load_data())
    html = _render(ctx)
    _check(html, GROUPS)
    assert len(ctx["cards"]) == 6
    assert len(ctx["per_capita"]) == 9
