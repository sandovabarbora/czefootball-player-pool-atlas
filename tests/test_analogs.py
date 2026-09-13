import pandas as pd

from src.historical_analogs import find_analogs, showcase_ids


def _corpus():
    rows = []
    for key, born, seasons, pos_group in [
        ("t", 2002, ["2024-2025"], "FW"),
        ("a", 1998, ["2020-2021", "2021-2022"], "FW"),
        ("b", 1990, ["2012-2013", "2013-2014"], "FW"),
        # same age (23) and identical stats as "a" in 2020-2021, but a
        # different position group -- must never be selected for FW target "t".
        ("c", 1998, ["2020-2021"], "MF"),
    ]:
        for s in seasons:
            rows.append({"player_key": key, "player": key.upper(), "nation": "X", "league": "L", "season": s,
                         "born": born, "min": 2000, "npg_ast_q": 0.5, "league_multiplier": 0.8,
                         "pos_group": pos_group})
    return pd.DataFrame(rows)


def test_analogs_match_same_age_and_list_following_seasons():
    out = find_analogs(_corpus(), "t", k=2)
    assert list(out.player_key) == ["a", "b"]          # both aged 22 in their first listed season
    assert out.iloc[0].followed[0]["season"] == "2021-2022"


def test_analogs_exclude_other_position_groups():
    out = find_analogs(_corpus(), "t", k=3)
    assert "c" not in out.player_key.values  # same age, off-group -> excluded


def test_analogs_output_columns():
    out = find_analogs(_corpus(), "t", k=2)
    assert list(out.columns) == ["rank", "player_key", "player", "nation", "league", "season",
                                  "min", "npg_ast_q", "distance", "followed"]
    assert list(out["rank"]) == [1, 2]


def _showcase_toy():
    fw = pd.DataFrame({
        "player_key": ["fw_top", "fw_young_nt", "fw_old_nt", "fw_low_min", "fw_export_2nd", "fw_home"],
        "player": ["FW Top", "FW Young NT", "FW Old NT", "FW Low Min", "FW Export 2nd", "FW Home"],
        "season": ["2024-2025"] * 6,
        "league": ["ENG-Premier League", "CZE-First League", "CZE-First League", "ITA-Serie A",
                   "GER-Bundesliga", "CZE-First League"],
        "czech_eligible": [True] * 6,
        "min": [1200, 1000, 950, 500, 1100, 3000],
        "npg_p90_quality": [0.9, 0.4, 0.3, 5.0, 0.2, 0.3],
        "ast_p90_quality": [0.2, 0.1, 0.1, 5.0, 0.1, 0.1],
        "nt_flag": [False, True, True, False, False, False],
        "born": [2000, 2003, 1995, 2005, 1998, 1999],
    })
    mf = pd.DataFrame({
        "player_key": ["mf_best_and_youngest"],
        "player": ["MF Best And Youngest"],
        "season": ["2024-2025"],
        "league": ["CZE-First League"],
        "czech_eligible": [True],
        "min": [1500],
        "npg_p90_quality": [0.6],
        "ast_p90_quality": [0.6],
        "nt_flag": [True],
        "born": [2004],
    })
    return {"FW": fw, "MF": mf}


def test_showcase_ids_picks_top_quality_and_youngest_nt_skipping_low_minutes():
    out = showcase_ids(_showcase_toy(), "2024-2025")
    keys = [s["player_key"] for s in out]
    # fw_low_min excluded: min < 900
    assert "fw_low_min" not in keys
    # top quality-adjusted FW
    assert "fw_top" in keys
    # youngest NT-flagged FW (born 2003 > born 1995)
    assert "fw_young_nt" in keys
    assert "fw_old_nt" not in keys
    # MF: same player is both top quality and youngest NT -> only listed once
    assert keys.count("mf_best_and_youngest") == 1
    assert len(out) <= 9
    reasons = {s["player_key"]: s["reason"] for s in out}
    assert reasons["fw_top"] == "highest quality-adjusted npG+A per 90 among FW"
    assert reasons["fw_young_nt"] == "youngest national-team call-up among FW"
    assert all("pos_group" in s and "player" in s for s in out)


def test_showcase_third_rule_most_top9_minutes_skips_already_chosen():
    out = showcase_ids(_showcase_toy(), "2024-2025", headline_leagues=["ENG-Premier League",
                                                                       "GER-Bundesliga",
                                                                       "ITA-Serie A"])
    reasons = {s["player_key"]: s["reason"] for s in out}
    # fw_top has the most top-9 minutes (1200) but is already chosen by rule (a);
    # fw_low_min (ITA, 500) is under the floor; fw_home (3000) plays at home ->
    # the rule falls through to fw_export_2nd (GER, 1100).
    assert reasons["fw_export_2nd"] == "most top-9 league minutes among FW"
    assert "fw_home" not in reasons
    assert [s["player_key"] for s in out if s["pos_group"] == "FW"] == ["fw_top", "fw_young_nt", "fw_export_2nd"]
    # MF has no headline-league player -> no third card for MF
    assert [s["player_key"] for s in out if s["pos_group"] == "MF"] == ["mf_best_and_youngest"]
