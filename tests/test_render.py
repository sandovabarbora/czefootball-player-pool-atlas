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
from src.render import (
    GROUPS,
    _build_observations,
    build_context,
    build_context_from_fixtures,
    load_data,
)

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


def test_observations_derive_counts_and_titles_from_context():
    ctx = build_context_from_fixtures()
    obs = ctx["observations"]
    # two countries in the fixture -> "other one peer"; one headline league -> "one strongest"
    assert "median of the other one peer," in obs[1]["body"]
    assert "rosters of the one strongest leagues" in obs[0]["body"]
    assert "rank 2 of 2" in obs[0]["body"]
    # Denmark (5.96 M) sits above Czechia (10.9 M): a smaller population
    assert "population 1.8 times smaller" in obs[0]["body"]
    # a larger country above Czechia (Poland-like) reads "larger", not "smaller"
    big = [{"country": "POL", "name": "Poland", "n_players": 32, "population_m": 36.62,
            "per_million": 0.87, "rank": 1}, dict(ctx["per_capita"][1], rank=2)]
    hero = dict(ctx["hero"], top=big[0])
    poland_above = _build_observations(hero, big, ctx["cohort_gaps"], ctx["movers"] | {
        "MF": ctx["movers"]["FW"], "DF": ctx["movers"]["FW"]}, ctx["thresholds"], ctx["seasons"], 9)
    assert "population 3.4 times larger" in poland_above[0]["body"]
    # fixture movers: 1 up, 0 stable in every group -> stable share 0 -> "mixed"
    assert obs[2]["title"].endswith(": mixed")
    assert "0 of 3 stayed within that band" in obs[2]["body"]
    # flip: make every group's players stable -> "mostly stable"
    stable = {g: {"up": [], "down": [], "n_czech": 4,
                  "directions": {"improving": 1, "stable": 3, "declining": 0}} for g in GROUPS}
    flipped = _build_observations(ctx["hero"], ctx["per_capita"], ctx["cohort_gaps"], stable,
                                  ctx["thresholds"], ctx["seasons"], n_headline=9)
    assert flipped[2]["title"].endswith(": mostly stable")
    assert "9 of 12 stayed within that band" in flipped[2]["body"]
    assert "rosters of the nine strongest leagues" in flipped[0]["body"]


@pytest.mark.skipif(not (config.PROCESSED_DIR / "per_capita.parquet").exists(),
                    reason="data/processed not present")
def test_template_renders_with_real_context():
    ctx = build_context(load_data())
    html = _render(ctx)
    _check(html, GROUPS)
    assert len(ctx["cards"]) == 9
    assert len(ctx["per_capita"]) == 9
