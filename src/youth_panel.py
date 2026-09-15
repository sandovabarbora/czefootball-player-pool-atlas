"""Cross-country youth-minutes panel (Task 20, spec §2 M3).

Question. Slide 3 already shows, for the metrics season alone, each
country's U21 share of its own domestic-league minutes next to its top-9
players per million; this module asks whether that association holds up
once the panel is widened -- across every peer country (`config.
PEER_COUNTRIES`, home nation included) and two seasons instead of one.

Panel (`build_panel`): one row per (country, season) for season in
{previous, metrics} -- **not** current, which is partial (see
`config/seasons.yaml`) and is deliberately left out, stated in the JSON's
own `seasons_used`. `x` = U21 share of that country's own domestic-league
minutes in that season (`src.pathways.youth_exposure`'s `share_u21`,
computed on that country's own top flight); `y` = that country's top-9
players per million in the same season
(`src.international_benchmark.per_capita`'s `per_million`). Both numbers
are contemporaneous (same country, same season) -- this is a descriptive
association, not a claim that a season's youth minutes cause that same
season's per-capita count.

A country whose own top flight has no FBref data at all (Slovakia --
`SVK-Super Liga` carries no `comp_id` in `config/leagues.yaml`, see that
file's own comment) gets `share_u21 = None` from `youth_exposure` in every
season; such rows are dropped here (the model needs a real `x`), so the
panel's actual n is smaller than "countries x 2 seasons" would suggest for
a home nation with an unfetched peer league -- for Czechia this is 8
countries x 2 seasons = 16, not 9 x 2 = 18 (`n`/`n_countries` in the output
JSON report the number actually used, not the nominal one).

Model (`fit_model`): `y ~ Normal(alpha + beta*x + u_country, sigma)`, PyMC
5, non-centred country random intercept --

    alpha        ~ Normal(0, 10)
    beta         ~ Normal(0, 20)
    u_country    = z_country * sigma_country,  z_country ~ Normal(0, 1),
                   sigma_country ~ HalfNormal(5)          (non-centred)
    sigma        ~ HalfNormal(5)

sampled with NUTS, 4 chains x 1000 draws after 1000 tune, target_accept 0.9,
`random_seed = config.RANDOM_SEED` (PyMC: Abril-Pla et al., 2023). Two
seasons per country only weakly identifies each country's own intercept --
`sigma_country`'s posterior and the wide beta interval both say so, and the
report copy states it plainly rather than reading the point estimate as
settled. `beta` is reported per 10 percentage points of U21 share (`beta *
0.10`, since `x` is a 0-1 share) with a 90% HDI, plus a posterior-median R^2
against the fitted values (fixed effect + country intercept).

Comparison (`bootstrap_ols_slope`): statsmodels is not a dependency, so the
"does a much simpler method agree" check is a plain `numpy.polyfit` degree-1
slope on the pooled panel (no country structure at all) with a
percentile-bootstrap 90% CI (1000 resamples of the panel's rows) -- reported
on the same per-10pp basis, so the report can show the two methods side by
side.

Output: `data/processed/<nation>/youth_panel.json` and figure
`outputs/<nation>/youth_panel.svg` (scatter, country codes as labels, the
two seasons connected per country, the population-level fitted line and its
90% band, home nation highlighted).
"""

from __future__ import annotations

import json
import logging
import warnings
from pathlib import Path
from typing import Any

import arviz as az
import numpy as np
import pandas as pd
import pymc as pm

from src import config
from src.international_benchmark import per_capita
from src.logging_setup import setup as logging_setup
from src.pathways import youth_exposure
from src.utils import read_parquet, season_label

LOG = logging.getLogger(__name__)

DRAWS = 1000
TUNE = 1000
CHAINS = 4
BOOTSTRAP_N = 1000
PANEL_SEASON_KEYS = ("previous", "metrics")


# =============================================================================
# Data
# =============================================================================


def domestic_league_by_country(cfg: dict[str, Any], peers: list[str]) -> dict[str, str]:
    """`{country: its own top-flight league key}`, home nation included.

    Duplicates `src.pathways.build_pathways`'s own `tier1_by_country`
    construction (not exposed there as a standalone helper): most peers'
    own top flight is in `cfg["peer_domestic"]` or `cfg["custom"]`; a peer
    whose own top flight is itself a headline league (e.g. every one of
    England's peers -- FRA, GER, ESP, ITA, NED, POR, BEL) falls back to the
    headline-league key's own country-code prefix ("FRA-Ligue 1" ->
    "FRA").
    """
    tier1_by_country = {
        v["country"]: k for k, v in {**cfg.get("custom", {}), **cfg["peer_domestic"]}.items()
        if v.get("tier", 1) == 1
    }
    tier1_by_country.update({
        k.split("-", 1)[0]: k for k in cfg["headline"] if k.split("-", 1)[0] not in tier1_by_country
    })
    mapping = {config.HOME: cfg["domestic"]}
    mapping.update({c: tier1_by_country[c] for c in peers if c in tier1_by_country})
    return mapping


def build_panel(
    tables: pd.DataFrame, peers_meta: dict[str, Any], headline_leagues: list[str],
    league_by_country: dict[str, str], seasons: dict[str, str],
) -> pd.DataFrame:
    """One row per (country, season) for `season` in {previous, metrics}
    (see module docstring). Columns: `country`, `season`, `season_key`,
    `x` (U21 share of domestic minutes), `y` (top-9 players per million).
    A country with no data for its own top flight in a season (`x is
    None`) is dropped from that season's rows.
    """
    league_country = {lg: c for c, lg in league_by_country.items()}
    rows = []
    for skey in PANEL_SEASON_KEYS:
        season = seasons[skey]
        pc = per_capita(tables, peers_meta, headline_leagues, season)
        youth = youth_exposure(tables, season, league_country)
        youth_by = {r["country"]: r for r in youth.to_dict("records")}
        for _, r in pc.iterrows():
            country = r["country"]
            yr = youth_by.get(country)
            share = yr["share_u21"] if yr else None
            if share is None:
                continue
            rows.append({
                "country": country, "season": season, "season_key": skey,
                "x": float(share), "y": float(r["per_million"]),
            })
    return pd.DataFrame(rows, columns=["country", "season", "season_key", "x", "y"])


# =============================================================================
# Bayesian model
# =============================================================================


def fit_model(
    panel: pd.DataFrame, *, draws: int = DRAWS, tune: int = TUNE, chains: int = CHAINS,
    target_accept: float = 0.9, seed: int | None = None, progressbar: bool = False,
    cores: int | None = None,
) -> az.InferenceData:
    """Fit `y ~ Normal(alpha + beta*x + u_country, sigma)` (see module
    docstring). Returns an InferenceData with a `country` dim on
    `u_country`."""
    seed = config.RANDOM_SEED if seed is None else seed
    country_cat = pd.Categorical(panel["country"])
    x = panel["x"].to_numpy()
    y = panel["y"].to_numpy()

    with pm.Model(coords={"country": list(country_cat.categories)}):
        alpha = pm.Normal("alpha", 0.0, 10.0)
        beta = pm.Normal("beta", 0.0, 20.0)

        sigma_country = pm.HalfNormal("sigma_country", 5.0)
        z_country = pm.Normal("z_country", 0.0, 1.0, dims="country")
        u_country = pm.Deterministic("u_country", z_country * sigma_country, dims="country")

        sigma = pm.HalfNormal("sigma", 5.0)
        mu = alpha + beta * x + u_country[country_cat.codes]
        pm.Normal("y", mu=mu, sigma=sigma, observed=y)

        idata = pm.sample(
            draws=draws, tune=tune, chains=chains, target_accept=target_accept,
            random_seed=seed, progressbar=progressbar, cores=cores or min(chains, 4),
        )
    return idata


def _hdi(samples: np.ndarray, prob: float = 0.9) -> tuple[float, float]:
    """Highest-density interval of a 1-D sample (same construction as
    `src.league_strength._hdi`/`src.series_model._hdi` -- duplicated rather
    than imported, per those modules' own comment on why)."""
    s = np.sort(np.asarray(samples))
    n = len(s)
    n_in = max(int(np.floor(prob * n)), 1)
    n_out = n - n_in
    if n_out <= 0:
        return float(s[0]), float(s[-1])
    widths = s[n_in:] - s[:n_out]
    lo = int(np.argmin(widths))
    return float(s[lo]), float(s[lo + n_in])


def bayes_summary(idata: az.InferenceData, panel: pd.DataFrame) -> dict[str, Any]:
    """`{beta_per_10pp, alpha, r2}`: beta rescaled to a 10-percentage-point
    step in U21 share with its 90% HDI, the posterior-median intercept, and
    an R^2 of the posterior-median fit (fixed effect + country intercept)
    against the observed `y` -- a descriptive goodness-of-fit number, not a
    claim the model is causal."""
    beta = idata.posterior["beta"].values.reshape(-1)
    beta_10pp = beta * 0.10
    lo, hi = _hdi(beta_10pp, 0.9)

    alpha_med = float(np.median(idata.posterior["alpha"].values))
    beta_med = float(np.median(beta))
    u_country = idata.posterior["u_country"]
    u_med = u_country.median(dim=("chain", "draw")).values
    countries = [str(c) for c in u_country.coords["country"].values]
    idx = {c: i for i, c in enumerate(countries)}
    codes = panel["country"].map(idx).to_numpy()
    fitted = alpha_med + beta_med * panel["x"].to_numpy() + u_med[codes]
    y = panel["y"].to_numpy()
    ss_res = float(np.sum((y - fitted) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

    return {
        "beta_per_10pp": {"median": round(float(np.median(beta_10pp)), 4), "lo": round(lo, 4), "hi": round(hi, 4)},
        "alpha": round(alpha_med, 4),
        "r2": round(r2, 4),
    }


def diagnostics_summary(idata: az.InferenceData) -> dict[str, Any]:
    """R-hat/ESS across the model's fixed effects plus the divergence count
    (same construction as `src.league_strength.diagnostics_summary`)."""
    summary = az.summary(idata, var_names=["alpha", "beta", "sigma_country", "sigma"], ci_prob=0.9)
    return {
        "max_rhat": round(float(summary["r_hat"].max()), 4),
        "min_ess_bulk": round(float(summary["ess_bulk"].min()), 1),
        "min_ess_tail": round(float(summary["ess_tail"].min()), 1),
        "n_divergences": int(idata.sample_stats["diverging"].values.sum()),
        "sigma_country_median": round(float(idata.posterior["sigma_country"].median()), 4),
    }


def population_line(idata: az.InferenceData, xs: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Population-level (fixed-effect only, no country intercept) fitted
    line over `xs`: posterior median + 90% band, one point per `xs`
    entry."""
    alpha = idata.posterior["alpha"].values.reshape(-1)
    beta = idata.posterior["beta"].values.reshape(-1)
    lines = alpha[:, None] + beta[:, None] * xs[None, :]
    med = np.median(lines, axis=0)
    lo = np.quantile(lines, 0.05, axis=0)
    hi = np.quantile(lines, 0.95, axis=0)
    return med, lo, hi


# =============================================================================
# OLS comparison
# =============================================================================


def ols_fit(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Plain degree-1 `numpy.polyfit` slope and intercept (no
    country structure -- the "much simpler method" comparison)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", np.RankWarning if hasattr(np, "RankWarning") else Warning)
        slope, intercept = np.polyfit(x, y, 1)
    return float(slope), float(intercept)


def bootstrap_ols_slope(panel: pd.DataFrame, *, n_boot: int = BOOTSTRAP_N, seed: int | None = None) -> dict[str, Any]:
    """OLS slope on the pooled panel, per 10pp of U21 share, with a
    percentile-bootstrap 90% CI (`n_boot` resamples of the panel's rows,
    with replacement)."""
    seed = config.RANDOM_SEED if seed is None else seed
    rng = np.random.default_rng(seed)
    x, y = panel["x"].to_numpy(), panel["y"].to_numpy()
    n = len(x)
    slope, intercept = ols_fit(x, y)

    boots = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, n, n)
        s, _ = ols_fit(x[idx], y[idx])
        boots[i] = s
    boots = boots[np.isfinite(boots)]
    boots_10pp = boots * 0.10
    lo, hi = np.percentile(boots_10pp, [5, 95])

    return {
        "slope_per_10pp": {"point": round(slope * 0.10, 4), "lo": round(float(lo), 4), "hi": round(float(hi), 4)},
        "intercept": round(intercept, 4),
        "n_boot": int(len(boots)),
    }


# =============================================================================
# Figure
# =============================================================================


def render_figure(
    panel: pd.DataFrame, xs: np.ndarray, fitted: np.ndarray, fitted_lo: np.ndarray, fitted_hi: np.ndarray,
    out_path: Path,
) -> None:
    """Scatter of `x` (U21 share, %) against `y` (top-9 per million), one
    line per country connecting its two seasons, the population-level
    fitted line + 90% band, home nation in oxblood."""
    import matplotlib.pyplot as plt

    from src.international_benchmark import CREAM, INK, MUTED, NAVY, OXBLOOD, RULE

    fig, ax = plt.subplots(figsize=(8.5, 5.8))
    fig.patch.set_facecolor(CREAM)
    ax.set_facecolor(CREAM)

    ax.plot(xs * 100, fitted, color=NAVY, lw=2.0, zorder=2, label="Fitted line (population level, 90% band)")
    ax.fill_between(xs * 100, fitted_lo, fitted_hi, color=NAVY, alpha=0.12, zorder=1, lw=0)

    for country, g in panel.groupby("country"):
        g = g.sort_values("season_key")
        is_home = country == config.HOME
        color = OXBLOOD if is_home else MUTED
        ax.plot(g["x"] * 100, g["y"], color=color, lw=1.4 if is_home else 1.0, alpha=0.9, zorder=3)
        ax.scatter(g["x"] * 100, g["y"], color=color, s=50 if is_home else 30,
                  zorder=4, edgecolors=CREAM, linewidths=0.6)
        last = g.iloc[-1]
        ax.annotate(country, xy=(last["x"] * 100, last["y"]), xytext=(5, 3), textcoords="offset points",
                   fontsize=9, fontfamily="sans-serif", color=color,
                   weight="bold" if is_home else "normal")

    ax.set_xlabel("U21 share of domestic-league minutes (%)", fontsize=10, fontfamily="sans-serif", color=INK)
    ax.set_ylabel("Top-9-league players per million population", fontsize=10, fontfamily="sans-serif", color=INK)
    ax.set_title("Youth minutes and pool depth, across countries and two seasons",
                fontsize=13, fontfamily="serif", color=INK, loc="left")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(RULE)
    ax.tick_params(colors=INK)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK, loc="upper left")
    plt.tight_layout()
    plt.savefig(out_path, format="svg", facecolor=CREAM, edgecolor="none")
    plt.close(fig)
    LOG.info("wrote %s", out_path)


# =============================================================================
# Assembly / main
# =============================================================================


def assemble_output(
    panel: pd.DataFrame, bayes: dict[str, Any], ols: dict[str, Any], diagnostics: dict[str, Any],
    seasons_used: list[str],
) -> dict[str, Any]:
    """Pure assembly of the JSON shape described in the module docstring;
    no fitting here, so this is testable on hand-built inputs."""
    return {
        "panel": [
            {"country": r.country, "season": r.season, "x": round(r.x, 4), "y": round(r.y, 2)}
            for r in panel.itertuples()
        ],
        "n": int(len(panel)),
        "n_countries": int(panel["country"].nunique()),
        "seasons_used": seasons_used,
        "bayes": bayes,
        "ols": ols,
        "diagnostics": diagnostics,
        "home": config.HOME,
    }


def main() -> None:
    logging_setup()
    config.ensure_dirs()

    cfg, peers, seasons = config.leagues(), config.PEER_COUNTRIES, config.seasons()
    peers_meta = config.peers_meta()
    tables = read_parquet(config.PROCESSED_DIR / "fbref_players.parquet")

    league_by_country = domestic_league_by_country(cfg, peers)
    panel = build_panel(tables, peers_meta, cfg["headline"], league_by_country, seasons)
    LOG.info("panel: %d rows, %d countries", len(panel), panel["country"].nunique())

    idata = fit_model(panel, seed=config.RANDOM_SEED)
    bayes = bayes_summary(idata, panel)
    diagnostics = diagnostics_summary(idata)
    LOG.info("bayes: %s", bayes)
    LOG.info("diagnostics: %s", diagnostics)

    ols = bootstrap_ols_slope(panel, seed=config.RANDOM_SEED)
    LOG.info("ols: %s", ols)

    seasons_used = [season_label(seasons[k]) for k in PANEL_SEASON_KEYS]
    result = assemble_output(panel, bayes, ols, diagnostics, seasons_used)
    out_json = config.PROCESSED_DIR / "youth_panel.json"
    out_json.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    LOG.info("wrote %s", out_json)

    xs = np.linspace(panel["x"].min(), panel["x"].max(), 60)
    fitted, lo, hi = population_line(idata, xs)
    render_figure(panel, xs, fitted, lo, hi, config.OUTPUTS_DIR / "youth_panel.svg")

    LOG.info("done: %s", config.NATION)


if __name__ == "__main__":
    main()
