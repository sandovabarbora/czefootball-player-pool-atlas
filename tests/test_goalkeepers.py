"""Tests for src/goalkeepers.py -- the counter-example chapter (Task 18)."""

from __future__ import annotations

import pandas as pd

from src.goalkeepers import (
    _export_ages,
    _shrink_series,
    attach_nt_flags,
    build_goalkeepers,
    club_tier,
    gk_cards,
    gk_first_top9_ages,
    home_top9_gks,
    join_keeper_pool,
    per_million,
    production_peer_medians,
    production_table,
)

HEADLINE = ["ENG-Premier League", "GER-Bundesliga"]


def _keepers_toy() -> pd.DataFrame:
    return pd.DataFrame({
        "league": ["ENG-Premier League", "ENG-Premier League", "GER-Bundesliga", "CZE-First League"],
        "season": ["2025-2026"] * 4,
        "team": ["Team A", "Team B", "Team C", "Team D"],
        "player": ["CZE Keeper", "SVK Keeper", "AUT Keeper", "Domestic Keeper"],
        "player_key": ["cze keeper|2000", "svk keeper|1998", "aut keeper|1999", "domestic keeper|2001"],
        "nation": ["CZE", "SVK", "AUT", "CZE"],
        "born": [2000, 1998, 1999, 2001],
        "age": [25, 27, 26, 24],
        "mp": [20, 15, 10, 5],
        "min": [1800, 1350, 900, 450],
        "ga": [22, 18, 12, 8],
        "saves": [50, 40, 30, 15],
        "sota": [72, 58, 42, 23],
        "save_pct": [69.4, 69.0, 71.4, 65.2],
        "cs": [5, 4, 3, 1],
    })


def _players_all_toy() -> pd.DataFrame:
    """GK rows matching `_keepers_toy()`'s (league, season, team, player_key)
    exactly, so `join_keeper_pool` succeeds for all four rows, plus some
    outfield rows for the export-age contrast."""
    gk_rows = pd.DataFrame({
        "league": ["ENG-Premier League", "ENG-Premier League", "GER-Bundesliga", "CZE-First League"],
        "season": ["2025-2026"] * 4,
        "team": ["Team A", "Team B", "Team C", "Team D"],
        "player": ["CZE Keeper", "SVK Keeper", "AUT Keeper", "Domestic Keeper"],
        "player_key": ["cze keeper|2000", "svk keeper|1998", "aut keeper|1999", "domestic keeper|2001"],
        "nation": ["CZE", "SVK", "AUT", "CZE"],
        "pos": ["GK"] * 4,
        "born": [2000, 1998, 1999, 2001],
        "min": [1800, 1350, 900, 450],
        "gls": [0, 0, 0, 0],
    })
    outfield_rows = pd.DataFrame({
        "league": ["ENG-Premier League"] * 2,
        "season": ["2025-2026"] * 2,
        "team": ["Team A", "Team B"],
        "player": ["Out Field", "Out Field 2"],
        "player_key": ["out field|1999", "out field 2|1998"],
        "nation": ["CZE", "CZE"],
        "pos": ["FW", "MF"],
        "born": [1999, 1998],
        "min": [1800, 1500],
        "gls": [40, 60],
    })
    return pd.concat([gk_rows, outfield_rows], ignore_index=True)


def test_per_million_ranks_and_breaks_ties_by_population():
    keepers = _keepers_toy()
    peers = {"CZE": {"name": "Czechia", "population_m": 10.9}, "SVK": {"name": "Slovakia", "population_m": 5.4}}
    out = per_million(keepers, peers, HEADLINE, "2025-2026", min_minutes=450)
    assert out.loc[out.country == "SVK", "n_gk"].iloc[0] == 1
    assert out.loc[out.country == "CZE", "n_gk"].iloc[0] == 1  # only the ENG row qualifies (top-9); CZE-First League doesn't
    # SVK's rate (1/5.4) > CZE's rate (1/10.9): SVK ranks first
    assert out.sort_values("rank")["country"].tolist() == ["SVK", "CZE"]
    assert out["rank"].tolist() == [1, 2]


def test_per_million_tie_break_smaller_population_first():
    keepers = pd.DataFrame({
        "league": ["ENG-Premier League"] * 2, "season": ["2025-2026"] * 2,
        "team": ["A", "B"], "player": ["P1", "P2"], "player_key": ["p1", "p2"],
        "nation": ["CZE", "SVK"], "born": [2000, 2000], "age": [25, 25],
        "mp": [10, 10], "min": [900, 900], "ga": [10, 10], "saves": [30, 30],
        "sota": [40, 40], "save_pct": [75.0, 75.0], "cs": [2, 2],
    })
    peers = {"CZE": {"name": "Czechia", "population_m": 10.0}, "SVK": {"name": "Slovakia", "population_m": 5.0}}
    out = per_million(keepers, peers, HEADLINE, "2025-2026", min_minutes=450)
    # equal n (1 each) but different population -> per_million differs, no real tie here;
    # use equal population instead to force a tie
    peers_tied = {"CZE": {"name": "Czechia", "population_m": 5.0}, "SVK": {"name": "Slovakia", "population_m": 5.0}}
    out2 = per_million(keepers, peers_tied, HEADLINE, "2025-2026", min_minutes=450)
    assert out2["per_million"].nunique() == 1
    assert out2.sort_values("rank")["country"].tolist() == ["CZE", "SVK"]  # insertion order tie-break (stable sort)


def test_per_million_applies_minutes_floor():
    keepers = _keepers_toy()
    peers = {"CZE": {"name": "Czechia", "population_m": 10.9}}
    out = per_million(keepers, peers, HEADLINE, "2025-2026", min_minutes=2000)
    assert out.loc[out.country == "CZE", "n_gk"].iloc[0] == 0  # CZE Keeper only has 1800 min


# ---- Task 18 fix round 1, item 4: join fbref_keepers to the GK rows of
# fbref_players.parquet, canonical born/nation/min, unjoined count logged.

def test_join_keeper_pool_uses_players_table_as_canonical_and_counts_unjoined():
    keepers = pd.DataFrame({
        "league": ["ENG-Premier League", "ENG-Premier League"], "season": ["2025-2026"] * 2,
        "team": ["Team A", "Team B"], "player": ["CZE Keeper", "Ghost Keeper"],
        "player_key": ["cze keeper|2000", "ghost keeper|1999"], "nation": ["XXX", "SVK"],  # wrong nation on purpose
        "born": [1900, 1998], "age": [25, 27], "mp": [20, 15], "min": [1, 1350],  # wrong min on purpose
        "ga": [22, 18], "saves": [50, 40], "sota": [72, 58], "save_pct": [69.4, 69.0], "cs": [5, 4],
    })
    players_all = pd.DataFrame({
        "league": ["ENG-Premier League"], "season": ["2025-2026"], "team": ["Team A"],
        "player": ["CZE Keeper"], "player_key": ["cze keeper|2000"], "nation": ["CZE"],
        "pos": ["GK"], "born": [2000], "min": [1800],
    })
    joined, unjoined = join_keeper_pool(keepers, players_all)
    assert unjoined == 1  # "Ghost Keeper" has no matching GK row -> dropped
    assert len(joined) == 1
    row = joined.iloc[0]
    assert row.nation == "CZE" and row.born == 2000 and row["min"] == 1800  # canonical, not the keeper page's own
    assert row.ga == 22  # production stats kept from the keeper table
    assert list(joined.columns) == list(keepers.columns)


def test_export_ages_walks_first_top9_season_and_counts_censored():
    t = pd.DataFrame({
        "league": ["CZE-First League", "GER-Bundesliga", "ENG-Premier League"],
        "season": ["2022-2023", "2023-2024", "2025-2026"],
        "team": ["Sparta", "Mainz", "Arsenal"],
        "player": ["Jan Novak"] * 3, "player_key": ["jan novak|2000"] * 3,
        "nation": ["CZE"] * 3, "born": [2000, 2000, 2000],
        "min": [900, 1500, 1800],
    })
    ages, censored = _export_ages(t, ["GER-Bundesliga", "ENG-Premier League"], "CZE", "2025-2026", "2020-2021")
    assert ages == [23.0]  # first top-9 season 2023-2024, born 2000 -> 23
    assert censored == 0  # 2023-2024 != the shared first_hist "2020-2021"


def test_export_ages_marks_censored_when_first_season_is_the_history_floor():
    t = pd.DataFrame({
        "league": ["GER-Bundesliga"], "season": ["2020-2021"], "team": ["Mainz"],
        "player": ["Jan Novak"], "player_key": ["jan novak|2000"],
        "nation": ["CZE"], "born": [2000], "min": [1500],
    })
    ages, censored = _export_ages(t, ["GER-Bundesliga"], "CZE", "2020-2021", "2020-2021")
    assert ages == [20.0]
    assert censored == 1  # first (only) top-9 season IS the earliest fetched season


def test_gk_first_top9_ages_pairs_name_with_age_and_censoring():
    home_top9 = pd.DataFrame({
        "player_key": ["jan novak|2000"], "player": ["Jan Novak"], "league": ["ENG-Premier League"],
        "team": ["Arsenal"], "min": [1800], "nation": ["CZE"], "born": [2000],
    })
    gk_history = pd.DataFrame({
        "league": ["GER-Bundesliga", "ENG-Premier League"],
        "season": ["2024-2025", "2025-2026"],
        "team": ["Mainz", "Arsenal"],
        "player": ["Jan Novak", "Jan Novak"], "player_key": ["jan novak|2000"] * 2,
        "nation": ["CZE"] * 2, "born": [2000, 2000], "min": [1500, 1800], "pos": ["GK"] * 2,
    })
    rows = gk_first_top9_ages(home_top9, gk_history, ["GER-Bundesliga", "ENG-Premier League"], "2020-2021")
    assert rows == [{"player_key": "jan novak|2000", "player": "Jan Novak",
                     "first_age": 24.0, "first_season": "2024-2025", "censored": False}]


def test_gk_first_top9_ages_uses_full_players_history_not_just_keeper_pages():
    """Task 18 fix round 1, item 2: the keeper pages only reach back to
    previous/metrics/current, so a GK whose true first top-9 season is
    2020-2021 must still be found and flagged censored when walked over
    `fbref_players.parquet`'s GK rows (which do reach that far back)."""
    home_top9 = pd.DataFrame({
        "player_key": ["old keeper|1996"], "player": ["Old Keeper"], "league": ["ENG-Premier League"],
        "team": ["Everton"], "min": [3000], "nation": ["ENG"], "born": [1996],
    })
    gk_history = pd.DataFrame({
        "league": ["ENG-Premier League", "ENG-Premier League"],
        "season": ["2020-2021", "2025-2026"],
        "team": ["Sunderland", "Everton"],
        "player": ["Old Keeper", "Old Keeper"], "player_key": ["old keeper|1996"] * 2,
        "nation": ["ENG"] * 2, "born": [1996, 1996], "min": [1200, 3000], "pos": ["GK"] * 2,
    })
    rows = gk_first_top9_ages(home_top9, gk_history, ["ENG-Premier League"], "2020-2021")
    assert rows[0]["first_age"] == 24.0  # 2020-2021, born 1996
    assert rows[0]["first_season"] == "2020-2021"
    assert rows[0]["censored"] is True


def test_club_tier_joins_goals_scored_percentile():
    home_top9 = pd.DataFrame({
        "player": ["CZE Keeper"], "player_key": ["cze keeper|2000"],
        "league": ["ENG-Premier League"], "team": ["Team A"], "min": [1800],
    })
    players_all = pd.DataFrame({
        "league": ["ENG-Premier League"] * 3,
        "season": ["2025-2026"] * 3,
        "team": ["Team A", "Team B", "Team X"],
        "gls": [40, 60, 20],
    })
    out = club_tier(home_top9, players_all, "2025-2026")
    assert len(out) == 1
    row = out.iloc[0]
    assert row.player == "CZE Keeper"
    # Team A scored 40 of {20,40,60} -> rank 2/3 -> pct = 2/3
    assert abs(row.club_goals_pct - (2 / 3)) < 1e-9


def test_shrink_series_falls_back_to_full_median_when_no_row_clears_k():
    df = pd.DataFrame({
        "league": ["ENG-Premier League"] * 3, "season": ["2025-2026"] * 3,
        "saves": [50, 40, 30], "sota": [72, 58, 42],
    })
    df["save_rate"] = df["saves"] / df["sota"]
    out = _shrink_series(df, "saves", "save_rate", "sota", k=900, per90=False)
    # no row's sota >= 900 -> med = median of the whole cohort's save_rate
    med = df["save_rate"].median()
    expected = (df["saves"] + 900 * med) / (df["sota"] + 900)
    assert (out.round(6) == expected.round(6)).all()
    # a K of 900 phantom shots vastly exceeds any one row's sota -> shrunk
    # values sit close to the cohort median, not to each player's own rate
    assert (out - med).abs().max() < (df["save_rate"] - med).abs().max()


def test_shrink_series_per90_matches_features_bayesian_shrink_formula():
    df = pd.DataFrame({
        "league": ["ENG-Premier League"] * 2, "season": ["2025-2026"] * 2,
        "ga": [22, 18], "min": [1800, 1350],
    })
    df["ga90"] = df["ga"] / (df["min"] / 90.0)
    out = _shrink_series(df, "ga", "ga90", "min", k=900, per90=True)
    k90 = 900 / 90.0
    med = df["ga90"].median()  # neither row clears 900 min? both do (1800, 1350 >= 900)
    well = df[df["min"] >= 900]
    med = well["ga90"].median()
    expected = (df["ga"] + k90 * med) / (df["min"] / 90.0 + k90)
    assert (out.round(6) == expected.round(6)).all()


# ---- Task 18 fix round 1, item 1: GA/90 quality adjustment divides by the
# league multiplier (weaker league -> GA scales up), not multiplies.

def test_production_table_adds_quality_adjusted_ga90():
    keepers = _keepers_toy()
    league_quality = {"multipliers": {"ENG-Premier League": 1.0, "GER-Bundesliga": 0.788, "CZE-First League": 0.434}}
    out = production_table(keepers, "2025-2026", league_quality, min_minutes=450, k=900)
    assert len(out) == 4
    row = out[out.player == "CZE Keeper"].iloc[0]
    assert abs(row.ga90 - 22 / (1800 / 90.0)) < 1e-9
    assert abs(row.ga90_q - row.ga90_shrunk / 1.0) < 1e-9  # ENG multiplier is the 1.0 baseline: no change
    assert 0 <= row.save_pct_shrunk <= 100


def test_production_table_ga90_q_inflates_for_a_sub_one_multiplier():
    """A sub-1 (weaker-than-baseline) league multiplier must INFLATE
    ga90_shrunk, not discount it -- dividing by a multiplier < 1 increases
    the value, matching the copy ('a goal conceded in a stronger league
    counts less' -- i.e. more in a weaker one)."""
    keepers = _keepers_toy()
    league_quality = {"multipliers": {"ENG-Premier League": 1.0, "GER-Bundesliga": 0.788, "CZE-First League": 0.434}}
    out = production_table(keepers, "2025-2026", league_quality, min_minutes=450, k=900)
    row = out[out.player == "AUT Keeper"].iloc[0]  # plays in GER-Bundesliga, multiplier 0.788
    assert row.league_multiplier == 0.788
    assert row.ga90_q > row.ga90_shrunk
    assert abs(row.ga90_q - row.ga90_shrunk / 0.788) < 1e-9


def test_production_peer_medians_one_row_per_peer_even_when_empty():
    keepers = _keepers_toy()
    league_quality = {"multipliers": {"ENG-Premier League": 1.0, "GER-Bundesliga": 0.788, "CZE-First League": 0.434}}
    prod = production_table(keepers, "2025-2026", league_quality, min_minutes=450, k=900)
    out = production_peer_medians(prod, ["CZE", "SVK", "POL"])
    assert out["country"].tolist() == ["CZE", "SVK", "POL"]
    pol_row = out[out.country == "POL"].iloc[0]
    assert pol_row.n == 0 and pd.isna(pol_row.median_ga90_q)


def test_home_top9_gks_applies_league_and_minutes_filter():
    keepers = _keepers_toy()
    out = home_top9_gks(keepers, "CZE", HEADLINE, "2025-2026", min_minutes=450)
    assert out["player"].tolist() == ["CZE Keeper"]  # domestic keeper's league isn't headline


def test_attach_nt_flags_matches_by_name_and_born():
    df = pd.DataFrame({"player": ["Jan Novak", "Petr Svoboda"], "born": [2000, 1998]})
    nt = pd.DataFrame({
        "player_norm": ["jan novak", "petr svoboda"], "born": [2000, 1990],  # Svoboda's born mismatches
        "event": ["UEFA Euro 2024", "UEFA Euro 2024"],
    })
    out = attach_nt_flags(df, nt)
    assert out[out.player == "Jan Novak"].iloc[0].nt_flag
    assert not out[out.player == "Petr Svoboda"].iloc[0].nt_flag  # born mismatch -> not flagged


def test_gk_cards_picks_most_minutes_and_youngest():
    keepers = _keepers_toy()
    league_quality = {"multipliers": {"ENG-Premier League": 1.0, "GER-Bundesliga": 0.788, "CZE-First League": 0.434}}
    prod = production_table(keepers, "2025-2026", league_quality, min_minutes=450, k=900)
    home_top9 = home_top9_gks(keepers, "CZE", HEADLINE, "2025-2026", min_minutes=450)
    tier = club_tier(home_top9, pd.DataFrame({
        "league": ["ENG-Premier League"], "season": ["2025-2026"], "team": ["Team A"], "gls": [40],
    }), "2025-2026")
    nt = pd.DataFrame({"player_norm": [], "born": [], "event": []})
    cards = gk_cards(home_top9, prod, tier, nt)
    assert len(cards) == 1  # only one CZE goalkeeper qualifies in the toy data -> same pick, dedup'd to one card
    assert cards[0]["player"] == "CZE Keeper"
    assert cards[0]["reason"] == "most top-9 minutes among home goalkeepers"


# ---- Task 18 fix round 1, item 3: one season everywhere -- the sentence's
# n_gk, the club-tier table's row count and the export-age median's n must
# all be the same number.

def test_build_goalkeepers_count_equals_table_rows_equals_median_n():
    keepers = _keepers_toy()
    players_all = _players_all_toy()
    peers_meta = {"CZE": {"name": "Czechia", "population_m": 10.9}, "SVK": {"name": "Slovakia", "population_m": 5.4}}
    league_quality = {"multipliers": {"ENG-Premier League": 1.0, "GER-Bundesliga": 0.788, "CZE-First League": 0.434}}
    nt = pd.DataFrame({"player_norm": [], "born": [], "event": []})
    out, unjoined = build_goalkeepers(
        keepers, players_all, peers_meta, HEADLINE, "CZE", "2025-2026",
        league_quality, nt, min_minutes=450, k=900,
    )
    assert unjoined == 0  # every keeper row in the toy data joins cleanly
    n_gk_sentence = next(r["n_gk"] for r in out["per_million"] if r["country"] == "CZE")
    assert n_gk_sentence == 1
    assert len(out["club_tier"]) == n_gk_sentence
    assert out["export_age"]["gk_n"] == n_gk_sentence


def test_build_goalkeepers_json_shape():
    keepers = _keepers_toy()
    players_all = _players_all_toy()
    peers_meta = {"CZE": {"name": "Czechia", "population_m": 10.9}, "SVK": {"name": "Slovakia", "population_m": 5.4}}
    league_quality = {"multipliers": {"ENG-Premier League": 1.0, "GER-Bundesliga": 0.788, "CZE-First League": 0.434}}
    nt = pd.DataFrame({"player_norm": [], "born": [], "event": []})
    out, unjoined = build_goalkeepers(
        keepers, players_all, peers_meta, HEADLINE, "CZE", "2025-2026",
        league_quality, nt, min_minutes=450, k=900,
    )
    assert unjoined == 0
    for key in ("min_minutes", "phantom_minutes", "per_million", "home_rank", "n_peers",
               "export_age", "club_tier", "club_strength_proxy", "production", "cards"):
        assert key in out
    for key in ("gk_n", "gk_median_age", "gk_censored", "gk_censored_share",
               "outfield_n", "outfield_median_age", "outfield_censored", "outfield_censored_share"):
        assert key in out["export_age"]
    assert out["export_age"]["gk_n"] == 1
    assert out["export_age"]["outfield_n"] == 2
    assert isinstance(out["production"]["home"], list) and isinstance(out["production"]["peer_medians"], list)
    assert len(out["cards"]) == 1
