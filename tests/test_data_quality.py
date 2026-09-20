import pandas as pd
from src.data_quality import compute_checks


def test_checks_count_split_seasons_and_no_tables():
    pool = pd.DataFrame({"player": ["Ladislav Krejčí", "Ladislav Krejčí", "Jan Novák"], "in_fbref_tables": [True, True, False]})
    tables = pd.DataFrame({"league": ["CZE-First League"] * 2, "nation": ["CZE", "CZE"], "born": [1999, pd.NA]})
    fw = pd.DataFrame({"player_key": ["x|1", "x|1"], "season": ["2025-2026"] * 2, "pos_group": ["FW"] * 2,
                       "min": [500, 400], "league": ["A", "B"], "team": ["a", "b"], "npg_p90": [0.1, 0.2],
                       "home_eligible": [True, True], "player": ["X", "X"], "born": [1, 1]})
    nt = pd.DataFrame({"player_norm": ["x", "ghost"], "born": [1, 2]})
    rows = {r["id"]: r["count"] for r in compute_checks(pool, tables, {"FW": fw}, nt, country_page_html=None)}
    assert rows["namesakes"] == 2 and rows["no_tables"] == 1
    assert rows["split_seasons"] == 1 and rows["missing_born"] == 1 and rows["nt_unmatched"] == 1
    assert rows["women_filtered"] is None
    assert rows["gk_unjoined"] is None  # no keepers table passed
    assert rows["home_league_no_nation"] == 0  # both rows carry a nationality


def test_home_league_no_nation_counts_only_the_home_league():
    """FBref leaves some home-league rows without a nationality (and, in the
    2025/26 tables, only the home league's). Every "own nationals" share
    reads that column as its numerator, so the rows have to be counted and
    the share quoted as a floor -- and a foreign league's blank must not be
    counted, since it moves no home-nation share."""
    pool = pd.DataFrame({"player": ["Jan Novák"], "in_fbref_tables": [True]})
    tables = pd.DataFrame({
        "league": ["CZE-First League", "CZE-First League", "CZE-First League", "DEN-Superliga"],
        "nation": ["CZE", "", None, ""], "born": [2000, 2006, 2004, 2005],
    })
    fw = pd.DataFrame({"player_key": [], "season": [], "pos_group": [], "min": [], "league": [],
                       "team": [], "npg_p90": [], "home_eligible": [], "player": [], "born": []})
    nt = pd.DataFrame({"player_norm": [], "born": []})
    rows = {r["id"]: r["count"] for r in compute_checks(pool, tables, {"FW": fw}, nt, country_page_html=None)}
    assert rows["home_league_no_nation"] == 2


def test_gk_unjoined_counts_keeper_rows_with_no_matching_gk_row():
    """Task 18 fix round 1, item 4: `gk_unjoined` reruns
    `src.goalkeepers.join_keeper_pool` on (league, season, team, player_key)
    -- a keeper row whose team doesn't match any GK row in the players table
    for that league/season/player_key fails to join and is counted."""
    pool = pd.DataFrame({"player": ["Jan Novák"], "in_fbref_tables": [True]})
    tables = pd.DataFrame({
        "league": ["CZE-First League"], "season": ["2025-2026"], "team": ["Sparta"],
        "player_key": ["jan novak|2000"], "pos": ["GK"], "nation": ["CZE"], "born": [2000], "min": [1800],
    })
    keepers = pd.DataFrame({
        "league": ["CZE-First League", "CZE-First League"], "season": ["2025-2026"] * 2,
        "team": ["Sparta", "Slavia"],  # second row's team has no matching GK row -> unjoined
        "player": ["Jan Novák", "Ghost Keeper"], "player_key": ["jan novak|2000", "ghost keeper|1999"],
        "nation": ["CZE", "CZE"], "born": [2000, 1999], "age": [25, 26], "mp": [10, 10], "min": [900, 900],
        "ga": [10, 10], "saves": [30, 30], "sota": [40, 40], "save_pct": [75.0, 75.0], "cs": [2, 2],
    })
    fw = pd.DataFrame({"player_key": [], "season": [], "pos_group": [], "min": [], "league": [], "team": [],
                       "npg_p90": [], "home_eligible": [], "player": [], "born": []})
    nt = pd.DataFrame({"player_norm": [], "born": []})
    rows = {r["id"]: r["count"] for r in compute_checks(
        pool, tables, {"FW": fw}, nt, country_page_html=None, keepers=keepers,
    )}
    assert rows["gk_unjoined"] == 1
