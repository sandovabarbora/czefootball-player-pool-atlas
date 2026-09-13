import pandas as pd

from src.sensitivity import churn, rank_pool


def test_rank_pool_ranks_within_position_group():
    feats = {
        "FW": pd.DataFrame({
            "player_key": ["f1", "f2"], "player": ["F1", "F2"], "league": ["L1", "L2"],
            "npg_p90_shrunk": [1.0, 0.5], "ast_p90_shrunk": [0.0, 0.0],
        }),
        "DF": pd.DataFrame({
            "player_key": ["d1", "d2"], "player": ["D1", "D2"], "league": ["L1", "L2"],
            "npg_p90_shrunk": [0.1, 0.2], "ast_p90_shrunk": [0.0, 0.0],
        }),
    }
    mult = {"L1": 1.0, "L2": 1.0}
    out = rank_pool(feats, mult)
    fw = out[out.pos_group == "FW"].set_index("player_key")
    df_ = out[out.pos_group == "DF"].set_index("player_key")
    assert fw.loc["f1", "rank"] == 1 and fw.loc["f2", "rank"] == 2
    assert df_.loc["d2", "rank"] == 1 and df_.loc["d1", "rank"] == 2


def test_churn_counts_top10_overlap_and_mean_delta_rank():
    baseline = pd.DataFrame({
        "player_key": ["a", "b", "c"], "pos_group": ["FW", "FW", "FW"], "rank": [1, 2, 3],
    })
    scenario = pd.DataFrame({
        "player_key": ["a", "b", "c"], "pos_group": ["FW", "FW", "FW"], "rank": [2, 1, 3],
    })
    out = churn(baseline, scenario)
    assert out["top10_overlap"] == 3   # same 3 players still in "top 10"
    assert out["top10_churn"] == 0
    # |2-1| + |1-2| + |3-3| = 2, mean over 3 = 0.667
    assert abs(out["mean_delta_rank_top20"] - 2 / 3) < 1e-3


def test_churn_detects_a_dropped_player():
    baseline = pd.DataFrame({
        "player_key": ["a", "b"], "pos_group": ["FW", "FW"], "rank": [1, 2],
    })
    scenario = pd.DataFrame({
        "player_key": ["a", "c"], "pos_group": ["FW", "FW"], "rank": [1, 2],
    })
    out = churn(baseline, scenario)
    assert out["top10_overlap"] == 1
    assert out["top10_churn"] == 1
