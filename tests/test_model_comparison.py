"""Tests for src/model_comparison.py (Task 16).

The Bayesian smoke test actually samples (2 chains x 100 draws, 200
synthetic rows) -- slow relative to the rest of the suite (a few seconds)
but the only way to check the model runs end to end and produces a
sane coverage number.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.model_comparison import (
    ORIGINS,
    build_pairs,
    predict_persistence,
    predict_shrinkage_to_league_mean,
    rolling_origin_split,
)

# =============================================================================
# Rolling-origin split: no leakage
# =============================================================================


def _toy_pairs() -> pd.DataFrame:
    """One row per (season_t -> target_season) pair, spanning four seasons."""
    rows = []
    for i, (t, tgt) in enumerate([
        ("2020-2021", "2021-2022"), ("2021-2022", "2022-2023"),
        ("2022-2023", "2023-2024"), ("2020-2021", "2021-2022"),
    ]):
        rows.append({"player_key": f"p{i}", "pos_group": "MF", "league": "X",
                     "season_t": t, "target_season": tgt, "value_t": 1.0, "target": 1.2,
                     "npg_p90_shrunk": 0.1, "ast_p90_shrunk": 0.1, "min_share": 0.8,
                     "age": 24.0, "cards_p90": 0.1, "league_multiplier": 1.0})
    return pd.DataFrame(rows)


def test_rolling_origin_split_has_no_leakage():
    pairs = _toy_pairs()
    for origin in ("2021-2022", "2022-2023", "2023-2024"):
        train, test = rolling_origin_split(pairs, origin)
        assert (test["target_season"] == origin).all()
        assert (train["target_season"] < origin).all()


def test_rolling_origin_split_first_origin_has_no_train_data():
    """The corpus's earliest feature season (2020-2021) makes its first
    target season (2021-2022) the very first pair possible -- no pair can
    have an earlier target season, so origin 1's train set is empty. A real
    corpus limitation, not a bug (see module docstring)."""
    pairs = _toy_pairs()
    train, _ = rolling_origin_split(pairs, "2021-2022")
    assert train.empty


def test_origins_constant_is_five_seasons_in_order():
    assert ORIGINS == ["2021-2022", "2022-2023", "2023-2024", "2024-2025", "2025-2026"]


# =============================================================================
# Baselines: known values
# =============================================================================


def test_predict_persistence_returns_value_t():
    test = pd.DataFrame({"value_t": [0.5, 1.2, 0.0]})
    pred = predict_persistence(test)
    assert list(pred) == [0.5, 1.2, 0.0]


def test_predict_shrinkage_to_league_mean_on_known_values():
    train = pd.DataFrame({
        "league": ["A"] * 10 + ["B"] * 2,
        "target": [1.0] * 10 + [3.0, 3.0],
    })
    test = pd.DataFrame({"league": ["A", "B", "C"]})
    pred = predict_shrinkage_to_league_mean(train, test, k=10)
    global_mean = train["target"].mean()  # (10*1 + 2*3)/12 = 16/12
    # league A: n=10, weight=10/20=0.5 -> 0.5*1.0 + 0.5*global_mean
    expected_a = 0.5 * 1.0 + 0.5 * global_mean
    assert pred.iloc[0] == pytest.approx(expected_a)
    # league B: n=2, weight=2/12 -> mostly the global mean
    expected_b = (2 / 12) * 3.0 + (10 / 12) * global_mean
    assert pred.iloc[1] == pytest.approx(expected_b)
    # league C: unseen in train -> falls back to the global mean
    assert pred.iloc[2] == pytest.approx(global_mean)


def test_predict_shrinkage_to_league_mean_falls_back_when_train_is_empty():
    train = pd.DataFrame(columns=["league", "target"])
    test = pd.DataFrame({"league": ["A", "B"], "value_t": [0.4, 0.6]})
    pred = predict_shrinkage_to_league_mean(train, test, k=10)
    # cold start (origin 1): no historical target data at all, fall back to
    # the test season's own known value_t mean (not the unknown target)
    for v in pred:
        assert v == pytest.approx(0.5)


def test_rmse_mae_on_known_values():
    from src.model_comparison import mae, rmse
    y_true = np.array([1.0, 2.0, 3.0])
    y_pred = np.array([1.0, 2.0, 5.0])
    assert mae(y_true, y_pred) == pytest.approx(2 / 3)
    assert rmse(y_true, y_pred) == pytest.approx(np.sqrt((0 + 0 + 4) / 3))


# =============================================================================
# build_pairs: pure pandas
# =============================================================================


def test_build_pairs_matches_consecutive_seasons_and_filters_minutes():
    fw = pd.DataFrame([
        {"player_key": "a|1998", "league": "X", "season": "2024-2025", "pos_group": "FW",
         "min": 900, "age": 26.0, "npg_p90_shrunk": 0.3, "ast_p90_shrunk": 0.1,
         "min_share": 0.8, "cards_p90": 0.1, "league_multiplier": 1.0,
         "npg_p90_quality": 0.3, "ast_p90_quality": 0.1},
        {"player_key": "a|1998", "league": "X", "season": "2025-2026", "pos_group": "FW",
         "min": 900, "age": 27.0, "npg_p90_shrunk": 0.4, "ast_p90_shrunk": 0.2,
         "min_share": 0.9, "cards_p90": 0.1, "league_multiplier": 1.0,
         "npg_p90_quality": 0.4, "ast_p90_quality": 0.2},
        {"player_key": "b|1999", "league": "X", "season": "2024-2025", "pos_group": "FW",
         "min": 100, "age": 22.0, "npg_p90_shrunk": 0.1, "ast_p90_shrunk": 0.0,   # below 450 -- excluded
         "min_share": 0.2, "cards_p90": 0.0, "league_multiplier": 1.0,
         "npg_p90_quality": 0.1, "ast_p90_quality": 0.0},
        {"player_key": "b|1999", "league": "X", "season": "2025-2026", "pos_group": "FW",
         "min": 900, "age": 23.0, "npg_p90_shrunk": 0.2, "ast_p90_shrunk": 0.0,
         "min_share": 0.5, "cards_p90": 0.0, "league_multiplier": 1.0,
         "npg_p90_quality": 0.2, "ast_p90_quality": 0.0},
        {"player_key": "c|2000", "league": "X", "season": "2025-2026", "pos_group": "FW",  # no prior season
         "min": 900, "age": 24.0, "npg_p90_shrunk": 0.2, "ast_p90_shrunk": 0.0,
         "min_share": 0.5, "cards_p90": 0.0, "league_multiplier": 1.0,
         "npg_p90_quality": 0.2, "ast_p90_quality": 0.0},
    ])
    pairs = build_pairs({"FW": fw})
    assert list(pairs["player_key"]) == ["a|1998"]
    row = pairs.iloc[0]
    assert row["target_season"] == "2025-2026"
    assert row["value_t"] == pytest.approx(0.3 + 0.1)
    assert row["target"] == pytest.approx(0.4 + 0.2)
    assert row["age"] == pytest.approx(26.0)


# =============================================================================
# Bayesian model smoke test
# =============================================================================


def _synthetic_pairs(n: int = 200, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    leagues = np.array(["A", "B"])
    league = rng.choice(leagues, size=n)
    league_multiplier = np.where(league == "A", 1.0, 0.6)
    pos = rng.choice(["FW", "MF", "DF"], size=n)
    npg = rng.normal(0.3, 0.1, size=n).clip(min=0)
    ast = rng.normal(0.15, 0.05, size=n).clip(min=0)
    age = rng.uniform(18, 34, size=n)
    min_share = rng.uniform(0.3, 1.0, size=n)
    cards = rng.uniform(0.0, 0.3, size=n)
    player_key = np.array([f"p{i % 60}" for i in range(n)])
    noise = rng.normal(0, 0.1, size=n)
    target = (npg + ast) * league_multiplier + noise
    return pd.DataFrame({
        "player_key": player_key, "pos_group": pos, "league": league,
        "target_season": "2024-2025", "value_t": npg + ast,
        "npg_p90_shrunk": npg, "ast_p90_shrunk": ast, "min_share": min_share,
        "age": age, "cards_p90": cards, "league_multiplier": league_multiplier,
        "target": target,
    })


def test_bayesian_smoke_coverage_is_plausible():
    from src.model_comparison import fit_bayesian, predict_bayesian

    train = _synthetic_pairs(seed=1)
    test = _synthetic_pairs(seed=2)
    idata, meta = fit_bayesian(train, draws=100, tune=100, chains=2, seed=42)
    point, lo, hi = predict_bayesian(idata, test, meta)
    assert len(point) == len(test)
    coverage = float(((test["target"].to_numpy() >= lo) & (test["target"].to_numpy() <= hi)).mean())
    assert 0.6 <= coverage <= 1.0
    assert np.isfinite(point).all()


# =============================================================================
# JSON shape
# =============================================================================


def test_assemble_output_shape():
    from src.model_comparison import assemble_output

    rows = [{"model": "persistence", "origin": "2021-2022", "n_test": 10, "rmse": 0.5, "mae": 0.4,
             "coverage90": None}]
    pooled = [{"model": "persistence", "n_test": 10, "rmse": 0.5, "mae": 0.4, "coverage90": None}]
    out = assemble_output(target="npg_p90_quality + ast_p90_quality (season t+1)",
                          origins=ORIGINS, rows=rows, pooled=pooled,
                          winner_pooled="persistence", notes=["a note"])
    assert set(out) == {"target", "origins", "rows", "pooled", "winner_pooled", "notes"}
    assert out["origins"] == ORIGINS
    assert out["winner_pooled"] == "persistence"
    import json
    json.dumps(out)  # round-trips through plain JSON types
