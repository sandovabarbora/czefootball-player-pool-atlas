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
    _build_observations,
    _current_club,
    build_context,
    build_context_from_fixtures,
    load_data,
    render_html,
)

SECTION_IDS = (
    "summary", "q1", "q2", "q3", "q4", "q5", "q6", "q7", "q8", "q8b", "q9", "for-federation",
    "explore", "benchmark", "observations", "clusters", "trajectories", "pathways",
    "exhibit-f", "analogs", "players", "methodology", "multipliers", "league-strength", "shrinkage",
    "pca-loadings", "sensitivity", "data-quality", "limitations", "validation-robustness", "how-built",
    "reproducibility", "references", "photo-credits",
)


def _render(ctx: dict) -> str:
    env = Environment(loader=FileSystemLoader(str(config.TEMPLATES_DIR)), autoescape=False)
    return env.get_template("report.html.j2").render(**ctx)


def _check(html: str, groups: list[str]) -> None:
    assert '<html lang="en">' in html
    assert 'class="hero-num-figure"' in html and "*" in html
    for cls in ("capita-row", "cohort-grid", "cluster-list", "cycle-card", "analog-block", "limitations",
                "slide", "slide-q", "slide-a", "slide-proof", "slide-how"):
        assert f'class="{cls}' in html, cls
    assert "peer-compare" in html
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
        "nt_flag": False, "nt_events": "", "home_eligible": True,
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


def test_nine_slides_each_carry_question_answer_proof_and_how():
    """Task 13b: the page opens with nine <section class="slide"> blocks,
    each exactly h2.slide-q / p.slide-a / div.slide-proof / p.slide-how, in
    that order, nothing else."""
    ctx = build_context_from_fixtures("en")
    html = _render(ctx)
    for n in range(1, 10):
        m = re.search(rf'<section class="slide" id="q{n}">(.*?)</section>', html, re.S)
        assert m, f"slide q{n} missing"
        block = m.group(1)
        assert re.search(r'<h2 class="slide-q">.+?</h2>', block, re.S), n
        assert re.search(r'<p class="slide-a">.*?</p>', block, re.S), n
        assert re.search(r'<div class="slide-proof">.*?</div>', block, re.S), n
        assert re.search(r'<p class="slide-how"><span class="slide-how-label">.*?</span>.*?</p>', block, re.S), n
        # order: q before a before proof before how
        idx = [block.index(x) for x in ('class="slide-q"', 'class="slide-a"', 'class="slide-proof"', 'class="slide-how"')]
        assert idx == sorted(idx), n


def test_for_a_federation_stays_after_the_slides_before_explore():
    ctx = build_context_from_fixtures("en")
    html = _render(ctx)
    assert 'class="for-federation"' in html and "Run for England" not in html
    q9_pos = html.index('id="q9"')
    fed_pos = html.index('class="for-federation"')
    explore_pos = html.index('id="explore"')
    assert q9_pos < fed_pos < explore_pos


def test_explore_section_folds_the_old_chapters_and_keeps_their_ids():
    """Task 13b: 'Explore the data' is folded (<details class="fold">), and
    the ids benchmark/observations/clusters/trajectories/pathways/exhibit-f/
    analogs/players survive inside it so old deep links still land."""
    ctx = build_context_from_fixtures("en")
    html = _render(ctx)
    explore = html.split('id="explore"')[1]
    for sid in ("benchmark", "observations", "clusters", "trajectories", "pathways",
                "exhibit-f", "analogs", "players"):
        assert f'id="{sid}"' in explore, sid
    # six top-level folds directly under the Explore section (brief: Benchmark
    # heatmap, Cluster archetypes, Trajectories, Pathways A-F, Historical
    # analogs, Player index)
    assert explore.count('<details class="fold">') >= 6


def test_hero_shows_its_numbers_once_not_in_tiles_and_a_meta_strip_too():
    """Task 10: hero.tiles/hero.meta are gone. Task 13b: the computed
    "argument" list is gone too, replaced by the nine slides."""
    ctx = build_context_from_fixtures("en")
    html = _render(ctx)
    assert 'class="hero-tiles"' not in html and 'class="hero-meta"' not in html
    assert 'class="argument"' not in html and 'id="findings"' not in html
    assert 'class="cards-more"' not in html


def test_peer_compare_table_has_three_countries_and_seven_rows():
    ctx = build_context_from_fixtures("en")
    pc = ctx["peer_compare"]
    assert pc["countries"] == ["CZE", "NOR", "DEN"]
    assert len(pc["rows"]) == 7
    assert all(set(pc["countries"]) <= set(r["by_country"]) for r in pc["rows"])
    html = _render(ctx)
    q8 = re.search(r'<section class="slide" id="q8">(.*?)</section>', html, re.S).group(1)
    assert q8.count("<th") >= 4  # metric + 3 countries
    assert q8.count("<tr>") == 1 + 7  # header row + one row per metric


def test_big5_context_has_peak_low_last_and_golden():
    ctx = build_context_from_fixtures("en")
    big5 = ctx["big5"]
    assert big5["peak_n"] >= big5["last_n"] or big5["peak_n"] >= big5["low_n"]
    assert big5["golden"]
    html = _render(ctx)
    q7 = re.search(r'<section class="slide" id="q7">(.*?)</section>', html, re.S).group(1)
    assert "big5_series.svg" in q7
    assert big5["golden"] in q7


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


def test_toc_lists_nine_questions_then_explore_then_method():
    """Task 13b: the Contents rail is q1..q9, Explore, Method (with its old
    submenu); "findings" is gone entirely, data-quality/how-built keep their
    ids but stay unlinked (methodology chapter is unchanged)."""
    ctx = build_context_from_fixtures("en")
    html = _render(ctx)
    toc_sticky = html.split('<nav class="toc-sticky"')[1].split("</nav>")[0]
    toc_mobile = html.split('<details class="toc-mobile"')[1].split("</details>")[0]
    for frag in (toc_sticky, toc_mobile):
        assert 'href="#findings"' not in frag
        assert 'href="#data-quality"' not in frag
        assert 'href="#how-built"' not in frag
        for n in range(1, 10):
            assert f'href="#q{n}"' in frag, n
        assert 'href="#explore"' in frag
    assert 'id="findings"' not in html
    assert 'id="data-quality"' in html and 'id="how-built"' in html


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


@pytest.mark.skipif(config.NATION != "cze", reason="golden fixture only covers NATION=cze")
@pytest.mark.skipif(not (config.PROCESSED_DIR / "per_capita.parquet").exists(),
                    reason="data/processed not present")
def test_context_matches_golden_fixture_for_cze():
    """Task 14a: the Czech run's context must stay byte-identical to the
    pre-refactor pipeline. `tests/fixtures/context_cze_golden.json` was
    captured from `build_context(load_data())` on main before the home-nation
    refactor landed; this compares the same (nation-configurable) subset
    today, for NATION=cze.
    """
    import json
    from pathlib import Path

    ctx = build_context(load_data(), lang="en")
    cards = [{"player_key": c["player_key"], "reason": c["reason"]} for c in ctx["cards"]]
    actual = {
        "hero": ctx["hero"],
        "per_capita": ctx["per_capita"],
        "cards": cards,
        "squad_lens_rows": ctx["squad_lens"].get("rows", []),
        "peer_compare": ctx["peer_compare"],
    }
    actual_json = json.loads(json.dumps(actual, sort_keys=True, default=str))

    golden_path = Path(__file__).parent / "fixtures" / "context_cze_golden.json"
    expected_json = json.loads(golden_path.read_text(encoding="utf-8"))

    assert actual_json == expected_json


def test_cluster_top_surnames_are_computed_not_hand_typed():
    """Task 14b: the tactical read's "(Name, Name, Name)" is the three
    home-eligible players with the most metrics-season minutes in the style
    cluster, by surname -- correct for any nation/refit, unlike a hand-typed
    list in config/cluster_labels.yaml."""
    from src.render import _cluster_top_surnames, _with_tactical_examples

    coords = pd.DataFrame([
        {"player_key": "a|2000", "player": "Jan Novak", "season": "2025-2026",
         "cluster_style": "C0", "home_eligible": True, "min": 900},
        {"player_key": "b|2001", "player": "Petr Svoboda", "season": "2025-2026",
         "cluster_style": "C0", "home_eligible": True, "min": 2000},
        {"player_key": "c|2002", "player": "Foreign Player", "season": "2025-2026",
         "cluster_style": "C0", "home_eligible": False, "min": 3000},
        {"player_key": "d|2003", "player": "Karel Dvorak", "season": "2025-2026",
         "cluster_style": "C1", "home_eligible": True, "min": 2500},
    ])
    names = _cluster_top_surnames(coords, "2025-2026", "C0")
    assert names == ["Svoboda", "Novak"]  # sorted by minutes, foreign player excluded, other cluster excluded
    assert _with_tactical_examples("Base read", names) == "Base read (Svoboda, Novak)."
    assert _with_tactical_examples("Base read", []) == "Base read."
    assert _with_tactical_examples("", names) == ""
    # a fixture lacking the needed columns degrades to no examples, not a KeyError
    assert _cluster_top_surnames(pd.DataFrame([{"player_key": "x", "season": "2025-2026"}]), "2025-2026", "C0") == []


def test_slide4_and_5_how_gain_a_home_league_note_only_when_it_is_inside_the_topn():
    """Task 14b: slide.4.how/slide.5.how's {home_note} is the empty string
    (identical to the pre-14b text) when the home domestic league is outside
    the top-N leagues (Czechia's case), and a clarifying sentence when it is
    inside them (a future England run's case) -- computed in the template
    from `domestic_league_code` / `headline_leagues`, never hardcoded."""
    ctx = build_context_from_fixtures("en")
    assert ctx["domestic_league_code"] not in ctx["headline_leagues"]
    html = _render(ctx)
    how = re.search(r'id="q4">.*?slide-how">(.*?)</p>', html, re.S).group(1)
    assert "is itself one of Europe's top" not in how


def test_slide_8b_goalkeepers_counter_example():
    """Task 18: slide 8b sits between q8 and q9, carries the strip-plot
    figure and the folded club-tier table, a GK card row appears in the
    roster under its own kicker, and chapter IV gets the GK shrinkage
    paragraph -- all driven by the `gk` context key (empty dict = section
    absent, tested separately below)."""
    ctx = build_context_from_fixtures("en")
    html = _render(ctx)
    q8_pos, q8b_pos, q9_pos = html.index('id="q8"'), html.index('id="q8b"'), html.index('id="q9"')
    assert q8_pos < q8b_pos < q9_pos
    q8b = re.search(r'<section class="slide" id="q8b">(.*?)</section>', html, re.S).group(1)
    assert re.search(r'<h2 class="slide-q">.+?</h2>', q8b, re.S)
    assert re.search(r'<p class="slide-a">.*?</p>', q8b, re.S)
    assert "gk_export_age.svg" in q8b
    assert "<table" in q8b and "Mainz 05" in q8b
    assert re.search(r'<p class="slide-how"><span class="slide-how-label">.*?</span>.*?</p>', q8b, re.S)
    assert "gk-card" in html and "Jindřich Staněk" in html
    assert "Goalkeepers — most top-9 minutes" in html
    assert "Bayesian shrinkage" in html  # ch4 shrinkage h3 still present
    shrink_section = html.split('id="shrinkage"')[1].split("<h3")[0]
    assert "save_pct_shrunk" in shrink_section


def test_slide_8b_absent_when_gk_context_empty():
    ctx = build_context_from_fixtures("en")
    ctx["gk"] = {}
    html = _render(ctx)
    assert 'id="q8b"' not in html
    assert "gk-card" not in html
    assert "save_pct_shrunk" not in html

    ctx2 = dict(ctx, domestic_league_code="ENG-Premier League", headline_leagues=["ENG-Premier League"])
    html2 = _render(ctx2)
    how2 = re.search(r'id="q4">.*?slide-how">(.*?)</p>', html2, re.S).group(1)
    assert "is itself one of Europe's top" in how2


def test_slide_8b_how_discloses_censoring_and_gains_home_note_only_when_headline():
    """Task 18 fix round 1, items 2 and 6: the how-line states the censored
    share of both the goalkeepers and the outfield exports, and gains the
    same {home_note} slides 4/5 use only when the home league is itself one
    of the headline leagues."""
    ctx = build_context_from_fixtures("en")
    assert ctx["domestic_league_code"] not in ctx["headline_leagues"]
    html = _render(ctx)
    how = re.search(r'id="q8b">.*?slide-how">(.*?)</p>', html, re.S).group(1)
    assert "censored" in how
    assert "% of the goalkeepers" in how and "% of the outfield exports" in how
    assert "needs no move" not in how

    ctx2 = dict(ctx, domestic_league_code="ENG-Premier League", headline_leagues=["ENG-Premier League"])
    html2 = _render(ctx2)
    how2 = re.search(r'id="q8b">.*?slide-how">(.*?)</p>', html2, re.S).group(1)
    assert "needs no move" in how2


def test_slide_8b_a_uses_czech_nominative_plural_agreement():
    """Task 18 fix round 1, item 5: the counted-noun + verb pair must agree
    as nominative plural + plural verb ('brankáři hrají'), not genitive
    plural + singular verb ('brankářů hraje')."""
    ctx = build_context_from_fixtures("cs")
    html = _render(ctx)
    a = re.search(r'id="q8b">.*?slide-a">(.*?)</p>', html, re.S).group(1)
    assert "brankáři hrají" in a
    assert "brankářů hraje" not in a


def test_repo_urls_point_at_the_real_owner():
    """The GitHub owner is sandovabarbora; a wrong owner makes every download 404."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for rel in ("src/render.py", "README.md"):
        assert "barborasandova/" not in (root / rel).read_text(encoding="utf-8"), rel
