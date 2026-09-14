"""Tests for src/league_strength.py (Task 15).

The synthetic-recovery test actually samples (2 chains x 300 draws, ~600
rows) -- slow relative to the rest of the suite (tens of seconds) but the
only way to check the model recovers a known `m_L` ordering/magnitude
end-to-end. It is module-scoped so the other tests that need a real
InferenceData (diagnostics, PPC, assembly-shape) share the one fit rather
than re-sampling.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import yaml

from src import config
from src.league_strength import (
    MIN_MINUTES,
    assemble_output,
    build_movers,
    build_oos_candidates,
    count_transitions,
    diagnostics_summary,
    fit_model,
    league_strength_table,
    n_transitions_by_league,
    ppc_summary,
    score_predictions,
    spearman_check,
    top_disagreements,
)
from src.references import format_harvard, load_refs

# =============================================================================
# Synthetic recovery
# =============================================================================


def _synthetic_movers(seed: int = 42, n_players: int = 300) -> pd.DataFrame:
    """300 movers, each with one row in league "STRONG" (true beta=0) and one
    in league "WEAK" (true beta=0.7, i.e. an easier scoring environment), all
    MF, age 26 (age_c=0) so age terms don't confound the check. True
    m_WEAK = exp(0 - 0.7) ~= 0.497; m_STRONG = 1 (it's the reference).
    """
    rng = np.random.default_rng(seed)
    alpha_true, beta_strong, beta_weak, sigma_u = -1.2, 0.0, 0.7, 0.8
    u = rng.normal(0.0, sigma_u, size=n_players)
    rows = []
    for i in range(n_players):
        for league, beta in (("STRONG", beta_strong), ("WEAK", beta_weak)):
            minutes = rng.uniform(450, 2700)
            exposure = minutes / 90.0
            lam = np.exp(alpha_true + beta + u[i]) * exposure
            y = rng.poisson(lam)
            ast = rng.integers(0, y + 1) if y > 0 else 0
            npg = y - ast
            rows.append({
                "player_key": f"player{i}", "league": league, "season": "2024-2025",
                "pos_group": "MF", "born": 1998, "min": int(minutes), "npg": int(npg), "ast": int(ast),
            })
    df = pd.DataFrame(rows)
    df["y"] = df["npg"] + df["ast"]
    df["exposure"] = df["min"] / 90.0
    df["age"] = 2024 - df["born"]
    df["age_c"] = (df["age"].astype(float) - 26.0) / 5.0
    return df


@pytest.fixture(scope="module")
def synthetic_fit():
    movers = _synthetic_movers()
    idata = fit_model(movers, draws=300, tune=300, chains=2, target_accept=0.9, seed=42, cores=2)
    return movers, idata


def test_synthetic_recovery_orders_and_bounds_m_l(synthetic_fit):
    movers, idata = synthetic_fit
    transitions_counts = {"STRONG": 300, "WEAK": 300}
    uefa = {"STRONG": 1.0, "WEAK": 0.5}
    table = league_strength_table(idata, transitions_counts, uefa, reference="STRONG")

    row = {r["league"]: r for r in table.to_dict(orient="records")}
    assert row["STRONG"]["median"] == pytest.approx(1.0, abs=1e-9)
    # true m_WEAK = exp(-0.7) ~= 0.497; short sampling on 600 rows, generous band
    assert 0.25 < row["WEAK"]["median"] < 0.80
    assert row["WEAK"]["hdi_lo"] < row["WEAK"]["median"] < row["WEAK"]["hdi_hi"]
    assert row["STRONG"]["median"] > row["WEAK"]["median"]


def test_diagnostics_and_ppc_shapes(synthetic_fit):
    movers, idata = synthetic_fit
    diag = diagnostics_summary(idata)
    for key in ("max_rhat", "min_ess_bulk", "min_ess_tail", "n_divergences",
                "sigma_league_median", "sigma_player_median"):
        assert key in diag
    assert diag["max_rhat"] > 0

    ppc = ppc_summary(idata, movers["y"].to_numpy())
    for side in ("observed", "replicated"):
        assert side in ppc
        for stat in ("zero_share", "mean", "p90"):
            assert stat in ppc[side]
    assert 0.0 <= ppc["observed"]["zero_share"] <= 1.0


# =============================================================================
# JSON assembly shape (pure, no fitting)
# =============================================================================


def test_assemble_output_shape(synthetic_fit):
    movers, idata = synthetic_fit
    table = league_strength_table(idata, {"STRONG": 300, "WEAK": 300}, {"STRONG": 1.0, "WEAK": 0.5},
                                   reference="STRONG")
    diagnostics = diagnostics_summary(idata)
    ppc = ppc_summary(idata, movers["y"].to_numpy())
    oos = {"metrics_season": "2024-2025", "n_candidates": 0, "rows": [], "refit_runtime_s": 0.0}
    spearman = spearman_check(table)
    disagreements = top_disagreements(table)
    fit_meta = {"rows": len(movers), "players": movers["player_key"].nunique(),
                "seasons": movers["season"].nunique(), "runtime_s": 12.3}

    out = assemble_output(table, diagnostics, ppc, oos, spearman, disagreements, fit_meta)
    assert set(out) == {"leagues", "diagnostics", "ppc", "oos", "spearman", "disagreements", "fit"}
    assert isinstance(out["leagues"], list) and out["leagues"]
    for row in out["leagues"]:
        assert set(row) == {"league", "median", "hdi_lo", "hdi_hi", "n_transitions", "uefa"}
    assert out["fit"]["rows"] == len(movers)
    assert out["spearman"]["n"] == 2

    import json
    json.dumps(out)  # round-trips through plain JSON types


def test_spearman_check_and_disagreements_on_a_synthetic_table():
    table = pd.DataFrame([
        {"league": "A", "median": 1.0, "hdi_lo": 0.9, "hdi_hi": 1.1, "n_transitions": 10, "uefa": 1.0},
        {"league": "B", "median": 0.8, "hdi_lo": 0.6, "hdi_hi": 1.0, "n_transitions": 8, "uefa": 0.85},
        {"league": "C", "median": 0.6, "hdi_lo": 0.4, "hdi_hi": 0.8, "n_transitions": 6, "uefa": 0.2},
        {"league": "D", "median": 0.2, "hdi_lo": 0.1, "hdi_hi": 0.4, "n_transitions": 4, "uefa": 0.6},
    ])
    sp = spearman_check(table)
    assert sp["n"] == 4
    assert sp["rho"] is not None

    dis = top_disagreements(table, n=2)
    assert len(dis) == 2
    leagues_flagged = {d["league"] for d in dis}
    assert leagues_flagged == {"C", "D"}  # C and D swap rank 3<->4 most
    for d in dis:
        assert d["rank_diff"] > 0


# =============================================================================
# OOS scorer (pure, toy table)
# =============================================================================


def test_score_predictions_on_a_toy_table():
    df = pd.DataFrame([
        {"y": 10, "exposure": 20.0, "rate_a": 0.5, "rate_b": 0.3},  # perfect for a
        {"y": 4, "exposure": 20.0, "rate_a": 0.2, "rate_b": 0.2},   # perfect for both
        {"y": 0, "exposure": 10.0, "rate_a": 0.1, "rate_b": 0.0},   # perfect for b
    ])
    out = score_predictions(df, {"a": "rate_a", "b": "rate_b"})
    assert list(out["method"]) == ["a", "b"]
    a, b = out.iloc[0], out.iloc[1]
    # a is exactly right on rows 0 and 1 but off on row 2; b is exact on 1 and 2 but off on 0
    assert a["mae"] < 0.05  # only off by 0.01 on row 2 (0.1 vs observed 0.0)
    assert b["mae"] > a["mae"]  # off by 0.2 on row 0 (0.3 vs observed 0.5)
    # both log predictive densities are finite (no crash from a zero-rate row)
    assert np.isfinite(a["log_pred_density"]) and np.isfinite(b["log_pred_density"])


def test_build_oos_candidates_only_flags_league_changes_landing_in_the_metrics_season():
    movers = pd.DataFrame([
        # player 1: A (2023-2024) -> B (2024-2025, metrics) -- a candidate
        {"player_key": "p1", "season": "2023-2024", "league": "A", "pos_group": "MF",
         "min": 900, "npg": 2, "ast": 2, "y": 4, "exposure": 10.0, "age_c": 0.0},
        {"player_key": "p1", "season": "2024-2025", "league": "B", "pos_group": "MF",
         "min": 900, "npg": 3, "ast": 1, "y": 4, "exposure": 10.0, "age_c": 0.2},
        # player 2: stays in A both seasons -- not a candidate
        {"player_key": "p2", "season": "2023-2024", "league": "A", "pos_group": "FW",
         "min": 900, "npg": 5, "ast": 0, "y": 5, "exposure": 10.0, "age_c": 0.0},
        {"player_key": "p2", "season": "2024-2025", "league": "A", "pos_group": "FW",
         "min": 900, "npg": 4, "ast": 1, "y": 5, "exposure": 10.0, "age_c": 0.2},
        # player 3: only has the metrics-season row -- no prior row, not a candidate
        {"player_key": "p3", "season": "2024-2025", "league": "B", "pos_group": "DF",
         "min": 900, "npg": 1, "ast": 0, "y": 1, "exposure": 10.0, "age_c": 0.0},
    ])
    cand = build_oos_candidates(movers, "2024-2025")
    assert list(cand["player_key"]) == ["p1"]
    assert cand.iloc[0]["prev_league"] == "A" and cand.iloc[0]["new_league"] == "B"
    assert cand.iloc[0]["prev_rate"] == pytest.approx((2 + 2) / (900 / 90.0))


# =============================================================================
# Data prep (pure pandas)
# =============================================================================


def test_build_movers_filters_and_restricts_to_movers():
    fw = pd.DataFrame([
        {"player_key": "a|1998", "league": "X", "season": "2024-2025", "born": 1998,
         "min": 900, "npg": 3, "ast": 1, "pos_group": "FW"},
        {"player_key": "a|1998", "league": "Y", "season": "2025-2026", "born": 1998,
         "min": 900, "npg": 2, "ast": 2, "pos_group": "FW"},
        {"player_key": "b|1999", "league": "X", "season": "2024-2025", "born": 1999,
         "min": 900, "npg": 1, "ast": 0, "pos_group": "FW"},  # never moves -- not a mover
        {"player_key": "c|2000", "league": "X", "season": "2024-2025", "born": np.nan,
         "min": 900, "npg": 1, "ast": 0, "pos_group": "FW"},  # born unknown -- excluded
        {"player_key": "d|2001", "league": "X", "season": "2024-2025", "born": 2001,
         "min": 100, "npg": 0, "ast": 0, "pos_group": "FW"},  # below MIN_MINUTES -- excluded
    ])
    movers = build_movers({"FW": fw})
    assert set(movers["player_key"]) == {"a|1998"}
    assert (movers["min"] >= MIN_MINUTES).all()
    assert "y" in movers and "exposure" in movers and "age_c" in movers
    row_2025 = movers[movers["season"] == "2025-2026"].iloc[0]
    assert row_2025["y"] == 4 and row_2025["exposure"] == pytest.approx(10.0)


def test_count_transitions_and_n_by_league():
    movers = pd.DataFrame([
        {"player_key": "a", "season": "2023-2024", "league": "X"},
        {"player_key": "a", "season": "2024-2025", "league": "Y"},
        {"player_key": "a", "season": "2025-2026", "league": "Y"},  # no change, no transition
        {"player_key": "b", "season": "2024-2025", "league": "Y"},
        {"player_key": "b", "season": "2025-2026", "league": "Z"},
    ])
    tr = count_transitions(movers)
    assert len(tr) == 2
    counts = n_transitions_by_league(tr)
    assert counts == {"X": 1, "Y": 2, "Z": 1}


# =============================================================================
# References (Harvard)
# =============================================================================


def test_refs_yaml_loads_with_year_title_and_doi_or_url():
    refs = load_refs()
    assert len(refs) >= 5
    for r in refs:
        assert r.get("year") and r.get("title"), r
        assert r.get("doi") or r.get("url"), r


def test_harvard_formatter_matches_the_brief_example():
    ref = {
        "key": "efron1975", "authors": ["Efron, B.", "Morris, C."], "year": 1975,
        "title": "Data analysis using Stein's estimator and its generalizations",
        "container": "Journal of the American Statistical Association",
        "volume": 70, "issue": 350, "pages": "311-319",
        "doi": "10.1080/01621459.1975.10479864",
    }
    assert format_harvard(ref) == (
        "Efron, B. and Morris, C. (1975) 'Data analysis using Stein's estimator and its "
        "generalizations', Journal of the American Statistical Association, 70(350), pp. 311–319."
    )


def test_config_refs_yaml_file_is_well_formed_and_verifiable():
    path = config.CONFIG_DIR / "refs.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(raw, list) and raw
    keys = [r["key"] for r in raw]
    assert len(keys) == len(set(keys)), "duplicate ref key"
    for r in raw:
        assert r.get("authors") and r.get("year") and r.get("title")
        assert r.get("doi") or r.get("url")


def test_uefa_ratio_direction_stronger_league_means_lower_raw_rate():
    from src.league_strength import uefa_ratio
    moves = pd.DataFrame({"prev_league": ["CZE-First League", "ENG-Premier League"],
                          "new_league": ["ENG-Premier League", "CZE-First League"]})
    r = uefa_ratio(moves, {"ENG-Premier League": 1.0, "CZE-First League": 0.434})
    assert r.iloc[0] < 1 and abs(r.iloc[0] - 0.434) < 1e-9     # up to the PL: fewer goals expected
    assert r.iloc[1] > 1                                       # down to the Czech league: more


def test_oos_candidates_use_the_shrunk_previous_rate_when_available():
    from src.league_strength import build_oos_candidates
    movers = pd.DataFrame({
        "player_key": ["p", "p"], "season": ["2024-2025", "2025-2026"], "league": ["A", "B"],
        "pos_group": ["FW", "FW"], "npg": [0, 3], "ast": [0, 1], "min": [900, 1800],
        "npg_p90_shrunk": [0.12, 0.2], "ast_p90_shrunk": [0.05, 0.1],
        "y": [0, 4], "exposure": [10.0, 20.0], "age_c": [0.0, 0.2],
    })
    out = build_oos_candidates(movers, "2025-2026")
    assert len(out) == 1 and abs(out.iloc[0]["prev_rate"] - 0.17) < 1e-9   # not the raw 0.0
