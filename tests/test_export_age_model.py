"""Tests for src/export_age_model.py -- age at export (M1 proper)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.export_age_model import (
    AGE_KNOTS,
    age_curve,
    assemble_output,
    attach_origin,
    beta_summary,
    build_corpus,
    build_design,
    build_first_seasons,
    diagnostics_summary,
    diff_between_ages,
    fit_model,
    home_nation_effect,
    natural_cubic_spline_basis,
    ppc_summary,
    run_lono,
)


def _feats_row(nation, key, player, season, age, npg_q, ast_q, pos="FW", league="ENG-Premier League"):
    return {
        "nation": nation, "player_key": key, "player": player, "pos_group": pos,
        "season": season, "age": age, "npg_p90_quality": npg_q, "ast_p90_quality": ast_q,
        "min": 1800, "league": league,
    }


def test_build_first_seasons_two_seasons_means_and_flag():
    feats = pd.DataFrame([
        _feats_row("CZE", "a|2000", "A", "2022-2023", 22, 0.20, 0.10),
        _feats_row("CZE", "a|2000", "A", "2023-2024", 23, 0.40, 0.20),
        _feats_row("CZE", "a|2000", "A", "2024-2025", 24, 0.90, 0.90),  # 3rd season, must not count
        _feats_row("DEN", "b|2001", "B", "2023-2024", 21, 0.50, 0.10),  # only one qualifying season
    ])
    out = build_first_seasons(feats)
    a = out[out.player_key == "a|2000"].iloc[0]
    assert a.first_season == "2022-2023" and a.age_export == 22.0
    assert a.n_seasons == 2
    assert abs(a.y - ((0.20 + 0.10) + (0.40 + 0.20)) / 2) < 1e-9

    b = out[out.player_key == "b|2001"].iloc[0]
    assert b.n_seasons == 1
    assert abs(b.y - 0.60) < 1e-9


def test_build_first_seasons_collapses_mid_season_split():
    # Two rows same player/season/pos (mid-season transfer between two
    # headline clubs) -- collapse_player_seasons weights by minutes; the
    # collapsed single row is still this player's "first" season.
    feats = pd.DataFrame([
        {"nation": "CZE", "player_key": "a|2000", "player": "A", "pos_group": "FW",
         "season": "2022-2023", "age": 22, "npg_p90_quality": 0.10, "ast_p90_quality": 0.00, "min": 900},
        {"nation": "CZE", "player_key": "a|2000", "player": "A", "pos_group": "FW",
         "season": "2022-2023", "age": 22, "npg_p90_quality": 0.30, "ast_p90_quality": 0.00, "min": 900},
    ])
    out = build_first_seasons(feats)
    assert len(out) == 1
    assert out.iloc[0].n_seasons == 1
    assert abs(out.iloc[0].y - 0.20) < 1e-9  # equal-minutes weighted mean of 0.10 and 0.30


def _tables_row(key, nation, born, league, season, minutes=1000):
    return {"player_key": key, "nation": nation, "born": born, "league": league, "season": season, "min": minutes}


def test_attach_origin_uses_ml_then_uefa_fallback_and_drops_censored():
    rows = pd.DataFrame([
        {"nation": "CZE", "player_key": "a|2000", "player": "A", "pos_group": "FW",
         "first_season": "2023-2024", "age_export": 23.0, "y": 0.5, "n_seasons": 1},
        {"nation": "CZE", "player_key": "b|2001", "player": "B", "pos_group": "MF",
         "first_season": "2020-2021", "age_export": 20.0, "y": 0.3, "n_seasons": 1},  # censored: table's own min season
        {"nation": "CZE", "player_key": "c|2002", "player": "C", "pos_group": "DF",
         "first_season": "2024-2025", "age_export": 24.0, "y": 0.2, "n_seasons": 1},  # no origin league on file
    ])
    tables = pd.DataFrame([
        _tables_row("a|2000", "CZE", 2000, "CZE-First League", "2020-2021"),
        _tables_row("a|2000", "CZE", 2000, "CZE-First League", "2022-2023"),
        _tables_row("a|2000", "CZE", 2000, "ENG-Premier League", "2023-2024"),
        _tables_row("b|2001", "CZE", 2001, "ENG-Premier League", "2020-2021"),
        _tables_row("c|2002", "CZE", 2002, "XXX-Untracked League", "2023-2024"),
        _tables_row("c|2002", "CZE", 2002, "ENG-Premier League", "2024-2025"),
    ])
    m_l_map = {"CZE-First League": 0.41}
    uefa = {"CZE-First League": 0.434, "ENG-Premier League": 1.0}

    out = attach_origin(rows, tables, m_l_map, uefa)
    assert set(out.player_key) == {"a|2000"}  # b censored, c's origin league has no strength estimate
    a = out.iloc[0]
    assert a.origin_league == "CZE-First League"
    assert a.origin_strength == 0.41 and a.origin_source == "m_L"


def test_attach_origin_falls_back_to_uefa_when_m_l_missing():
    rows = pd.DataFrame([
        {"nation": "DEN", "player_key": "d|2000", "player": "D", "pos_group": "FW",
         "first_season": "2023-2024", "age_export": 22.0, "y": 0.4, "n_seasons": 1},
    ])
    tables = pd.DataFrame([
        _tables_row("d|2000", "DEN", 2000, "DEN-Superliga", "2021-2022"),
        _tables_row("d|2000", "DEN", 2000, "DEN-Superliga", "2022-2023"),
        _tables_row("d|2000", "DEN", 2000, "GER-Bundesliga", "2023-2024"),
    ])
    out = attach_origin(rows, tables, {}, {"DEN-Superliga": 0.55})  # no M2 estimate at all
    assert out.iloc[0].origin_source == "uefa"
    assert out.iloc[0].origin_strength == 0.55


def test_build_corpus_end_to_end_toy():
    features_by_group = {
        "FW": pd.DataFrame([
            _feats_row("CZE", "a|2000", "A", "2022-2023", 22, 0.20, 0.10),
            _feats_row("CZE", "a|2000", "A", "2023-2024", 23, 0.40, 0.20),
            _feats_row("SVK", "x|1999", "X", "2020-2021", 19, 0.10, 0.00),  # censored (== table min season)
        ]),
    }
    tables = pd.DataFrame([
        _tables_row("a|2000", "CZE", 2000, "CZE-First League", "2020-2021"),
        _tables_row("a|2000", "CZE", 2000, "CZE-First League", "2021-2022"),
        _tables_row("a|2000", "CZE", 2000, "ENG-Premier League", "2022-2023"),
        _tables_row("x|1999", "SVK", 1999, "ENG-Premier League", "2020-2021"),
    ])
    corpus = build_corpus(features_by_group, tables, ["CZE", "SVK"], ["ENG-Premier League"],
                          {"CZE-First League": 0.41}, {"CZE-First League": 0.434})
    assert len(corpus) == 1
    assert corpus.iloc[0].player_key == "a|2000"
    assert corpus.iloc[0].n_seasons == 2


# --- Spline basis -----------------------------------------------------------


def test_natural_cubic_spline_basis_shape_and_linear_below_first_knot():
    x = np.array([15.0, 17.0, 18.9, 20.0, 22.0, 24.0, 26.0, 30.0])
    basis = natural_cubic_spline_basis(x, AGE_KNOTS)
    assert basis.shape == (len(x), len(AGE_KNOTS) - 1)
    # linear term is just x itself
    assert np.allclose(basis[:, 0], x)
    # a natural spline is linear below the first (boundary) knot: every
    # nonlinear basis column is exactly zero there
    below = x < AGE_KNOTS[0]
    assert np.allclose(basis[below, 1:], 0.0)
    # above the first knot the nonlinear columns are not all zero
    assert not np.allclose(basis[~below, 1:], 0.0)


def test_natural_cubic_spline_basis_no_nans_across_full_age_range():
    x = np.linspace(15.0, 35.0, 41)
    basis = natural_cubic_spline_basis(x, AGE_KNOTS)
    assert np.isfinite(basis).all()


# --- Model: short synthetic fit recovers a known age effect sign -----------


def _synthetic_corpus(n: int = 90, seed: int = 0) -> pd.DataFrame:
    """n < SPLINE_MIN_N -> exercises the quadratic-fallback branch. A clear
    positive age slope and a clear positive strength slope, no nation/
    position effect, small noise -- both signs should be recoverable from a
    short fit."""
    rng = np.random.default_rng(seed)
    age = rng.uniform(18.0, 30.0, n)
    strength = rng.uniform(0.3, 1.0, n)
    pos = rng.choice(["FW", "MF", "DF"], n)
    nation = rng.choice(["AAA", "BBB", "CCC"], n)
    y = 0.10 + 0.03 * (age - 18.0) + 0.50 * strength + rng.normal(0, 0.05, n)
    return pd.DataFrame({
        "nation": nation, "player_key": [f"p{i}" for i in range(n)], "player": [f"P{i}" for i in range(n)],
        "pos_group": pos, "first_season": "2023-2024", "age_export": age, "y": y, "n_seasons": 1,
        "origin_league": "X", "origin_strength": strength, "origin_source": "m_L",
    })


def test_fit_model_recovers_known_age_and_strength_signs():
    corpus = _synthetic_corpus()
    design = build_design(corpus)
    assert design["use_spline"] is False  # n < 150 -> quadratic branch

    idata = fit_model(design, use_strength=True, draws=300, tune=300, chains=2, seed=1, cores=2)
    assert "beta" in idata.posterior

    curve = age_curve(idata, design)
    by_age = {r["age"]: r["median"] for r in curve}
    assert by_age[27] > by_age[19]  # positive age slope recovered

    diff = diff_between_ages(idata, design, 21, 24)
    assert diff["lo"] <= diff["median"] <= diff["hi"]
    assert diff["median"] < 0  # y(21) < y(24): arriving later goes with more, here

    beta = beta_summary(idata, design)
    assert beta["lo"] <= beta["median"] <= beta["hi"]
    assert beta["median"] > 0  # positive strength slope recovered

    diag = diagnostics_summary(idata)
    assert diag["max_rhat"] > 0 and diag["n_divergences"] >= 0
    assert "sigma_n_median" in diag

    ppc = ppc_summary(idata, design)
    assert set(ppc["observed"]) == {"mean", "sd", "p10", "p90"}
    assert abs(ppc["observed"]["mean"] - ppc["replicated"]["mean"]) < 0.3

    home = home_nation_effect(idata, design, "AAA")
    assert home is not None and home["lo"] <= home["median"] <= home["hi"]
    assert home_nation_effect(idata, design, "ZZZ") is None


def test_fit_model_without_strength_has_no_beta():
    corpus = _synthetic_corpus()
    design = build_design(corpus)
    idata = fit_model(design, use_strength=False, draws=200, tune=200, chains=2, seed=1, cores=2)
    assert "beta" not in idata.posterior
    assert beta_summary(idata, design) is None
    diag = diagnostics_summary(idata)  # must not choke on the missing beta
    assert diag["max_rhat"] > 0


def test_run_lono_excludes_home_nation_and_reports_runtime():
    corpus = _synthetic_corpus(n=120, seed=2)
    lono = run_lono(corpus, "AAA", draws=100, tune=100, chains=2, seed=1)
    assert lono["n_excluded"] == int((corpus["nation"] == "AAA").sum())
    assert lono["n"] == len(corpus) - lono["n_excluded"]
    assert lono["diff_21_24"]["lo"] <= lono["diff_21_24"]["median"] <= lono["diff_21_24"]["hi"]
    assert lono["beta"] is not None
    assert lono["runtime_s"] >= 0


def test_run_lono_absent_home_nation_reports_zero_excluded():
    corpus = _synthetic_corpus(n=40, seed=3)
    lono = run_lono(corpus, "ZZZ", draws=50, tune=50, chains=2, seed=1)
    assert lono["n_excluded"] == 0
    assert lono["n"] == len(corpus)


# --- JSON shape --------------------------------------------------------


def test_assemble_output_shape():
    corpus = pd.DataFrame({
        "nation": ["CZE", "CZE", "DEN"], "age_export": [21.0, 23.0, 20.0],
        "n_seasons": [2, 1, 2], "origin_source": ["m_L", "uefa", "m_L"],
    })
    design = {"use_spline": True, "knots": [19, 21, 23, 25]}
    curve = [{"age": 19, "median": 0.3, "lo": 0.2, "hi": 0.4}]
    diff = {"age_a": 21, "age_b": 24, "median": -0.05, "lo": -0.2, "hi": 0.1}
    beta = {"median": 0.4, "lo": 0.1, "hi": 0.7}
    home_effect = {"median": 0.02, "lo": -0.05, "hi": 0.09}
    diagnostics = {"max_rhat": 1.0, "min_ess_bulk": 800.0, "min_ess_tail": 750.0,
                   "n_divergences": 0, "sigma_n_median": 0.05}
    ppc = {"observed": {"mean": 0.3, "sd": 0.2, "p10": 0.1, "p90": 0.5},
          "replicated": {"mean": 0.3, "sd": 0.2, "p10": 0.1, "p90": 0.5}}
    no_strength = {"diagnostics": diagnostics, "home_nation_effect": home_effect, "runtime_s": 12.0}
    lono = {"n_excluded": 2, "n": 1, "diff_21_24": diff, "beta": beta, "diagnostics": diagnostics,
           "runtime_s": 5.0}
    fit_meta = {"n": 3, "runtime_s": 30.0, "runtime_no_strength_s": 28.0, "runtime_lono_s": 5.0}

    out = assemble_output(corpus, design, curve, diff, beta, home_effect, diagnostics, ppc,
                          no_strength, lono, "CZE", fit_meta)
    assert out["n"] == 3
    assert out["age_range"] == {"min": 20.0, "max": 23.0}
    assert out["n_seasons_counts"] == {"2": 2, "1": 1}
    assert out["origin_source_counts"] == {"m_L": 2, "uefa": 1}
    assert out["use_spline"] is True and out["knots"] == [19, 21, 23, 25]
    assert out["home_median_age"] == 22.0  # median of [21, 23]
    assert out["home_code"] == "CZE"
    assert out["beta"] == beta and out["diff_21_24"] == diff
    assert out["no_strength"] == no_strength and out["lono"] == lono
    assert out["fit"] == fit_meta

    # a home nation absent from the corpus -> None, not a KeyError
    out2 = assemble_output(corpus, design, curve, diff, beta, home_effect, diagnostics, ppc,
                           no_strength, lono, "ZZZ", fit_meta)
    assert out2["home_median_age"] is None
