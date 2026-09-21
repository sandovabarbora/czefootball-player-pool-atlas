"""When did the train leave: a Bayesian change point, a rolling-origin
backtest and one aggregate forecast on the Big-5 series (36 seasons, 1990/91 on) (Task 19,
spec §2 M4 + §4c).

Question. Slide 7 already shows the series (Task 13a, `src.big5_series`) and
says where it peaked and where it stands now; this module answers the
question underneath the picture -- *when* did the level actually change,
how sure is that date, and what does an honest one-step-ahead forecaster
(no change point, because a forecaster standing at season t does not know
whether t is on one side of a break or the other) do with this series.

Model 1: local level with one change point in the level (`fit_change_point`).
Poisson counts, `n_t ~ Poisson(lambda_t)`, `log lambda_t = mu_t`. `mu_t` is a
Gaussian random walk (the local-level state-space form, Durbin and Koopman,
2012), `mu_t = mu_{t-1} + eps_t`, `eps_t ~ Normal(0, sigma)`,
`sigma ~ HalfNormal(0.2)`, plus a one-off step `delta ~ Normal(0, 1)` added
to every `mu_t` from an unknown break season `tau` onward:
`mu_t += delta * 1[t >= tau]`. `tau ~ DiscreteUniform(margin, T-margin)`
(`margin = 3`: a break needs at least three seasons of evidence on each
side to be identifiable at all).

Marginalising tau. `tau` is discrete and NUTS only moves continuous
parameters, so it is not sampled directly (no `pm.Mixture`, per the brief):
the random-walk path `mu_base_t = mu_0 + cumsum(eps)_t` does not depend on
`tau` at all, only the step's placement does, so the whole per-season
Poisson log-likelihood can be evaluated at every candidate `tau` from the
*same* continuous draw and combined with `pm.math.logsumexp` into one
scalar `pm.Potential` -- the standard way to marginalise a discrete
parameter out of a model to let a continuous sampler handle the rest
(Gelman et al., 2013, on discrete-parameter marginalisation; Adams and
MacKay, 2007, is the canonical Bayesian-changepoint reference, though their
online/sequential setting differs from this batch, single-changepoint one).
The marginal posterior over `tau` itself is then recovered *after*
sampling, per posterior draw of the continuous parameters: normalise the
per-candidate log-likelihoods (softmax over `tau`) and average the
resulting weights over draws (`tau_posterior`) -- the standard move for
reporting a marginalised discrete parameter's own posterior.

Model 2: plain local level, no change point (`fit_local_level`) -- "the
honest forecaster": at any real origin season, whether a break has already
happened is exactly the unknown the forecaster does not get to use. Used
for both the rolling-origin backtest and the report's one forecast.

Rolling-origin backtest (`run_backtest`, Hyndman and Athanasopoulos, 2021,
chapter 5.10): for each origin season t in `backtest_origins()` (2010/11 to
2024/25, the home nation's series only), fit the plain local level on
seasons up to and including t, forecast `n_{t+1}` by one-step-ahead
posterior-predictive simulation (`forecast_next`), score against the naive
"same as last season" baseline by MAE and 90% interval coverage.

The one forecast (`main`): next season's count for the home nation and its
two `series_contrast` peers, median + 90% interval, from the plain local
level fitted on the full series -- reported as a methods demonstration on
a count, explicitly not a statement about any player (see the report
template's forecast sentence).

Output: `data/processed/<nation>/series_model.json` and figure
`outputs/<nation>/series_model.svg`.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import arviz as az
import numpy as np
import pymc as pm
import pytensor.tensor as pt
from scipy.special import gammaln

from src import config
from src.logging_setup import setup as logging_setup

LOG = logging.getLogger(__name__)

TAU_MARGIN = 3
"""tau ~ DiscreteUniform(TAU_MARGIN, T - TAU_MARGIN): at least this many
seasons of evidence required on each side of a candidate break for it to
be identifiable at all."""

BACKTEST_START = "2010-2011"
BACKTEST_END = "2024-2025"

# Runtime budget (T = 36, a tiny series): every fit below is 2 chains, short
# draws/tune -- the backtest alone refits ~15 times, so each fit needs to
# stay well under a second of sampling for the whole module to land inside
# the < 5 min target.
DRAWS = 500
TUNE = 500
CHAINS = 2

N_BREAKS = 2
"""Breaks in the home-nation fit. On the 36-season series (1990/91 on) a
single step is misspecified: the count rises through the 1990s and falls
after the 2000s plateau, and one step lands wherever it buys the most
likelihood, which is the rise. Two ordered steps date both; the report's
"break" is the one that lowers the level, the other is reported as the
rise. The backtest and forecast stay on the plain local level either way."""


# =============================================================================
# Data
# =============================================================================


def extract_series(big5_series: dict[str, Any], code: str) -> np.ndarray:
    """The season-by-season player count `n` for one country code, as a
    float array (Poisson counts, but float64 for PyTensor's sake)."""
    return np.asarray(big5_series["countries"][code]["n"], dtype="float64")


def next_season_label(season: str) -> str:
    """'2025-2026' -> '2026-2027': the season label one year past `season`."""
    start, end = (int(x) for x in season.split("-"))
    return f"{start + 1}-{end + 1}"


def tau_grid_for(t: int, margin: int = TAU_MARGIN) -> np.ndarray:
    """The support of `tau ~ DiscreteUniform(margin, T - margin)`: season
    *indices* (0-based, into the `T`-length series) a candidate break could
    sit at, inclusive on both ends."""
    if t < 2 * margin + 1:
        raise ValueError(f"series too short ({t} seasons) for a margin of {margin} on each side")
    return np.arange(margin, t - margin + 1)


def tau_pairs_for(t: int, margin: int = TAU_MARGIN) -> np.ndarray:
    """The support of two ordered breaks `tau1 < tau2`, each at least
    `margin` seasons from the ends and from each other, as an (n_pairs, 2)
    array of season indices -- the two-break model's discrete grid, the
    same way `tau_grid_for` is the one-break model's."""
    g = tau_grid_for(t, margin)
    pairs = [(a, b) for a in g for b in g if b - a >= margin]
    if not pairs:
        raise ValueError(f"series too short ({t} seasons) for two breaks with a margin of {margin}")
    return np.array(pairs, dtype=int)


def _step_matrix(t: int, tau_grid: np.ndarray) -> np.ndarray:
    """(T, n_candidates, n_breaks) indicator: season t is at or after the
    k-th break of candidate c. A 1-D grid is one break per candidate."""
    grid = tau_grid.reshape(len(tau_grid), -1)  # (n_candidates, n_breaks)
    return (np.arange(t)[:, None, None] >= grid[None, :, :]).astype("float64")


def backtest_origins(seasons: list[str], start: str = BACKTEST_START, end: str = BACKTEST_END) -> list[str]:
    """Origin season labels from `start` to `end` inclusive, both must be in
    `seasons` (raises `ValueError` via `list.index` otherwise -- a real
    corpus/config mismatch, not something to fail silently on)."""
    i0, i1 = seasons.index(start), seasons.index(end)
    return seasons[i0:i1 + 1]


def rolling_origin_backtest_split(seasons: list[str], origin: str) -> tuple[list[int], int]:
    """(train_indices, next_index) for one backtest origin: `train_indices`
    are every season index up to and including `origin`'s, `next_index` is
    the index of the season being forecast (`origin`'s successor). Raises
    `ValueError` if `origin` is the series' last season (nothing to score
    against) -- `backtest_origins`'s own `end` bound keeps this from
    happening in `main`, but the function itself does not assume it.
    """
    idx = seasons.index(origin)
    if idx + 1 >= len(seasons):
        raise ValueError(f"no season after {origin!r} in {seasons!r} to forecast")
    return list(range(0, idx + 1)), idx + 1


# =============================================================================
# Model 1: local level with one (marginalised) change point
# =============================================================================


def _mu0_prior(y: np.ndarray) -> float:
    """A weakly-informative centre for `mu_0`: log of the series' own mean
    count (floored at 1 so an all-zero synthetic series in a test doesn't
    take `log(0)`)."""
    return float(np.log(max(float(y.mean()), 1.0)))


def fit_change_point(
    y: np.ndarray, *, tau_grid: np.ndarray | None = None, n_breaks: int = 1, draws: int = DRAWS, tune: int = TUNE,
    chains: int = CHAINS, target_accept: float = 0.95, seed: int | None = None, progressbar: bool = False,
    cores: int | None = None,
) -> tuple[az.InferenceData, np.ndarray]:
    """Fit the local level + one marginalised change point on `y` (see
    module docstring). Returns `(idata, tau_grid)`; `idata.posterior` carries
    `mu0`, `sigma`, `delta` and the full state path `mu_base` (the random
    walk *without* the step -- `tau_posterior`/`forecast_next` add the step
    back in where needed). `tau` itself is not a variable in `idata` -- it
    was marginalised out of the model, not sampled -- `tau_posterior`
    recovers its posterior from `mu_base`/`delta` after the fact.
    """
    seed = config.RANDOM_SEED if seed is None else seed
    t = len(y)
    if tau_grid is None:
        tau_grid = tau_grid_for(t) if n_breaks == 1 else tau_pairs_for(t)
    step = _step_matrix(t, tau_grid)  # (T, n_candidates, n_breaks)
    n_breaks = step.shape[2]
    log_prior_tau = -np.log(len(tau_grid))

    with pm.Model():
        mu0 = pm.Normal("mu0", mu=_mu0_prior(y), sigma=1.0)
        sigma = pm.HalfNormal("sigma", 0.2)
        z_eps = pm.Normal("z_eps", 0.0, 1.0, shape=t - 1)
        eps = pm.Deterministic("eps", z_eps * sigma)
        mu_base = pm.Deterministic("mu_base", mu0 + pt.concatenate([[0.0], pt.cumsum(eps)]))
        # one step per break; with one break this is the scalar delta of the original model
        delta = pm.Normal("delta", 0.0, 1.0, shape=n_breaks) if n_breaks > 1 else pm.Normal("delta", 0.0, 1.0)

        steps = pt.tensordot(pt.as_tensor(step), delta, axes=[[2], [0]]) if n_breaks > 1 else delta * step[:, :, 0]
        mu_tau = mu_base[:, None] + steps  # (T, n_candidates): the level under each candidate break
        lam_tau = pm.math.exp(mu_tau)
        logp_tau = pm.logp(pm.Poisson.dist(mu=lam_tau), y[:, None]).sum(axis=0)  # (n_tau,)
        pm.Potential("y_marginal", pm.math.logsumexp(logp_tau + log_prior_tau))

        idata = pm.sample(draws=draws, tune=tune, chains=chains, target_accept=target_accept,
                          random_seed=seed, progressbar=progressbar, cores=cores or min(chains, 4))
    return idata, tau_grid


def tau_log_likelihoods(y: np.ndarray, mu_base: np.ndarray, delta: np.ndarray, tau_grid: np.ndarray) -> np.ndarray:
    """Poisson log-likelihood of `y` under each candidate break in
    `tau_grid`, one row per posterior draw. `mu_base` is (n_draws, T) -- the
    random-walk level *without* the step, `delta` is (n_draws,). Pure numpy
    (no PyTensor), so it is the piece `tau_posterior` and the change-point
    recovery test can exercise directly without refitting a model.
    """
    t = mu_base.shape[1]
    step = _step_matrix(t, tau_grid)  # (T, n_candidates, n_breaks)
    delta = np.asarray(delta).reshape(mu_base.shape[0], -1)  # (draws, n_breaks)
    mu_tau = mu_base[:, :, None] + np.einsum("tcb,db->dtc", step, delta)  # (draws, T, n_candidates)
    lam_tau = np.exp(mu_tau)
    logp = y[None, :, None] * np.log(lam_tau) - lam_tau - gammaln(y[None, :, None] + 1.0)
    return logp.sum(axis=1)  # (n_draws, n_tau)


def tau_posterior(idata: az.InferenceData, y: np.ndarray, tau_grid: np.ndarray) -> np.ndarray:
    """Marginal posterior `p(tau | y)` over `tau_grid`: per posterior draw,
    normalise (softmax) the candidate log-likelihoods from
    `tau_log_likelihoods`, then average the resulting weights over draws --
    the standard way to recover a discrete parameter's own posterior once
    it has been marginalised out of the sampled model (see module
    docstring)."""
    mu_base = idata.posterior["mu_base"].values.reshape(-1, len(y))
    delta = _delta_draws(idata)
    loglik = tau_log_likelihoods(y, mu_base, delta, tau_grid)  # (n_draws, n_tau)
    loglik -= loglik.max(axis=1, keepdims=True)  # softmax stability
    weights = np.exp(loglik)
    weights /= weights.sum(axis=1, keepdims=True)
    return weights.mean(axis=0)  # (n_tau,), sums to 1


def _delta_draws(idata: az.InferenceData) -> np.ndarray:
    """(n_draws,) for the one-break model, (n_draws, n_breaks) for two."""
    d = idata.posterior["delta"].values
    return d.reshape(-1) if d.ndim == 2 else d.reshape(-1, d.shape[-1])


def marginal_over_breaks(tau_grid: np.ndarray, probs: np.ndarray, t: int) -> list[np.ndarray]:
    """From the posterior over candidate pairs, the marginal posterior of
    each break over season indices 0..T-1 (one array per break)."""
    grid = tau_grid.reshape(len(tau_grid), -1)
    out = []
    for k in range(grid.shape[1]):
        m = np.zeros(t)
        np.add.at(m, grid[:, k], probs)
        out.append(m)
    return out


def top_tau(tau_grid: np.ndarray, probs: np.ndarray, seasons: list[str], n: int = 3) -> list[dict[str, Any]]:
    """The `n` highest-probability candidate break seasons, `{season, prob}`."""
    order = np.argsort(-probs)[:n]
    return [{"season": seasons[int(tau_grid[i])], "prob": round(float(probs[i]), 4)} for i in order]


def _hdi(samples: np.ndarray, prob: float = 0.9) -> tuple[float, float]:
    """Highest-density interval of a 1-D sample (same construction as
    `src.league_strength._hdi` -- duplicated rather than imported so this
    module doesn't pull in `league_strength`'s PyMC model just for one
    small numeric helper)."""
    s = np.sort(np.asarray(samples))
    n = len(s)
    n_in = max(int(np.floor(prob * n)), 1)
    n_out = n - n_in
    if n_out <= 0:
        return float(s[0]), float(s[-1])
    widths = s[n_in:] - s[:n_out]
    lo = int(np.argmin(widths))
    return float(s[lo]), float(s[lo + n_in])


def break_summary(idata: az.InferenceData, y: np.ndarray, tau_grid: np.ndarray, seasons: list[str]) -> dict[str, Any]:
    """`{top, delta_factor, sigma}` for the report/JSON: the top-3 candidate
    break seasons with their posterior probability, the step as a
    multiplicative factor `exp(delta)` (median, 90% HDI), and the random
    walk's own posterior-median innovation scale `sigma`."""
    probs = tau_posterior(idata, y, tau_grid)
    delta = _delta_draws(idata)
    sigma = idata.posterior["sigma"].values.reshape(-1)

    def factor_of(d: np.ndarray) -> dict[str, float]:
        f = np.exp(d)
        lo, hi = _hdi(f, 0.9)
        return {"median": round(float(np.median(f)), 4), "lo": round(lo, 4), "hi": round(hi, 4)}

    if delta.ndim == 1:
        return {"top": top_tau(tau_grid, probs, seasons), "delta_factor": factor_of(delta),
                "sigma": round(float(np.median(sigma)), 4), "n_breaks": 1}
    # two breaks: the marginal of each over seasons; the report's "break" is
    # the one that lowers the level (the layer at the top breaking), the
    # other is reported as the rise. If neither lowers it, the later one
    # stands in and the JSON says so.
    marg = marginal_over_breaks(tau_grid, probs, len(y))
    idx = np.arange(len(y))
    # each break's own season is read off the most probable *pair*, with
    # that season's marginal probability -- the two marginals can peak on
    # the same season (one as tau1, one as tau2), which no single pair can
    modal_pair = tau_grid[int(np.argmax(probs))]
    blocks = [{"top": top_tau(idx, m, seasons), "delta_factor": factor_of(delta[:, k]),
               "modal": {"season": seasons[int(modal_pair[k])], "prob": round(float(m[int(modal_pair[k])]), 4)}}
              for k, m in enumerate(marg)]
    falls = [k for k, b in enumerate(blocks) if b["delta_factor"]["median"] < 1.0]
    fall = falls[-1] if falls else 1
    rise = 1 - fall
    pair_top = np.argsort(-probs)[:3]
    return {
        **blocks[fall], "rise": blocks[rise], "n_breaks": 2, "fall_is_a_fall": bool(falls),
        "pair_top": [{"seasons": [seasons[int(tau_grid[i][0])], seasons[int(tau_grid[i][1])]], "prob": round(float(probs[i]), 4)}
                     for i in pair_top],
        "sigma": round(float(np.median(sigma)), 4),
    }


# =============================================================================
# Model 2: plain local level, no change point -- "the honest forecaster"
# =============================================================================


def fit_local_level(
    y: np.ndarray, *, draws: int = DRAWS, tune: int = TUNE, chains: int = CHAINS,
    target_accept: float = 0.95, seed: int | None = None, progressbar: bool = False, cores: int | None = None,
) -> az.InferenceData:
    """Fit the local level *without* a change point -- at any real origin
    season, whether a break has already happened is exactly what a
    forecaster does not get to use; this is the model behind both the
    backtest and the report's one forecast (see module docstring).
    """
    seed = config.RANDOM_SEED if seed is None else seed
    t = len(y)
    with pm.Model():
        mu0 = pm.Normal("mu0", mu=_mu0_prior(y), sigma=1.0)
        sigma = pm.HalfNormal("sigma", 0.2)
        z_eps = pm.Normal("z_eps", 0.0, 1.0, shape=t - 1)
        eps = pm.Deterministic("eps", z_eps * sigma)
        mu = pm.Deterministic("mu", mu0 + pt.concatenate([[0.0], pt.cumsum(eps)]))
        pm.Poisson("y", mu=pm.math.exp(mu), observed=y)

        idata = pm.sample(draws=draws, tune=tune, chains=chains, target_accept=target_accept,
                          random_seed=seed, progressbar=progressbar, cores=cores or min(chains, 4))
    return idata


def forecast_next(idata: az.InferenceData, seed: int | None = None) -> tuple[float, float, float]:
    """One-step-ahead posterior-predictive forecast from a `fit_local_level`
    fit: `(median, lo, hi)` of `n_{T+1}`, by Monte Carlo simulation per
    posterior draw -- draw the next innovation `eps_{T+1} ~ Normal(0,
    sigma)`, step the level, then draw `n_{T+1} ~ Poisson(exp(level))`. The
    90% interval is the 5th/95th percentile of the simulated draws.
    """
    rng = np.random.default_rng(config.RANDOM_SEED if seed is None else seed)
    mu_last = idata.posterior["mu"].values[..., -1].reshape(-1)
    sigma = idata.posterior["sigma"].values.reshape(-1)
    mu_next = mu_last + rng.normal(0.0, sigma)
    n_next = rng.poisson(np.exp(mu_next))
    lo, hi = np.quantile(n_next, [0.05, 0.95])
    return float(np.median(n_next)), float(lo), float(hi)


# =============================================================================
# Rolling-origin backtest
# =============================================================================


def run_backtest(
    seasons: list[str], y: np.ndarray, *, start: str = BACKTEST_START, end: str = BACKTEST_END,
    draws: int = DRAWS, tune: int = TUNE, chains: int = CHAINS, seed: int | None = None,
) -> dict[str, Any]:
    """One-step-ahead rolling-origin backtest of the plain local level
    against the naive "same as last season" baseline, over
    `backtest_origins(seasons, start, end)` (see module docstring; `start`/
    `end` default to the report's own span but are overridable so a test
    can exercise this on a cheap three-origin slice). `{rows, pooled}`:
    `rows` one dict per origin, `pooled` the mean MAE of each method and
    the model's mean 90% coverage across origins.
    """
    seed = config.RANDOM_SEED if seed is None else seed
    rows = []
    for i, origin in enumerate(backtest_origins(seasons, start, end)):
        train_idx, next_idx = rolling_origin_backtest_split(seasons, origin)
        y_train, actual = y[train_idx], float(y[next_idx])
        idata = fit_local_level(y_train, draws=draws, tune=tune, chains=chains, seed=seed + i)
        median, lo, hi = forecast_next(idata, seed=seed + i)
        naive = float(y_train[-1])
        # median/lo/hi are rounded to whole players for display -- n_t is a
        # count, and a quantile of integer posterior-predictive draws can
        # land on a fraction (e.g. 5.95); MAE/coverage are scored against
        # the unrounded values above, not the display-rounded ones.
        rows.append({
            "origin": origin, "next_season": seasons[next_idx], "actual": actual,
            "median": round(median), "lo": round(lo), "hi": round(hi),
            "naive": naive, "mae_model": round(abs(actual - median), 4),
            "mae_naive": round(abs(actual - naive), 4), "covered": bool(lo <= actual <= hi),
        })
    pooled = {
        "mae_model": round(float(np.mean([r["mae_model"] for r in rows])), 4),
        "mae_naive": round(float(np.mean([r["mae_naive"] for r in rows])), 4),
        "coverage90": round(float(np.mean([r["covered"] for r in rows])), 4),
    }
    return {"rows": rows, "pooled": pooled}


# =============================================================================
# Assembly
# =============================================================================


def assemble_output(
    break_result: dict[str, Any], contrast: dict[str, dict[str, Any]], backtest: dict[str, Any],
    forecast: dict[str, dict[str, Any]], diagnostics: dict[str, Any],
) -> dict[str, Any]:
    """Pure assembly of the JSON shape described in the module docstring;
    no fitting here, so this is testable on hand-built inputs."""
    return {"break": break_result, "contrast": contrast, "backtest": backtest,
            "forecast": forecast, "diagnostics": diagnostics}


# =============================================================================
# Diagnostics
# =============================================================================


def diagnostics_summary(idata: az.InferenceData) -> dict[str, Any]:
    """R-hat/ESS across the change-point model's continuous parameters plus
    the divergence count (same construction as `src.league_strength.
    diagnostics_summary`) -- `tau` itself carries no diagnostics, having
    been marginalised out rather than sampled."""
    summary = az.summary(idata, var_names=["mu0", "sigma", "delta"], ci_prob=0.9)
    return {
        "max_rhat": round(float(summary["r_hat"].max()), 4),
        "min_ess_bulk": round(float(summary["ess_bulk"].min()), 1),
        "min_ess_tail": round(float(summary["ess_tail"].min()), 1),
        "n_divergences": int(idata.sample_stats["diverging"].values.sum()),
    }


# =============================================================================
# Figure
# =============================================================================


def render_figure(
    seasons: list[str], y: np.ndarray, tau_grid: np.ndarray, tau_probs: np.ndarray,
    fitted: np.ndarray, fitted_lo: np.ndarray, fitted_hi: np.ndarray,
    forecast_season: str, forecast_median: float, forecast_lo: float, forecast_hi: float,
    out_path: Path, break_season: str | None = None, break_prob: float | None = None,
) -> None:
    """Task 27B3: one matplotlib SVG, home-nation series only: the observed
    counts against the change-point model's fitted level, drawn as a pale
    oxblood band; the break itself marked with a vertical rule labelled
    "<season> · <prob>%"; the one-step forecast, one season past the
    series, separated from the observed run by a thin dashed rule and drawn
    with its 90% interval at the right edge. `tau_grid`/`tau_probs` are
    still accepted (unused by the drawing) so callers don't need to change;
    the full marginal posterior over candidate break seasons lives in the
    JSON and the surrounding prose instead of a second panel here.
    """
    import matplotlib.pyplot as plt

    from src.figstyle import CREAM, INK, OXBLOOD, OXBLOOD_TINT, RULE, use_style
    from src.utils import season_label

    use_style()
    years = [int(s[:4]) for s in seasons]
    forecast_year = int(forecast_season[:4])

    fig, ax = plt.subplots(figsize=(10.4, 5.6))
    fig.patch.set_facecolor(CREAM)

    ax.fill_between(years, fitted_lo, fitted_hi, color=OXBLOOD_TINT, zorder=1, lw=0)
    ax.plot(years, fitted, color=OXBLOOD, lw=2.2, zorder=3)
    ax.scatter(years, y, color=INK, s=24, zorder=4)

    if break_season is not None:
        break_year = int(break_season[:4])
        ax.axvline(break_year, color=INK, lw=1.1, ls=(0, (3, 2)), zorder=2)
        prob_txt = f" · {round(break_prob * 100)} %" if break_prob is not None else ""
        ax.annotate(
            f"{season_label(break_season)}{prob_txt}", xy=(break_year, 1), xycoords=("data", "axes fraction"),
            xytext=(6, -4), textcoords="offset points", ha="left", va="top", fontsize=10, color=INK, fontweight=600,
        )

    divider_x = years[-1] + 0.5
    ax.axvline(divider_x, color=RULE, lw=1.0, ls=(0, (2, 2)), zorder=2)
    ax.errorbar([forecast_year], [forecast_median],
               yerr=[[forecast_median - forecast_lo], [forecast_hi - forecast_median]],
               fmt="o", color=OXBLOOD, capsize=4, zorder=5, markersize=6)
    ax.annotate(f"{season_label(forecast_season)}: {forecast_median:.0f}", xy=(forecast_year, forecast_median),
               xytext=(8, 0), textcoords="offset points", fontsize=10, color=OXBLOOD, va="center", fontweight=600)

    ax.set_ylabel("Players (≥ 450 min)", color=INK)
    ax.set_title("Dating the break and one forecast", loc="left")
    ax.set_xlim(years[0] - 0.6, forecast_year + 1.6)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(RULE)
    ax.tick_params(colors=INK)

    plt.savefig(out_path, format="svg")
    plt.close(fig)
    LOG.info("wrote %s", out_path)


def fitted_level(idata: az.InferenceData, tau_grid: np.ndarray, mode_tau: int | tuple[int, ...]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Median + 90% band of the change-point model's fitted level
    `exp(mu_base + delta * 1[t >= mode_tau])`, illustrating the fit at the
    single most probable break season (`mode_tau`, a season index) --
    a plotting convenience, not a re-marginalisation over `tau`; the JSON's
    `break.top`/`delta_factor` carry the full marginal posterior.
    """
    mu_base = idata.posterior["mu_base"].values.reshape(-1, idata.posterior.sizes["mu_base_dim_0"])
    delta = _delta_draws(idata).reshape(mu_base.shape[0], -1)  # (draws, n_breaks)
    taus = np.atleast_1d(np.asarray(mode_tau))
    step = (np.arange(mu_base.shape[1])[:, None] >= taus[None, :]).astype("float64")  # (T, n_breaks)
    level = np.exp(mu_base + delta @ step.T)
    return np.median(level, axis=0), np.quantile(level, 0.05, axis=0), np.quantile(level, 0.95, axis=0)


# =============================================================================
# Main
# =============================================================================


def main() -> None:
    logging_setup()
    config.ensure_dirs()
    t_start = time.time()

    big5_path = config.PROCESSED_DIR / "big5_series.json"
    big5_series = json.loads(big5_path.read_text(encoding="utf-8"))
    seasons = big5_series["seasons"]
    home = config.HOME
    contrast_codes = list(config.nation()["series_contrast"])

    y_home = extract_series(big5_series, home)
    t0 = time.time()
    idata_home, tau_grid = fit_change_point(y_home, n_breaks=N_BREAKS, seed=config.RANDOM_SEED)
    LOG.info("%s change-point fit: %.1f s (%d seasons)", home, time.time() - t0, len(y_home))
    break_result = break_summary(idata_home, y_home, tau_grid, seasons)
    diagnostics = diagnostics_summary(idata_home)
    LOG.info("%s break: %s", home, break_result)
    LOG.info("diagnostics: %s", diagnostics)

    contrast: dict[str, Any] = {}
    for code in contrast_codes:
        y_c = extract_series(big5_series, code)
        t0 = time.time()
        idata_c, tau_grid_c = fit_change_point(y_c, n_breaks=N_BREAKS, seed=config.RANDOM_SEED)
        LOG.info("%s change-point fit: %.1f s", code, time.time() - t0)
        contrast[code] = break_summary(idata_c, y_c, tau_grid_c, seasons)

    t0 = time.time()
    backtest = run_backtest(seasons, y_home, seed=config.RANDOM_SEED)
    LOG.info("backtest: %.1f s, pooled=%s", time.time() - t0, backtest["pooled"])

    forecast: dict[str, Any] = {}
    next_season = next_season_label(seasons[-1])
    for i, code in enumerate([home, *contrast_codes]):
        y_c = y_home if code == home else extract_series(big5_series, code)
        t0 = time.time()
        idata_fc = fit_local_level(y_c, seed=config.RANDOM_SEED + i)
        median, lo, hi = forecast_next(idata_fc, seed=config.RANDOM_SEED + i)
        LOG.info("%s forecast fit: %.1f s -> %s: %.1f (%.1f-%.1f)",
                 code, time.time() - t0, next_season, median, lo, hi)
        # rounded to whole players (a count), same reasoning as run_backtest's rows
        forecast[code] = {"season": next_season, "median": round(median),
                          "lo": round(lo), "hi": round(hi)}

    result = assemble_output(break_result, contrast, backtest, forecast, diagnostics)
    out_json = config.PROCESSED_DIR / "series_model.json"
    out_json.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    LOG.info("wrote %s", out_json)

    tau_probs = tau_posterior(idata_home, y_home, tau_grid)
    # the fitted level is drawn at the most probable candidate (a pair, for two breaks)
    mode_tau = tuple(int(v) for v in np.atleast_1d(tau_grid[int(np.argmax(tau_probs))]))
    fitted_med, fitted_lo, fitted_hi = fitted_level(idata_home, tau_grid, mode_tau)
    home_forecast = forecast[home]
    top_break = break_result["top"][0]
    render_figure(seasons, y_home, tau_grid, tau_probs, fitted_med, fitted_lo, fitted_hi,
                 home_forecast["season"], home_forecast["median"], home_forecast["lo"], home_forecast["hi"],
                 config.OUTPUTS_DIR / "series_model.svg",
                 break_season=top_break["season"], break_prob=top_break["prob"])

    LOG.info("done: %s, %.1f s total", config.NATION, time.time() - t_start)


if __name__ == "__main__":
    main()
