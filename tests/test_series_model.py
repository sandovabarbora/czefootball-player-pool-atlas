"""Tests for src/series_model.py (Task 19): the change-point model, the
rolling-origin backtest and the one forecast on the 26-season Big-5 series.

The synthetic-recovery and forecast-coverage tests actually sample (short
NUTS runs on a tiny series, T <= 26) -- slower than the pure-function tests
but the only way to check the marginalised change point and the forecast
interval behave end to end.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.series_model import (
    TAU_MARGIN,
    assemble_output,
    backtest_origins,
    break_summary,
    extract_series,
    fit_change_point,
    fit_local_level,
    forecast_next,
    next_season_label,
    rolling_origin_backtest_split,
    run_backtest,
    tau_grid_for,
    tau_posterior,
)

SEASONS_26 = [f"{2000 + i}-{2001 + i}" for i in range(26)]  # "2000-2001" .. "2025-2026"


# =============================================================================
# Pure data/index helpers
# =============================================================================


def test_extract_series_reads_one_countrys_counts():
    big5 = {"countries": {"CZE": {"n": [21, 17, 24]}, "DEN": {"n": [16, 20, 19]}}}
    assert list(extract_series(big5, "CZE")) == [21.0, 17.0, 24.0]
    assert list(extract_series(big5, "DEN")) == [16.0, 20.0, 19.0]


def test_next_season_label():
    assert next_season_label("2025-2026") == "2026-2027"
    assert next_season_label("2000-2001") == "2001-2002"


def test_tau_grid_for_margin_three_on_a_26_season_series():
    grid = tau_grid_for(26)
    assert grid[0] == TAU_MARGIN
    assert grid[-1] == 26 - TAU_MARGIN
    assert len(grid) == 26 - 2 * TAU_MARGIN + 1


def test_tau_grid_for_rejects_a_too_short_series():
    with pytest.raises(ValueError):
        tau_grid_for(2 * TAU_MARGIN)


def test_backtest_origins_span_2010_11_to_2024_25():
    origins = backtest_origins(SEASONS_26)
    assert origins[0] == "2010-2011"
    assert origins[-1] == "2024-2025"
    assert len(origins) == 15


# =============================================================================
# Backtest split: no leakage
# =============================================================================


def test_backtest_split_never_uses_future_seasons():
    for origin in backtest_origins(SEASONS_26):
        train_idx, next_idx = rolling_origin_backtest_split(SEASONS_26, origin)
        origin_idx = SEASONS_26.index(origin)
        assert max(train_idx) == origin_idx
        assert next_idx == origin_idx + 1
        assert all(i <= origin_idx for i in train_idx)


def test_backtest_split_raises_on_the_series_last_season():
    with pytest.raises(ValueError):
        rolling_origin_backtest_split(SEASONS_26, SEASONS_26[-1])


# =============================================================================
# Change point: synthetic recovery
# =============================================================================


def _synthetic_step_series(seed: int = 0) -> np.ndarray:
    """26 seasons, Poisson noise around a level that steps from 20 to 10 at
    t = 14 (0-indexed) -- the brief's synthetic-recovery fixture."""
    rng = np.random.default_rng(seed)
    levels = np.array([20.0] * 14 + [10.0] * 12)
    return rng.poisson(levels).astype("float64")


def test_change_point_recovers_the_known_break_within_one_season():
    y = _synthetic_step_series()
    idata, tau_grid = fit_change_point(y, draws=300, tune=300, chains=2, seed=123)
    probs = tau_posterior(idata, y, tau_grid)
    mode_tau = int(tau_grid[int(np.argmax(probs))])
    assert abs(mode_tau - 14) <= 1


def test_break_summary_shape_and_a_downward_step():
    y = _synthetic_step_series()
    idata, tau_grid = fit_change_point(y, draws=300, tune=300, chains=2, seed=123)
    seasons = [f"{2000 + i}-{2001 + i}" for i in range(len(y))]
    summary = break_summary(idata, y, tau_grid, seasons)
    assert len(summary["top"]) == 3
    assert set(summary["top"][0]) == {"season", "prob"}
    assert summary["top"][0]["prob"] >= summary["top"][1]["prob"] >= summary["top"][2]["prob"]
    assert {"median", "lo", "hi"} <= set(summary["delta_factor"])
    # level drops 20 -> 10 at the break: the multiplicative factor is < 1
    assert summary["delta_factor"]["median"] < 1.0
    assert summary["sigma"] > 0


def test_two_breaks_recover_a_rise_and_a_fall():
    """The 36-season fit (2026-09-21): a rise at index 10 (5 -> 25) and a
    fall at index 24 (25 -> 12); the summary's `break` is the fall, `rise`
    the rise, each within a season of the truth and with the right sign."""
    from src.series_model import tau_pairs_for

    rng = np.random.default_rng(7)
    y = rng.poisson(np.r_[np.full(10, 5.0), np.full(14, 25.0), np.full(12, 12.0)]).astype("float64")
    idata, grid = fit_change_point(y, n_breaks=2, draws=300, tune=300, chains=2, seed=3)
    assert grid.shape == tau_pairs_for(len(y)).shape and grid.shape[1] == 2
    seasons = [f"{1990 + i}-{1991 + i}" for i in range(len(y))]
    summary = break_summary(idata, y, grid, seasons)
    assert summary["n_breaks"] == 2 and summary["fall_is_a_fall"]
    assert abs(seasons.index(summary["top"][0]["season"]) - 24) <= 1
    assert abs(seasons.index(summary["rise"]["top"][0]["season"]) - 10) <= 1
    assert summary["delta_factor"]["median"] < 1.0 < summary["rise"]["delta_factor"]["median"]
    assert summary["pair_top"][0]["seasons"] == [summary["rise"]["top"][0]["season"], summary["top"][0]["season"]]


# =============================================================================
# Forecast: interval coverage on a synthetic random walk
# =============================================================================


def _synthetic_random_walk(seed: int, t: int = 26, level0: float = 15.0, sigma: float = 0.08) -> tuple[np.ndarray, float]:
    """A synthetic Poisson-observed random walk (no break, so it is a fair
    test of the *plain* local level's own forecast, not the change-point
    model): returns the observed series `y[0:t]` and the true next-step
    mean count (drawn one more random-walk step past the series)."""
    rng = np.random.default_rng(seed)
    log_level = np.log(level0)
    log_levels = [log_level]
    for _ in range(t):
        log_level += rng.normal(0.0, sigma)
        log_levels.append(log_level)
    y = rng.poisson(np.exp(log_levels[:t])).astype("float64")
    true_next_mean = np.exp(log_levels[t])
    return y, true_next_mean


def test_forecast_interval_covers_the_true_next_value_most_of_the_time():
    """20 independent synthetic random-walk series; the 90% forecast
    interval should contain a draw from the true next-step distribution at
    least 70% of the time (the brief's coverage bar -- a strict 90% target
    over only 20 draws would be too noisy a bar for a unit test)."""
    covered = 0
    n_reps = 20
    for i in range(n_reps):
        y, true_next_mean = _synthetic_random_walk(seed=1000 + i)
        idata = fit_local_level(y, draws=300, tune=300, chains=2, seed=2000 + i)
        median, lo, hi = forecast_next(idata, seed=3000 + i)
        rng = np.random.default_rng(4000 + i)
        actual_next = rng.poisson(true_next_mean)
        if lo <= actual_next <= hi:
            covered += 1
    assert covered / n_reps >= 0.7


# =============================================================================
# Backtest run + JSON assembly shape
# =============================================================================


def test_run_backtest_on_a_short_span_scores_model_and_naive():
    """A short, cheap slice of origins (three, not the full fifteen) to
    check `run_backtest`'s own wiring -- pooled MAE/coverage, one row per
    origin, no leakage (reuses the split already proven leak-free above)."""
    seasons = SEASONS_26
    y, _ = _synthetic_random_walk(seed=7)
    origins = seasons[10:13]  # three origins, cheap

    result = run_backtest(seasons, y, start=origins[0], end=origins[-1], draws=200, tune=200, chains=2, seed=42)

    assert len(result["rows"]) == 3
    for row in result["rows"]:
        assert {"origin", "next_season", "actual", "median", "lo", "hi", "naive",
                "mae_model", "mae_naive", "covered"} <= set(row)
    assert {"mae_model", "mae_naive", "coverage90"} == set(result["pooled"])


def test_assemble_output_shape():
    result = assemble_output(
        break_result={"top": [{"season": "2015-2016", "prob": 0.4}], "delta_factor": {"median": 0.8, "lo": 0.6, "hi": 1.0}, "sigma": 0.1},
        contrast={"DEN": {"top": [], "delta_factor": {"median": 1.0, "lo": 0.9, "hi": 1.1}, "sigma": 0.1}},
        backtest={"rows": [], "pooled": {"mae_model": 1.0, "mae_naive": 1.5, "coverage90": 0.9}},
        forecast={"CZE": {"season": "2026-2027", "median": 10.0, "lo": 6.0, "hi": 14.0}},
        diagnostics={"max_rhat": 1.0, "n_divergences": 0},
    )
    assert set(result) == {"break", "contrast", "backtest", "forecast", "diagnostics"}
    assert result["forecast"]["CZE"]["season"] == "2026-2027"
