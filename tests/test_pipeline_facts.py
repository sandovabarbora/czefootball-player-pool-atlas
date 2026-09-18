"""Tests for src/pipeline_facts.py -- the three new computed facts behind
the "why the train left" funnel (Task 26B): club breadth of youth minutes,
domestic-league age structure, and age at first move abroad."""

from __future__ import annotations

import pandas as pd

from src.pipeline_facts import (
    age_structure,
    build_pipeline_facts,
    club_breadth,
    first_move_abroad,
)


def test_club_breadth_counts_clubs_above_threshold():
    # Club A: 1000 of 2000 minutes to a U21 player (50%, above 10%).
    # Club B: 100 of 2000 minutes to a U21 player (5%, not above 10%).
    t = pd.DataFrame({
        "league": ["AAA-Top"] * 4, "season": ["2024-2025"] * 4,
        "team": ["Club A", "Club A", "Club B", "Club B"],
        "born": [2004, 1990, 2004, 1990],
        "min": [1000, 1000, 100, 1900],
    })
    out = club_breadth(t, "2024-2025", {"AAA": "AAA-Top"})
    row = out.iloc[0]
    assert row.n_clubs == 2
    assert row.n_clubs_above == 1
    assert abs(row.share_clubs_above - 0.5) < 1e-9


def test_club_breadth_missing_league_yields_zero_row_not_dropped():
    t = pd.DataFrame({"league": ["AAA-Top"], "season": ["2024-2025"], "team": ["Club A"],
                      "born": [2004], "min": [900]})
    out = club_breadth(t, "2024-2025", {"AAA": "AAA-Top", "BBB": "BBB-Top"})
    assert len(out) == 2
    bbb = out[out.country == "BBB"].iloc[0]
    assert bbb.n_clubs == 0 and bbb.n_clubs_above == 0 and bbb.share_clubs_above is None


def test_age_structure_weighted_mean_and_shares():
    # Ages at season start (2024-2025): born 2003 -> 21, born 1994 -> 30.
    t = pd.DataFrame({
        "league": ["AAA-Top"] * 2, "season": ["2024-2025"] * 2,
        "team": ["Club A", "Club A"], "born": [2003, 1994], "min": [1000, 1000],
    })
    out = age_structure(t, "2024-2025", {"AAA": "AAA-Top"})
    row = out.iloc[0]
    assert abs(row.weighted_mean_age - 25.5) < 1e-9
    assert abs(row.share_le22 - 0.5) < 1e-9
    assert abs(row.share_ge30 - 0.5) < 1e-9
    assert row.minutes_total == 2000


def test_age_structure_missing_born_excluded_from_mean_but_kept_in_denominator():
    t = pd.DataFrame({
        "league": ["AAA-Top"] * 2, "season": ["2024-2025"] * 2,
        "team": ["Club A", "Club A"], "born": [2003, None], "min": [1000, 1000],
    })
    out = age_structure(t, "2024-2025", {"AAA": "AAA-Top"})
    row = out.iloc[0]
    assert row.weighted_mean_age == 21.0  # only the known-age row feeds the mean
    assert abs(row.share_le22 - 0.5) < 1e-9  # denominator is still both rows' minutes


def test_age_structure_missing_league_yields_none_row():
    t = pd.DataFrame({"league": ["AAA-Top"], "season": ["2024-2025"], "team": ["Club A"],
                      "born": [2003], "min": [900]})
    out = age_structure(t, "2024-2025", {"AAA": "AAA-Top", "BBB": "BBB-Top"})
    bbb = out[out.country == "BBB"].iloc[0]
    assert bbb.minutes_total == 0
    assert bbb.weighted_mean_age is None and bbb.share_le22 is None and bbb.share_ge30 is None


def test_first_move_abroad_finds_first_qualifying_season_and_its_age():
    # Player is currently (2024-2025) abroad in BBB-Top with enough
    # minutes; an earlier 2023-2024 cameo abroad (300 min) doesn't qualify,
    # so the first QUALIFYING season is 2024-2025 itself.
    t = pd.DataFrame({
        "league": ["AAA-Top", "BBB-Top", "BBB-Top"],
        "season": ["2022-2023", "2023-2024", "2024-2025"],
        "player_key": ["p1", "p1", "p1"], "nation": ["AAA", "AAA", "AAA"],
        "team": ["Home", "Away", "Away"], "born": [2003, 2003, 2003], "min": [1800, 300, 900],
    })
    out = first_move_abroad(t, {"AAA": "AAA-Top"}, ["AAA"], current="2024-2025", min_minutes=450)
    row = out.iloc[0]
    assert row.n == 1
    assert row.median_age == 21.0  # season-start year 2024 - born 2003 = 21
    assert row.censored_share == 0.0


def test_first_move_abroad_censors_when_first_qualifying_season_is_the_earliest_in_the_table():
    # Only history available starts already abroad -- we cannot see what,
    # if anything, came before it.
    t = pd.DataFrame({
        "league": ["BBB-Top"], "season": ["2022-2023"], "player_key": ["p1"],
        "nation": ["AAA"], "team": ["Away"], "born": [2001], "min": [900],
    })
    out = first_move_abroad(t, {"AAA": "AAA-Top"}, ["AAA"], current="2022-2023", min_minutes=450)
    row = out.iloc[0]
    assert row.n == 1 and row.censored_share == 1.0


def test_first_move_abroad_player_not_currently_abroad_is_not_counted():
    t = pd.DataFrame({
        "league": ["AAA-Top"], "season": ["2023-2024"], "player_key": ["p1"],
        "nation": ["AAA"], "team": ["Home"], "born": [2003], "min": [1800],
    })
    out = first_move_abroad(t, {"AAA": "AAA-Top"}, ["AAA"], current="2023-2024", min_minutes=450)
    row = out.iloc[0]
    assert row.n == 0 and row.median_age is None and row.censored_share == 0.0


def test_first_move_abroad_past_export_not_on_current_roster_is_not_counted():
    # A player who was abroad in an earlier season but is back home (or
    # off the fetched leagues) THIS season doesn't count -- only players
    # currently rostered abroad do (mirrors export_route's own "who is on
    # the roster now" construction).
    t = pd.DataFrame({
        "league": ["BBB-Top", "AAA-Top"], "season": ["2022-2023", "2024-2025"],
        "player_key": ["p1", "p1"], "nation": ["AAA", "AAA"],
        "team": ["Away", "Home"], "born": [2000, 2000], "min": [900, 1800],
    })
    out = first_move_abroad(t, {"AAA": "AAA-Top"}, ["AAA"], current="2024-2025", min_minutes=450)
    row = out.iloc[0]
    assert row.n == 0


def test_first_move_abroad_missing_domestic_league_yields_zero_row():
    t = pd.DataFrame({"league": ["BBB-Top"], "season": ["2023-2024"], "player_key": ["p1"],
                      "nation": ["CCC"], "team": ["Away"], "born": [2003], "min": [900]})
    out = first_move_abroad(t, {"AAA": "AAA-Top"}, ["AAA", "CCC"], current="2023-2024", min_minutes=450)
    ccc = out[out.country == "CCC"].iloc[0]
    assert ccc.n == 0 and ccc.median_age is None and ccc.censored_share == 0.0


def test_build_pipeline_facts_assembles_all_three_keys():
    t = pd.DataFrame({
        "league": ["AAA-Top", "AAA-Top"], "season": ["2024-2025", "2024-2025"],
        "player_key": ["p1", "p2"], "nation": ["AAA", "AAA"],
        "team": ["Club A", "Club A"], "born": [2004, 1990], "min": [1000, 1000],
    })
    cfg = {"peer_domestic": {"AAA-Top": {"country": "AAA", "tier": 1}}, "custom": {}, "headline": [],
          "domestic": "AAA-Top"}
    out = build_pipeline_facts(t, cfg, {"metrics": "2024-2025", "current": "2024-2025"}, ["AAA"])
    assert set(out) == {"breadth", "age_structure", "first_move_abroad"}
    # domestic_league_by_country always also carries config.HOME (CZE in the
    # test environment) alongside the requested peers -- see its own
    # docstring -- so look each country up by name rather than assume order.
    assert {r["country"] for r in out["breadth"]} >= {"AAA"}
    assert {r["country"] for r in out["age_structure"]} >= {"AAA"}
    assert {r["country"] for r in out["first_move_abroad"]} == {"AAA"}
