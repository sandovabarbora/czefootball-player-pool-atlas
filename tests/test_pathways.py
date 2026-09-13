"""Tests for src/pathways.py — youth exposure at home, export route, how
exports fare, profile by tier, and destinations of Czech exports."""

from __future__ import annotations

import pandas as pd

from src.pathways import (
    CLUB_STRENGTH_PROXY,
    SIDEWAYS_DEFINITION,
    _age,
    _dedupe_player_season,
    _summarize_destinations,
    build_pathways,
    destinations,
    export_route,
    fare,
    profile,
    youth_exposure,
)


def test_age_at_season_start_no_plus_one():
    # This module's own convention: age at the season's Jul 1 = season-start
    # year minus birth year (not the +1-cohort convention used elsewhere,
    # e.g. src.international_benchmark.assign_cohort).
    assert _age(2004, "2024-2025") == 20
    assert _age(2001, "2025-2026") == 24


def test_youth_exposure_counts_own_young_nationals():
    t = pd.DataFrame({
        "league": ["CZE-First League"] * 3, "season": ["2024-2025"] * 3,
        "player_key": list("abc"), "nation": ["CZE", "CZE", "SVK"],
        "born": [2004, 1995, 2004], "min": [900, 2700, 900],
    })
    out = youth_exposure(t, "2024-2025", {"CZE-First League": "CZE"})
    row = out.iloc[0]
    assert abs(row.share_u21 - 900 / 4500) < 1e-9
    assert row.minutes_total == 4500


def test_youth_exposure_share_u23_includes_older_band():
    t = pd.DataFrame({
        "league": ["CZE-First League"] * 2, "season": ["2024-2025"] * 2,
        "player_key": list("ab"), "nation": ["CZE", "CZE"],
        "born": [2002, 1990], "min": [1000, 1000],
    })
    # age(2002, 2024-2025) = 22 -> not u21, but is u23
    out = youth_exposure(t, "2024-2025", {"CZE-First League": "CZE"})
    row = out.iloc[0]
    assert row.share_u21 == 0.0
    assert abs(row.share_u23 - 0.5) < 1e-9


def test_youth_exposure_missing_league_yields_none_row():
    # SVK-Super Liga has no FBref comp_id (see config/leagues.yaml) and so
    # never appears in fbref_players.parquet at all. It must still get a
    # row -- with minutes_total 0 and share_u21/share_u23 None -- rather
    # than being silently dropped from the exhibit.
    t = pd.DataFrame({
        "league": ["CZE-First League"], "season": ["2024-2025"],
        "player_key": ["a"], "nation": ["CZE"], "born": [2004], "min": [900],
    })
    out = youth_exposure(t, "2024-2025", {"CZE-First League": "CZE", "SVK-Super Liga": "SVK"})
    assert len(out) == 2
    svk = out[out.country == "SVK"].iloc[0]
    assert svk.league == "SVK-Super Liga"
    assert svk.minutes_total == 0
    assert svk.share_u21 is None
    assert svk.share_u23 is None


def test_dedupe_player_season_sums_minutes_and_keeps_dominant_row():
    df = pd.DataFrame({
        "player_key": ["x", "x", "y"], "season": ["2023-2024"] * 3,
        "league": ["CZE-First League", "GER-Bundesliga", "AUT-Bundesliga"],
        "team": ["Sparta", "Mainz 05", "Rapid"],
        "nation": ["CZE", "CZE", "AUT"], "born": [2000, 2000, 1998],
        "min": [300, 900, 1200],
    })
    out = _dedupe_player_season(df)
    assert len(out) == 2
    x = out[out.player_key == "x"].iloc[0]
    assert x["min"] == 1200
    assert x.league == "GER-Bundesliga"  # dominant (most-minutes) club


def test_export_route_recent_entrants_and_full_roster_age():
    # x: first top-9 season 2025-2026 (== current) -> recent entrant.
    # old: first top-9 season 2021-2022, but still on the current-season
    #   roster -> counts toward n/median_export_age, excluded from
    #   origin_shares/n_recent (its "before" season, 2020-2021, predates
    #   our peer/domestic coverage window, so its true origin classifies
    #   would be an artifact, not signal).
    # y: first top-9 season 2024-2025 (== metrics, the recent_since floor)
    #   -> recent entrant, with a domestic-league "before" season
    #   (2023-2024) that IS inside our coverage window.
    t = pd.DataFrame({
        "player_key": ["x", "x", "x", "old", "old", "old", "y", "y", "y"],
        "nation": ["CZE", "CZE", "CZE", "CZE", "CZE", "CZE", "DEN", "DEN", "DEN"],
        "born": [2001, 2001, 2001, 1999, 1999, 1999, 2000, 2000, 2000],
        "league": ["CZE-First League", "NED-Eredivisie", "ENG-Premier League",
                   "CZE-First League", "ENG-Premier League", "ENG-Premier League",
                   "DEN-Superliga", "ITA-Serie A", "ITA-Serie A"],
        "season": ["2022-2023", "2023-2024", "2025-2026",
                   "2020-2021", "2021-2022", "2025-2026",
                   "2023-2024", "2024-2025", "2025-2026"],
        "min": [1000] * 9,
    })
    out = export_route(t, ["ENG-Premier League", "ITA-Serie A"], ["NED-Eredivisie"],
                        {"CZE-First League": "CZE", "DEN-Superliga": "DEN"},
                        ["CZE", "DEN"], recent_since="2024-2025")
    cze, den = out[out.country == "CZE"].iloc[0], out[out.country == "DEN"].iloc[0]

    # Full roster (x age 24, old age 22): both counted in n/median_export_age.
    assert cze.n == 2
    assert cze.median_export_age == 23.0

    # Recent-entrant subset excludes "old" (first top-9 season 2021-2022 < 2024-2025).
    assert cze.n_recent == 1
    assert cze.median_export_age_recent == 24.0
    assert cze.origin_shares["stepping_stone"] == 1.0
    assert cze.origin_shares["domestic"] == 0.0  # "old" would have been domestic, but is excluded

    assert den.n == 1 and den.n_recent == 1
    assert den.median_export_age == 24.0 and den.median_export_age_recent == 24.0
    assert den.origin_shares["domestic"] == 1.0


def test_export_route_censored_share_at_first_fetched_season():
    # x's earliest tracked headline appearance IS the table's own earliest
    # season (2020-2021) -> its true origin before that is unknown to our
    # data (censored). y's only headline appearance is at the current
    # season, one season later than the table's minimum, so it is not
    # censored (even though its own origin is "not_covered", a separate
    # concept from censoring).
    t = pd.DataFrame({
        "player_key": ["x", "x", "y"], "nation": ["CZE", "CZE", "CZE"],
        "born": [1999, 1999, 2001],
        "league": ["ENG-Premier League", "ENG-Premier League", "ENG-Premier League"],
        "season": ["2020-2021", "2023-2024", "2023-2024"],
        "min": [1000, 1000, 1000],
    })
    out = export_route(t, ["ENG-Premier League"], [], {"CZE-First League": "CZE"},
                        ["CZE"], current="2023-2024")
    cze = out[out.country == "CZE"].iloc[0]
    assert cze.n == 2
    assert abs(cze.censored_share - 0.5) < 1e-9


def test_fare_uses_goals_scored_percentile_proxy():
    tables = pd.DataFrame({
        "player_key": ["a", "b", "c", "d"], "nation": ["CZE", "CZE", "DEN", "ENG"],
        "league": ["ENG-Premier League"] * 4,
        "season": ["2024-2025"] * 4,
        "team": ["Weakside", "Strongside", "Strongside", "Weakside"],
        "born": [2000, 2000, 2000, 2000],
        "min": [900, 1800, 1800, 900],
        "mp": [20, 20, 20, 20],
        "gls": [1, 10, 10, 1],
    })
    out = fare(tables, ["ENG-Premier League"], ["CZE", "DEN"], "2024-2025")
    cze = out[out.country == "CZE"].iloc[0]
    den = out[out.country == "DEN"].iloc[0]
    # Weakside scored 2 total, Strongside 20 total -> Strongside is the
    # top-scoring (and only other) club, percentile rank 1.0 vs 0.5.
    assert cze.n == 2
    assert abs(den.median_club_goals_pct - 1.0) < 1e-9
    assert den.median_club_goals_pct > cze.median_club_goals_pct
    assert (out.club_strength_proxy == CLUB_STRENGTH_PROXY).all()


def test_fare_zero_matches_yields_n_zero_row():
    # HUN has no players in the one headline league present -> must still
    # get a row (n=0, medians None), not be dropped from the exhibit.
    tables = pd.DataFrame({
        "player_key": ["a"], "nation": ["CZE"],
        "league": ["ENG-Premier League"], "season": ["2024-2025"],
        "team": ["Arsenal"], "born": [2000], "min": [1800], "mp": [20], "gls": [10],
    })
    out = fare(tables, ["ENG-Premier League"], ["CZE", "HUN"], "2024-2025")
    assert len(out) == 2
    hun = out[out.country == "HUN"].iloc[0]
    assert hun.n == 0
    assert hun.median_min_share is None
    assert hun.median_club_goals_pct is None
    assert hun.club_strength_proxy == CLUB_STRENGTH_PROXY


def test_destinations_buckets_one_player_each():
    # One Czech-eligible player per destination bucket, all >= 450 min.
    # NED-Eredivisie is deliberately omitted from `headline` here (unlike
    # the live config) so "Stepping Sam"'s GER-2. Bundesliga row exercises
    # the stepping_stone branch cleanly; top9-before-stepping_stone
    # precedence itself is exercised by the live run (see report).
    feats = pd.DataFrame({
        "player": ["Domestic Dan", "Topnine Tom", "Stepping Sam", "Peer Pavel", "Other Otto"],
        "player_key": ["dan", "tom", "sam", "pavel", "otto"],
        "league": ["CZE-First League", "ENG-Premier League", "GER-2. Bundesliga",
                   "AUT-Bundesliga", "SOMEWHERE-Unknown League"],
        "season": ["2024-2025"] * 5,
        "nation": ["CZE"] * 5,
        "czech_eligible": [True] * 5,
        "min": [2000, 1800, 1200, 900, 500],
    })
    league_quality = {"multipliers": {
        "CZE-First League": 0.434, "ENG-Premier League": 1.0,
        "GER-2. Bundesliga": 0.473, "AUT-Bundesliga": 0.268,
        # "SOMEWHERE-Unknown League" deliberately absent -> None multiplier.
    }}
    cfg = {
        "domestic": "CZE-First League",
        "headline": ["ENG-Premier League"],
        "stepping_stone": ["GER-2. Bundesliga"],
        "peer_domestic": {"AUT-Bundesliga": {"country": "AUT"}},
    }
    rows = destinations(feats, league_quality, cfg, "2024-2025")
    by_player = {r["player"]: r["bucket"] for r in rows}
    assert by_player == {
        "Domestic Dan": "domestic",
        "Topnine Tom": "top9",
        "Stepping Sam": "stepping_stone",
        "Peer Pavel": "peer_domestic",
        "Other Otto": "other",
    }

    summary = _summarize_destinations(rows, league_quality["multipliers"][cfg["domestic"]])
    assert summary["n_total"] == 5
    assert summary["n_abroad"] == 4
    assert summary["sideways_definition"] == SIDEWAYS_DEFINITION
    # Sideways: AUT-Bundesliga (0.268) <= 0.434 -> sideways. ENG-PL (1.0)
    # and GER-2. Bundesliga (0.473) are not. "Other Otto" has no multiplier
    # on file, so is excluded from the sideways count (not "sideways").
    assert abs(summary["sideways_share"] - 1 / 4) < 1e-9
    bucket_names = {b["bucket"] for b in summary["buckets"]}
    assert bucket_names == {"top9", "stepping_stone", "peer_domestic", "other"}
    assert summary["examples"]["peer_domestic"] == ["Peer Pavel"]


def test_destinations_excludes_below_min_minutes():
    feats = pd.DataFrame({
        "player": ["Benchwarmer"], "player_key": ["bw"],
        "league": ["ENG-Premier League"], "season": ["2024-2025"],
        "nation": ["CZE"], "czech_eligible": [True], "min": [200],
    })
    league_quality = {"multipliers": {"CZE-First League": 0.434, "ENG-Premier League": 1.0}}
    cfg = {"domestic": "CZE-First League", "headline": ["ENG-Premier League"],
           "stepping_stone": [], "peer_domestic": {}}
    assert destinations(feats, league_quality, cfg, "2024-2025") == []


def test_build_pathways_fare_is_flat_list_with_proxy_per_record():
    tables = pd.DataFrame({
        "player_key": ["a", "b"], "nation": ["CZE", "DEN"],
        "league": ["ENG-Premier League", "CZE-First League"],
        "season": ["2024-2025", "2024-2025"],
        "team": ["Arsenal", "Sparta"],
        "born": [2000, 2000], "min": [1800, 1800], "mp": [20, 20], "gls": [10, 5],
    })
    feats = pd.DataFrame({
        "player_key": ["a"], "player": ["Test Player"], "nation": ["CZE"],
        "league": ["ENG-Premier League"], "season": ["2024-2025"], "pos_group": ["FW"],
        "npg_p90_quality": [0.3], "ast_p90_quality": [0.1],
        "czech_eligible": [True], "min": [1800],
    })
    league_quality = {"multipliers": {"CZE-First League": 0.434, "ENG-Premier League": 1.0}}
    cfg = {
        "headline": ["ENG-Premier League"],
        "stepping_stone": [],
        "domestic": "CZE-First League",
        "peer_domestic": {"DEN-Superliga": {"country": "DEN"}},
    }
    seasons = {"metrics": "2024-2025", "current": "2024-2025"}
    out = build_pathways(tables, feats, league_quality, cfg, seasons, ["CZE", "DEN"])

    assert isinstance(out["fare"], list)
    for row in out["fare"]:
        assert {"country", "n", "median_min_share", "median_club_goals_pct", "club_strength_proxy"} <= row.keys()
        assert row["club_strength_proxy"] == CLUB_STRENGTH_PROXY

    dest = out["destinations"]
    assert dest.keys() >= {
        "n_total", "n_abroad", "buckets", "sideways_share", "sideways_definition", "examples",
    }
    assert dest["n_total"] == 1 and dest["n_abroad"] == 1
    assert dest["buckets"][0]["bucket"] == "top9"


def test_profile_other_tier_for_peer_in_third_country_league():
    feats = pd.DataFrame({
        "player_key": ["p1", "p2"], "nation": ["CZE", "AUT"],
        "league": ["AUT-Bundesliga", "AUT-Bundesliga"], "season": ["2024-2025"] * 2,
        "pos_group": ["FW", "FW"],
        "npg_p90_quality": [0.3, 0.4], "ast_p90_quality": [0.1, 0.1],
    })
    peer_domestic = {"AUT-Bundesliga": "AUT", "CZE-First League": "CZE"}
    out = profile(feats, peer_domestic, ["ENG-Premier League"], ["NED-Eredivisie"],
                   ["CZE", "AUT"], "2024-2025")
    cze_row = out[(out.country == "CZE") & (out.pos_group == "FW")].iloc[0]
    aut_row = out[(out.country == "AUT") & (out.pos_group == "FW")].iloc[0]
    assert cze_row.tier == "other"    # CZE player in AUT's own domestic league
    assert aut_row.tier == "domestic"  # AUT player in AUT's own domestic league


def test_destinations_sideways_counts_equal_multiplier_as_sideways():
    # A peer league whose multiplier equals the domestic one (0.434) is
    # sideways (<=), a league just above it (0.435) is not.
    feats = pd.DataFrame({
        "player": ["Equal Eda", "Above Aleš"],
        "player_key": ["eda", "ales"],
        "league": ["AUT-Bundesliga", "POL-Ekstraklasa"],
        "season": ["2024-2025"] * 2,
        "nation": ["CZE"] * 2,
        "czech_eligible": [True] * 2,
        "min": [1000, 1000],
    })
    league_quality = {"multipliers": {"CZE-First League": 0.434, "AUT-Bundesliga": 0.434,
                                      "POL-Ekstraklasa": 0.435}}
    cfg = {"domestic": "CZE-First League", "headline": [], "stepping_stone": [],
           "peer_domestic": {"AUT-Bundesliga": {"country": "AUT"}, "POL-Ekstraklasa": {"country": "POL"}}}
    rows = destinations(feats, league_quality, cfg, "2024-2025")
    summary = _summarize_destinations(rows, league_quality["multipliers"][cfg["domestic"]])
    assert summary["n_abroad"] == 2
    assert abs(summary["sideways_share"] - 0.5) < 1e-9
