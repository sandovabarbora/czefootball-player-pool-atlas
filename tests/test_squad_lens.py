import pandas as pd

from src.squad_lens import build_squad_lens

HEAD = ["ENG-Premier League"]
STEP = ["AUT-Bundesliga"]
PD = {"CZE-First League": "CZE", "DEN-Superliga": "DEN"}
MULT = {"ENG-Premier League": 1.0, "AUT-Bundesliga": 0.268, "CZE-First League": 0.434, "DEN-Superliga": 0.371}


def _squads():
    return pd.DataFrame({
        "country": ["CZE", "CZE", "CZE", "DEN"], "player": ["A", "B", "C", "D"],
        "player_norm": ["a", "b", "c", "d"], "born": [1995, 2003, 1990, 1999], "event": ["E"] * 4})


def _tables():
    return pd.DataFrame({
        "season": ["2025-2026"] * 4, "player": ["A", "B", "D", "B"], "born": [1995, 2003, 1999, 2003],
        "league": ["ENG-Premier League", "CZE-First League", "DEN-Superliga", "AUT-Bundesliga"],
        "min": [2500, 1200, 900, 300], "nation": ["CZE", "CZE", "DEN", "CZE"],
        "player_key": ["a|1995", "b|2003", "d|1999", "b|2003"]})


def test_lens_counts_tiers_cohorts_and_unmatched():
    out = build_squad_lens(_squads(), _tables(), HEAD, STEP, PD, "2025-2026", MULT)
    assert out["event"] == "E" and out["season"] == "2025-2026"
    cze = next(c for c in out["countries"] if c["country"] == "CZE")
    assert cze["n"] == 3 and cze["matched"] == 2
    assert cze["tiers"] == {"top9": 1, "stepping_stone": 0, "domestic": 1, "other": 0, "unmatched": 1}  # B: most minutes row = CZE league
    # A born 1995 -> 30+, B born 2003 -> 23-25, C (unmatched) born 1990 -> 30+
    # (assign_cohort's age = season-start-year + 1 - born; verified against src.international_benchmark)
    assert cze["cohorts"]["23-25"] == 1 and cze["cohorts"]["30+"] == 2
    # median over matched players' tier-defining-row minutes: median(2500, 1200)
    assert cze["median_minutes"] == 1850.0
    den = next(c for c in out["countries"] if c["country"] == "DEN")
    assert den["tiers"]["domestic"] == 1 and den["median_multiplier"] == 0.371


def test_unmatched_player_has_no_minutes_or_league_but_still_counts_towards_cohorts():
    out = build_squad_lens(_squads(), _tables(), HEAD, STEP, PD, "2025-2026", MULT)
    cze = next(c for c in out["countries"] if c["country"] == "CZE")
    # C (born 1990, unmatched) still contributes to the 30+ cohort even though
    # it has no fbref_players row for the metrics season.
    assert cze["tiers"]["unmatched"] == 1
    assert sum(cze["cohorts"].values()) == cze["n"]


def test_empty_multipliers_for_a_country_with_no_matched_league_quality_give_none():
    squads = pd.DataFrame({
        "country": ["CZE"], "player": ["Z"], "player_norm": ["z"], "born": [2000], "event": ["E"]})
    tables = pd.DataFrame({
        "season": ["2025-2026"], "player": ["Z"], "born": [2000], "league": ["POL-Ekstraklasa"],
        "min": [500], "nation": ["CZE"], "player_key": ["z|2000"]})
    out = build_squad_lens(squads, tables, HEAD, STEP, PD, "2025-2026", {})
    cze = next(c for c in out["countries"] if c["country"] == "CZE")
    assert cze["matched"] == 1 and cze["median_multiplier"] is None
