import pandas as pd
from src.data_quality import compute_checks


def test_checks_count_split_seasons_and_no_tables():
    pool = pd.DataFrame({"player": ["Ladislav Krejčí", "Ladislav Krejčí", "Jan Novák"], "in_fbref_tables": [True, True, False]})
    tables = pd.DataFrame({"nation": ["CZE", "CZE"], "born": [1999, pd.NA]})
    fw = pd.DataFrame({"player_key": ["x|1", "x|1"], "season": ["2025-2026"] * 2, "pos_group": ["FW"] * 2,
                       "min": [500, 400], "league": ["A", "B"], "team": ["a", "b"], "npg_p90": [0.1, 0.2],
                       "czech_eligible": [True, True], "player": ["X", "X"], "born": [1, 1]})
    nt = pd.DataFrame({"player_norm": ["x", "ghost"], "born": [1, 2]})
    rows = {r["id"]: r["count"] for r in compute_checks(pool, tables, {"FW": fw}, nt, country_page_html=None)}
    assert rows["namesakes"] == 2 and rows["no_tables"] == 1
    assert rows["split_seasons"] == 1 and rows["missing_born"] == 1 and rows["nt_unmatched"] == 1
    assert rows["women_filtered"] is None
