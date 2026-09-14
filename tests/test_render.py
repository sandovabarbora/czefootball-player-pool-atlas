"""Template render tests.

The template renders offline from a small hand-written fixture context (no
parquet, no network). A second test renders the real context when
data/processed/ is present (skipped otherwise) so the two context shapes
cannot drift apart unnoticed.
"""

from __future__ import annotations

import re

import pandas as pd
import pytest
from jinja2 import Environment, FileSystemLoader

from src import config
from src.utils import season_label
from src.render import (
    GROUPS,
    RULE_KICKERS,
    _build_findings,
    _build_observations,
    _current_club,
    build_context,
    build_context_from_fixtures,
    load_data,
    render_html,
)

SECTION_IDS = (
    "summary", "findings", "benchmark", "observations", "clusters", "trajectories", "pathways",
    "cards", "analogs", "methodology", "multipliers", "shrinkage", "pca-loadings",
    "sensitivity", "data-quality", "limitations", "how-built", "reproducibility", "photo-credits",
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
    # KaTeX sources and the figures' cluster-name JSON legitimately contain "}}"
    no_tex = re.sub(r'data-tex="[^"]*"|data-cluster-names=\'[^\']*\'', "", html)
    assert "}}" not in no_tex
    text = re.sub(r"<[^>]+>", " ", html)
    assert not re.search(r"\bNone\b", text)
    assert "nan" not in text.split()


def test_template_renders_with_fixture_context():
    ctx = build_context_from_fixtures()
    html = _render(ctx)
    _check(html, ctx["groups"])
    assert "Exhibit E" in html and 'class="cycle-row-kicker"' in html
    # the template tolerates a pathways.json without `destinations`
    ctx["pathways"]["destinations"] = None
    assert "Exhibit E" not in _render(ctx)


def test_exhibit_e_with_empty_buckets_renders_sentence_without_bars():
    ctx = build_context_from_fixtures()
    ctx["pathways"]["destinations"] = {"n_total": 12, "n_abroad": 0, "buckets": [],
                                       "sideways_share": 0.0, "sideways_definition": "n/a"}
    html = _render(ctx)
    assert "Exhibit E" in html
    assert "Of the 12 mapped Czech players, 0 play outside" in html
    assert 'aria-label="Czech players abroad by destination bucket"' not in html
    assert "sideways" not in html.split("Exhibit E")[1].split("</section>")[0]


def _current_rows(*rows: tuple[str, str, str, int]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["player_key", "team", "league", "min"])
    df["season"] = "2025-2026"
    # same dedupe as render: row with most minutes per player
    return df.sort_values("min", ascending=False).drop_duplicates("player_key").set_index("player_key")


def test_current_club_prefers_the_row_with_more_minutes():
    cur = _current_rows(("p|2000", "Karviná", "CZE-First League", 300),
                        ("p|2000", "Viktoria Plzeň", "CZE-First League", 900))
    club, league, source, label = _current_club("p|2000", cur, None, "2025/26")
    assert (club, league, source, label) == ("Viktoria Plzeň", "CZE-First League", "tables", "2025/26")


def test_current_club_uses_raw_table_rows_under_the_minutes_floor():
    # Early-season rows have few minutes; a 100-minute current-season row must
    # still beat the country-page fallback (the features frames would have
    # dropped it at the 450-minute inclusion floor).
    cur = _current_rows(("p|2000", "Leverkusen", "GER-Bundesliga", 100))
    pool_row = pd.Series({"club_current": "Sparta Prague", "fbref_id": "abc"})
    assert _current_club("p|2000", cur, pool_row, "2025/26") == (
        "Leverkusen", "GER-Bundesliga", "tables", "2025/26")


def test_build_cards_reads_current_club_from_raw_table_not_features():
    from src.render import _build_cards
    season, current = "2024-2025", "2025-2026"
    feat = pd.DataFrame([{
        "player_key": "p|2000", "player": "P", "season": season, "league": "CZE-First League",
        "team": "Karviná", "born": 2000, "age": 24, "min": 1800, "min_share": 0.6, "npg": 5, "ast": 2,
        "npg_p90": 0.25, "ast_p90": 0.1, "npg_p90_quality": 0.11, "ast_p90_quality": 0.04,
        "nt_flag": False, "nt_events": "", "czech_eligible": True,
    }])
    coords = pd.DataFrame([{"player_key": "p|2000", "season": season, "min": 1800,
                            "cluster_style": "C0", "cluster_quality": "C0"}])
    raw = pd.DataFrame([{"player_key": "p|2000", "player": "P", "season": current,
                         "league": "GER-Bundesliga", "team": "Leverkusen", "min": 120}])
    pool = pd.DataFrame([{"player_key": "p|2000", "fbref_id": "abc", "club_current": "Sparta Prague"}])
    showcase = [{"player_key": "p|2000", "player": "P", "pos_group": "FW", "reason": "highest quality-adjusted"}]
    cards = _build_cards(showcase, {}, {"FW": feat}, {"FW": coords}, {"FW": pd.DataFrame()}, pool,
                         {}, {}, season, current, current_table=raw)
    assert cards[0]["club"] == "Leverkusen" and cards[0]["club_label"] == "2025/26"
    # without the raw table the features frame has no 2025/26 row -> fallback
    cards = _build_cards(showcase, {}, {"FW": feat}, {"FW": coords}, {"FW": pd.DataFrame()}, pool,
                         {}, {}, season, current)
    assert cards[0]["club"] == "Sparta Prague" and cards[0]["club_label"] == "latest known"


def test_current_club_falls_back_to_pool_and_is_labelled_latest_known():
    cur = _current_rows(("other|1999", "Slavia Prague", "CZE-First League", 500))
    pool_row = pd.Series({"club_current": "Bohemians 1905", "fbref_id": "abc"})
    club, league, source, label = _current_club("p|2000", cur, pool_row, "2025/26")
    assert (club, league, source, label) == ("Bohemians 1905", "", "country page", "latest known")
    # no pool club either -> empty club, still labelled as a fallback
    assert _current_club("p|2000", cur, None, "2025/26") == ("", "", "country page", "latest known")
    # the label reaches the meta line: fixture card switched to the fallback case
    ctx = build_context_from_fixtures()
    ctx["cards"][0].update(club="Bohemians 1905", club_label="latest known")
    html = _render(ctx)
    assert "Bohemians 1905 (latest known)" in html and "Bohemians 1905 (2025/26)" not in html


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


def test_findings_are_five_and_each_ends_with_asterisk():
    ctx = build_context_from_fixtures("en")
    assert len(ctx["findings"]) == 5
    assert all(f["text"].endswith("*") and f["foot"] for f in ctx["findings"])
    html = _render(ctx)
    # Task 11: the method note fold is gone; its content is the mono line
    # under the "For a federation" tiles, right after the argument list.
    assert 'class="findings"' in html
    assert 'class="for-federation"' in html and "Run for England" in html


def test_findings_have_a_figure_field_for_the_tile_headline():
    ctx = build_context_from_fixtures("en")
    assert all(f.get("figure") for f in ctx["findings"])


def test_hero_shows_its_numbers_once_not_in_tiles_and_a_meta_strip_too():
    """Task 10: hero.tiles/hero.meta are gone; the argument list carries those
    numbers instead, and every chapter-opening framing paragraph gets the
    two-line lede treatment."""
    ctx = build_context_from_fixtures("en")
    html = _render(ctx)
    assert 'class="hero-tiles"' not in html and 'class="hero-meta"' not in html
    assert 'class="argument"' in html
    assert html.count('class="framing lede"') == 3
    assert 'class="cards-more"' not in html


def test_findings_have_an_anchor_into_the_exhibit_they_source():
    ctx = build_context_from_fixtures("en")
    html = _render(ctx)
    assert all(f.get("anchor", "").startswith("#") for f in ctx["findings"])
    # every anchor lands on an id that actually exists in the page
    ids = set(re.findall(r'id="([^"]+)"', html))
    assert all(f["anchor"][1:] in ids for f in ctx["findings"])


def test_card_rows_merge_the_national_team_core_rules_into_one_row():
    from src.render import _card_rows

    def card(reason: str, key: str) -> dict:
        return {"player_key": key, "reason": reason}

    cards = [
        card("highest quality-adjusted npG+A per 90 among FW", "a"),
        card("most top-9 minutes among 2026 FIFA World Cup squad FW", "b"),
        card("most domestic minutes among 2026 FIFA World Cup squad FW", "c"),
        card("youngest national-team call-up among FW", "d"),
    ]
    rows = _card_rows(cards, nt_core_event="2026 FIFA World Cup")
    assert [c["player_key"] for c in rows[0]["cards"]] == ["a"]
    # merged row: top-9 trio then home trio, one kicker
    assert [c["player_key"] for c in rows[1]["cards"]] == ["b", "c"]
    assert rows[1]["kicker"].startswith("National-team core")
    assert [c["player_key"] for c in rows[2]["cards"]] == ["d"]


def test_toc_drops_findings_data_quality_how_built_but_ids_remain():
    ctx = build_context_from_fixtures("en")
    html = _render(ctx)
    toc_sticky = html.split('<nav class="toc-sticky"')[1].split("</nav>")[0]
    toc_mobile = html.split('<details class="toc-mobile"')[1].split("</details>")[0]
    for frag in (toc_sticky, toc_mobile):
        assert 'href="#findings"' not in frag
        assert 'href="#data-quality"' not in frag
        assert 'href="#how-built"' not in frag
    assert 'id="findings"' in html and 'id="data-quality"' in html and 'id="how-built"' in html


def test_findings_use_squad_lens_when_present_and_fall_back_otherwise():
    ctx = build_context_from_fixtures("en")
    squad_text = ctx["findings"][4]["text"]
    assert "top-9" in squad_text or "top9" in squad_text.lower()
    # empty squad_lens -> the fifth finding falls back to the exhibit E sideways share
    no_lens = _build_findings(ctx["hero"], ctx["cohort_gaps"], ctx["pathways"], {}, ctx["seasons"], ctx["t"])
    assert len(no_lens) == 5
    assert "sideways" in no_lens[4]["text"].lower()


def test_how_built_section_counts_tests_and_rulings():
    ctx = build_context_from_fixtures("en")
    html = render_html(ctx)
    assert 'id="how-built"' in html and str(ctx["facts"]["n_tests"]) in html


def test_no_typed_season_in_render_or_i18n_module():
    import re
    from pathlib import Path
    for f in ("src/render.py", "src/i18n.py", "src/international_benchmark.py", "site/svg_labels.py"):
        src = Path(f).read_text(encoding="utf-8")
        body = "\n".join(l for l in src.splitlines() if not l.strip().startswith(("#", '"""', "'''")))
        assert not re.search(r"20\d\d[/–-]\d\d\b", body.replace("2024–26", "")), f


@pytest.mark.skipif(not (config.PROCESSED_DIR / "per_capita.parquet").exists(),
                    reason="data/processed not present")
def test_template_renders_with_real_context():
    ctx = build_context(load_data())
    html = _render(ctx)
    _check(html, GROUPS)
    n_rules = len(RULE_KICKERS)
    assert 3 * (n_rules - 1) <= len(ctx["cards"]) <= 3 * n_rules   # one card per group per rule, last rule may miss a group
    # Display rows (task 9) merge the two national-team-core rules into one
    # row; a merged or {event}-carrying kicker only *starts with* its short
    # label rather than matching it exactly.
    expected = ["Highest quality-adjusted production", "National-team core", "Youngest national-team call-up",
                "Most top-9 minutes", "Most domestic minutes under 23, no top-9 season yet"][:len(ctx["card_rows"])]
    assert [r["kicker"].startswith(k) for r, k in zip(ctx["card_rows"], expected, strict=True)] == [True] * len(expected)
    assert all(c["club"] and c["age_current"] for c in ctx["cards"])
    current = season_label(config.seasons()["current"])
    assert all(c["club_label"] in (current, "latest known") for c in ctx["cards"])
    assert len(ctx["per_capita"]) == 9
