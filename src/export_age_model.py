"""Age at export (M1 proper): does leaving later go with anything? PyMC 5.

Football question (Task 23, spec §2 M1): "Do we sell our best 21-year-olds
too late?" Analytical question: league-adjusted production in a player's
first two top-{topn} seasons as a function of their age at the first such
season, given origin-league strength and position, with a country effect --
the caveat that selection (better players tend to leave earlier) is not
separated from development is part of the finding, not a footnote to it.

Corpus (`build_corpus`): every player of every peer nationality (home nation
included -- `config.PEER_COUNTRIES` already carries it first, same set
`src.pathways`/`src.youth_panel` use) whose first top-9-league season with
>= 450 minutes (`config.features()["min_minutes"]`, the same floor already
baked into `features_{FW,MF,DF}.parquet` -- see that module) lies inside the
fetched window and is not censored. "Censored" reuses `src.pathways.
export_route`'s own rule (not exposed there as a standalone helper, so
duplicated here, same as `src.youth_panel.domestic_league_by_country`
duplicates that module's tier-1-by-country construction): a player whose
first qualifying season IS the earliest season in the fetched roster tables
(`fbref_players.parquet`) has no visible history before it, so their true
origin is unknown, not "not covered" -- dropped, not guessed at. A player
with a qualifying first season that isn't censored but who nonetheless has
no earlier row at all in the roster tables (a genuine professional debut,
not a data-coverage artifact) is dropped for the same practical reason --
no origin league to price -- documented here rather than reported as a
third, spurious "origin unknown" category.

For every surviving player: `age_export` = the `age` column of that first
qualifying row (the report's own "age at the season's start" feature,
already computed by `src.features.per90`, not recomputed here under a
different convention); `origin_strength` = the transfer-graph model's (M2,
`src.league_strength`) `m_L` for the league of the season immediately before
the first qualifying one, or -- where M2 has no fitted estimate for that
league -- the UEFA-coefficient multiplier (`config.league_quality()`);
`origin_source` records which of the two was used, per row; `y` = the mean
of `npg_p90_quality + ast_p90_quality` (the report's own league-adjusted
production feature) over the player's first one or two qualifying top-9
seasons (`n_seasons` flags which); `pos_group` and `nation` carry through
from the first qualifying row.

Model (`fit_model`), PyMC 5, non-centred throughout:

    y ~ Normal(mu, sigma)
    mu = alpha + f(age) + beta*origin_strength + gamma_pos + u_nation

`f(age)` is a natural cubic spline with knots at 19, 21, 23, 25
(`natural_cubic_spline_basis`, the standard truncated-power-basis
construction -- ESL section 5.2.1 -- since `patsy`/`formulaic` are not
dependencies here), or a plain quadratic in centred age when the corpus is
small (`n < SPLINE_MIN_N = 150`; which branch was used is recorded in the
output). `u_nation ~ Normal(0, sigma_n)` is a non-centred partial-pooling
country random intercept, the same construction as `src.league_strength`'s
`b_league`/`src.youth_panel`'s `u_country`.

Standardised-priors lesson (`src.youth_panel`'s own review-round-2 fix,
explicitly reused here): the spline design columns are `(age - knot)_+^3`
differences, tens to low thousands in raw units over this corpus's age
range -- a raw-scale "weakly informative" prior on their coefficients would
in fact be wildly informative, the exact failure mode `youth_panel`'s
docstring documents for its own beta. Every design column (the spline/
quadratic age columns, `origin_strength`) AND the outcome `y` are therefore
z-scored before fitting, with `Normal(0, 2.5)`/`HalfNormal(1)` priors on the
standardised parameters (`build_design`); every summary function converts
back to raw (npG+A/90, m_L) units before reporting, exactly mirroring
`src.youth_panel._between_raw_beta_alpha`'s pattern.

4 chains x 1000 draws after 1000 tune, target_accept 0.9, `random_seed =
config.RANDOM_SEED`, PyMC (Abril-Pla et al., 2023), NUTS (Hoffman and
Gelman, 2014), diagnosed with ArviZ. The same model refit without
`origin_strength` (`use_strength=False`) shows what the league term
absorbs: if origin strength carries some of what otherwise reads as a
nation effect, `sigma_n` should widen once it is dropped.

Validation:
  1. Posterior predictive check (`ppc_summary`): observed vs. replicated `y`
     -- mean, sd, 10th/90th percentile (Gelman et al., 2013).
  2. Leave-one-nation-out (`run_lono`): refit excluding the home nation's
     own rows (lighter budget, same non-centred model) -- does the age
     curve move? Reported as the shift in the age-21-vs-24 difference and
     in beta between the full and the LONO fit.
  3. Diagnostics: R-hat, ESS, divergence count (`diagnostics_summary`).

Selection caveat (stated, not fixed): the corpus is not a random sample of
players who could have left later -- players who leave earlier tend to be
the ones judged ready earliest, a selection effect the age curve cannot
distinguish from a genuine development effect of arriving young. The curve
describes what age-at-export goes with; it does not identify what delaying
export would do to a given player.

Output: `data/processed/<nation>/export_age_model.json` and figure
`outputs/<nation>/export_age_model.svg` (the fitted curve with its 90% band,
the home nation's own exports as points, a rug of every corpus player's
age).
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import arviz as az
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pymc as pm

from src import config
from src.international_benchmark import CREAM, INK, MUTED, NAVY, OXBLOOD, RULE
from src.logging_setup import setup as logging_setup
from src.utils import collapse_player_seasons, read_parquet

LOG = logging.getLogger(__name__)

# Matplotlib defaults shared with the rest of the report's figures (same
# literal block as src.league_strength/src.youth_panel).
plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["Spectral", "Cambria", "Georgia", "Times New Roman", "DejaVu Serif"]
plt.rcParams["font.sans-serif"] = ["Bricolage Grotesque", "Helvetica Neue", "Arial", "DejaVu Sans"]
plt.rcParams["text.color"] = INK

AGE_KNOTS: tuple[float, ...] = (19.0, 21.0, 23.0, 25.0)
SPLINE_MIN_N = 150
EVAL_AGES: tuple[int, ...] = (19, 21, 23, 25, 27)

DRAWS, TUNE, CHAINS, TARGET_ACCEPT = 1000, 1000, 4, 0.9
LONO_DRAWS, LONO_TUNE, LONO_CHAINS = 500, 500, 2


# =============================================================================
# Data
# =============================================================================


def _dedupe_player_season(df: pd.DataFrame, key_cols: tuple[str, ...] = ("player_key", "season")) -> pd.DataFrame:
    """Collapse (player_key, season) duplicates from mid-season transfers to
    one row (most-minutes club decides league/team for the season).

    Duplicates `src.pathways._dedupe_player_season` (that module's own
    private helper, not exposed as a standalone function) -- fit to
    `fbref_players.parquet`'s raw shape, which is all this module needs `t`
    for: finding the league of the season immediately before a player's
    first qualifying top-9 season.
    """
    key_cols = list(key_cols)
    sizes = df.groupby(key_cols)["min"].transform("size")
    singles, dup_rows = df[sizes == 1], df[sizes > 1]
    if dup_rows.empty:
        return df
    collapsed = []
    for _, g in dup_rows.groupby(key_cols):
        lead = g.loc[g["min"].idxmax()].to_dict()
        lead["min"] = int(g["min"].sum())
        collapsed.append(lead)
    out = pd.concat([singles, pd.DataFrame(collapsed)], ignore_index=True)
    return out[df.columns.tolist()]


def build_first_seasons(feats: pd.DataFrame) -> pd.DataFrame:
    """One row per (nation, player_key): the player's first top-9-league,
    >= 450-minute season and `y`.

    `feats` is already restricted by the caller to peer nationalities and
    headline leagues (`build_corpus`); the >= 450-minute floor is inherited
    from `features_{FW,MF,DF}.parquet` itself (`src.features.main`), not
    reapplied here. Rows are first collapsed with `collapse_player_seasons`
    for the rare case of a mid-season transfer between two headline clubs
    in the same season (two rows would otherwise both count as "first").

    `y` is the mean of `npg_p90_quality + ast_p90_quality` over the
    player's first one or two qualifying seasons in `feats` (sorted by
    season); `n_seasons` records which (1 or 2) -- most players will have
    only one qualifying row for the metrics season closest to their debut,
    since seasons before/after a debut with < 450 minutes are excluded from
    `feats` entirely, same as everywhere else in this report.
    """
    feats = collapse_player_seasons(feats, rate_cols=["npg_p90_quality", "ast_p90_quality"])
    rows = []
    for (nation, key), g in feats.sort_values("season").groupby(["nation", "player_key"]):
        g = g.reset_index(drop=True)
        first = g.iloc[0]
        two = g.head(2)
        y = float((two["npg_p90_quality"] + two["ast_p90_quality"]).mean())
        rows.append({
            "nation": nation, "player_key": key, "player": first["player"],
            "pos_group": first["pos_group"], "first_season": first["season"],
            "age_export": float(first["age"]), "y": y, "n_seasons": int(len(two)),
        })
    cols = ["nation", "player_key", "player", "pos_group", "first_season", "age_export", "y", "n_seasons"]
    return pd.DataFrame(rows, columns=cols)


def attach_origin(
    rows: pd.DataFrame, tables: pd.DataFrame, m_l_map: dict[str, float], uefa_multipliers: dict[str, float],
) -> pd.DataFrame:
    """Attach `origin_league`/`origin_strength`/`origin_source`, dropping
    censored rows and rows with no priceable origin (see module docstring).

    `tables` is the raw `fbref_players.parquet` frame (every season, every
    league, no minute floor), deduped to one row per (player_key, season).
    For each `rows` entry: censored (`first_season` == the whole table's
    earliest fetched season -- `pathways.export_route`'s own rule) is
    dropped; otherwise the league of the immediately preceding season row
    (any league, any minutes) is the origin; a row with no preceding season
    at all is dropped (nothing to price); `origin_strength` prefers M2's
    `m_L` (`m_l_map`) and falls back to the UEFA multiplier
    (`uefa_multipliers`), recording which in `origin_source`; a league with
    neither on file drops the row (rare, no strength estimate at all).
    """
    t = _dedupe_player_season(tables)
    first_hist = t["season"].min()
    hist_by_key = {k: g.sort_values("season") for k, g in t.groupby("player_key")}

    out = []
    for r in rows.to_dict("records"):
        if r["first_season"] == first_hist:
            continue
        hist = hist_by_key.get(r["player_key"])
        if hist is None:
            continue
        before = hist[hist["season"] < r["first_season"]]
        if before.empty:
            continue
        origin_league = before.iloc[-1]["league"]
        m, source = m_l_map.get(origin_league), "m_L"
        if m is None:
            m, source = uefa_multipliers.get(origin_league), "uefa"
        if m is None:
            continue
        out.append({**r, "origin_league": origin_league, "origin_strength": float(m), "origin_source": source})

    cols = ["nation", "player_key", "player", "pos_group", "first_season", "age_export", "y", "n_seasons",
            "origin_league", "origin_strength", "origin_source"]
    return pd.DataFrame(out, columns=cols)


# =============================================================================
# Age design: natural cubic spline (or quadratic fallback)
# =============================================================================


def natural_cubic_spline_basis(x: np.ndarray, knots: tuple[float, ...]) -> np.ndarray:
    """Natural cubic spline basis, the truncated-power-basis construction
    (Hastie, Tibshirani and Friedman, *The Elements of Statistical
    Learning*, 2nd edn, eqs 5.4-5.5) -- written out directly since
    `patsy`/`formulaic` are not dependencies here.

    For K knots xi_1 < ... < xi_K (`knots`, sorted), returns a `(len(x),
    K-1)` array: column 0 is the plain linear term `x`; columns 1..K-2 are
    `d_k(x) - d_{K-1}(x)` for `k = 1, ..., K-2` (1-indexed), where
    `d_k(x) = ((x-xi_k)_+^3 - (x-xi_K)_+^3) / (xi_K - xi_k)`. The constant
    term (`N_1 = 1` in the ESL numbering) is left to the caller's own model
    intercept, not included here.

    A natural spline is linear outside the boundary knots by construction:
    for `x <= xi_1` every `d_k(x)` is 0 (both truncated cubes vanish), so
    every nonlinear column is exactly 0 there and only the linear term
    survives -- the property `test_natural_cubic_spline_basis_shape_and_
    linear_below_first_knot` checks directly.
    """
    knots = tuple(sorted(knots))
    K = len(knots)
    x = np.asarray(x, dtype=float)
    x_last = knots[-1]

    def _pos_cube(z: np.ndarray) -> np.ndarray:
        return np.clip(z, 0.0, None) ** 3

    def _d(k: int) -> np.ndarray:
        return (_pos_cube(x - knots[k]) - _pos_cube(x - x_last)) / (x_last - knots[k])

    d_ref = _d(K - 2)  # d_{K-1}, 1-indexed -- the (K-1)th knot, 0-indexed K-2
    cols = [x] + [_d(k) - d_ref for k in range(K - 2)]
    return np.column_stack(cols)


def age_design(age: np.ndarray, n: int, knots: tuple[float, ...] = AGE_KNOTS) -> tuple[np.ndarray, list[str], bool]:
    """`(raw_design, column_names, use_spline)` for the age term.

    Natural cubic spline (`natural_cubic_spline_basis`) when the corpus is
    at least `SPLINE_MIN_N` rows, else a quadratic in age centred on the
    corpus's own mean age (brief: "a quadratic if n < 150 -- decide from n
    and state it"). `n` is passed explicitly (not `len(age)`) so a caller
    evaluating the SAME design on a different set of ages (the report
    curve, LONO) uses the branch the ORIGINAL fit chose, not one decided by
    however many evaluation points happen to be passed in.
    """
    age = np.asarray(age, dtype=float)
    use_spline = n >= SPLINE_MIN_N
    if use_spline:
        return natural_cubic_spline_basis(age, knots), ["age_ns1", "age_ns2", "age_ns3"], True
    age_c = (age - 23.0) / 5.0
    return np.column_stack([age_c, age_c**2]), ["age_c", "age_c2"], False


def build_corpus(
    features_by_group: dict[str, pd.DataFrame], tables: pd.DataFrame, peers: list[str], headline: list[str],
    m_l_map: dict[str, float], uefa_multipliers: dict[str, float],
) -> pd.DataFrame:
    """Assemble the full corpus (see module docstring): peer-nationality,
    headline-league rows from `features_{FW,MF,DF}.parquet` reduced to one
    row per player (`build_first_seasons`), then priced with an origin
    league and filtered for censoring (`attach_origin`)."""
    headline_set = set(headline)
    frames = []
    for g, df in features_by_group.items():
        sub = df[df["nation"].isin(peers) & df["league"].isin(headline_set)].copy()
        if "pos_group" not in sub.columns:
            sub["pos_group"] = g
        frames.append(sub)
    feats = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    first = build_first_seasons(feats)
    corpus = attach_origin(first, tables, m_l_map, uefa_multipliers)
    return corpus.reset_index(drop=True)


# =============================================================================
# Model
# =============================================================================

POS_GROUPS = ["FW", "MF", "DF"]  # same order as src.league_strength.POS_GROUPS


def build_design(corpus: pd.DataFrame) -> dict[str, Any]:
    """Standardise every design column and `y` (the youth_panel-review
    lesson, see module docstring); everything a `fit_model` call and every
    summary function below need, bundled so raw-scale conversion always
    uses the SAME means/sds the model was actually fit on.
    """
    n = len(corpus)
    age = corpus["age_export"].to_numpy(dtype=float)
    X_age_raw, age_cols, use_spline = age_design(age, n)
    age_mean = X_age_raw.mean(axis=0)
    age_sd = X_age_raw.std(axis=0)
    age_sd = np.where(age_sd > 0, age_sd, 1.0)

    strength = corpus["origin_strength"].to_numpy(dtype=float)
    strength_mean = float(strength.mean())
    strength_sd = float(strength.std()) or 1.0

    y = corpus["y"].to_numpy(dtype=float)
    y_mean = float(y.mean())
    y_sd = float(y.std()) or 1.0

    pos_cat = pd.Categorical(corpus["pos_group"], categories=POS_GROUPS)
    if pos_cat.isna().any():
        raise ValueError(f"pos_group has values outside {POS_GROUPS}")
    nation_cat = pd.Categorical(corpus["nation"])
    pos_weights = (
        corpus["pos_group"].value_counts(normalize=True).reindex(POS_GROUPS, fill_value=0.0).to_numpy()
    )

    return {
        "n": n, "use_spline": use_spline, "knots": list(AGE_KNOTS), "age_cols": age_cols,
        "X_age_std": (X_age_raw - age_mean) / age_sd, "age_mean": age_mean, "age_sd": age_sd,
        "strength_std": (strength - strength_mean) / strength_sd,
        "strength_mean": strength_mean, "strength_sd": strength_sd,
        "y_std": (y - y_mean) / y_sd, "y_mean": y_mean, "y_sd": y_sd,
        "pos_codes": pos_cat.codes, "pos_categories": list(pos_cat.categories), "pos_weights": pos_weights,
        "nation_codes": nation_cat.codes, "nation_categories": list(nation_cat.categories),
    }


def fit_model(
    design: dict[str, Any], *, use_strength: bool = True, draws: int = DRAWS, tune: int = TUNE,
    chains: int = CHAINS, target_accept: float = TARGET_ACCEPT, seed: int | None = None,
    progressbar: bool = False, cores: int | None = None,
) -> az.InferenceData:
    """Fit `y_std ~ Normal(mu, sigma)`, `mu = alpha + f(age)_std + beta*
    strength_std + gamma_pos + u_nation` (see module docstring) on `design`
    (`build_design`). `use_strength=False` fits the same model with the
    `beta*strength_std` term dropped -- the "what does the league term
    absorb" comparison the brief asks for. Non-centred `u_nation` (the only
    hierarchical term); everything else is a plain, standardised-scale
    prior."""
    seed = config.RANDOM_SEED if seed is None else seed
    coords = {
        "age_basis": design["age_cols"], "pos": design["pos_categories"], "nation": design["nation_categories"],
    }
    with pm.Model(coords=coords):
        alpha = pm.Normal("alpha", 0.0, 2.5)
        b_age = pm.Normal("b_age", 0.0, 2.5, dims="age_basis")
        mu = alpha + pm.math.dot(design["X_age_std"], b_age)

        if use_strength:
            beta = pm.Normal("beta", 0.0, 2.5)
            mu = mu + beta * design["strength_std"]

        gamma_pos = pm.Normal("gamma_pos", 0.0, 2.5, dims="pos")
        mu = mu + gamma_pos[design["pos_codes"]]

        sigma_n = pm.HalfNormal("sigma_n", 1.0)
        z_nation = pm.Normal("z_nation", 0.0, 1.0, dims="nation")
        u_nation = pm.Deterministic("u_nation", z_nation * sigma_n, dims="nation")
        mu = mu + u_nation[design["nation_codes"]]

        sigma = pm.HalfNormal("sigma", 1.0)
        pm.Normal("y_std", mu=mu, sigma=sigma, observed=design["y_std"])

        idata = pm.sample(
            draws=draws, tune=tune, chains=chains, target_accept=target_accept,
            random_seed=seed, progressbar=progressbar, cores=cores or min(chains, 4),
        )
        pm.sample_posterior_predictive(idata, random_seed=seed, progressbar=progressbar, extend_inferencedata=True)
    return idata


def _hdi(samples: np.ndarray, prob: float = 0.9) -> tuple[float, float]:
    """Highest-density interval of a 1-D sample (same construction as
    `src.league_strength._hdi`/`src.youth_panel._hdi` -- duplicated per
    those modules' own comment on why)."""
    s = np.sort(np.asarray(samples))
    n = len(s)
    n_in = max(int(np.floor(prob * n)), 1)
    n_out = n - n_in
    if n_out <= 0:
        return float(s[0]), float(s[-1])
    widths = s[n_in:] - s[:n_out]
    lo = int(np.argmin(widths))
    return float(s[lo]), float(s[lo + n_in])


def _eval_age_std(eval_ages: list[float] | tuple[float, ...], design: dict[str, Any]) -> np.ndarray:
    """Age design columns for `eval_ages`, on the SAME branch (spline vs.
    quadratic) and standardisation (`age_mean`/`age_sd`) as `design`'s own
    fit -- `age_design`'s `n` argument is `design["n"]`, not
    `len(eval_ages)`, exactly so a handful of evaluation ages reuses the
    fit's own branch rather than picking their own."""
    raw, _, use_spline = age_design(np.asarray(eval_ages, dtype=float), design["n"], tuple(design["knots"]))
    if use_spline != design["use_spline"]:
        raise AssertionError("age_design branch mismatch between fit and evaluation")
    return (raw - design["age_mean"]) / design["age_sd"]


def age_curve(
    idata: az.InferenceData, design: dict[str, Any], eval_ages: tuple[int, ...] = EVAL_AGES, hdi_prob: float = 0.9,
) -> list[dict[str, Any]]:
    """Expected `y` (raw npG+A/90) at each of `eval_ages`, 90% HDI -- the
    population-average curve: origin strength held at the corpus mean
    (`strength_std = 0`), position at the corpus's own frequency-weighted
    average of `gamma_pos` (`design["pos_weights"]`), nation effect at 0
    (`u_nation` excluded -- the marginal curve, not any one nation's own).
    """
    X_eval_std = _eval_age_std(eval_ages, design)
    alpha = idata.posterior["alpha"].values.reshape(-1)
    b_age = idata.posterior["b_age"].values.reshape(-1, X_eval_std.shape[1])
    gamma_pos = idata.posterior["gamma_pos"].values.reshape(-1, len(design["pos_categories"]))
    mu_std_base = alpha + gamma_pos @ design["pos_weights"]
    age_contrib = X_eval_std @ b_age.T  # (n_eval, n_draws)
    y_draws = (mu_std_base[None, :] + age_contrib) * design["y_sd"] + design["y_mean"]

    rows = []
    for age, draws in zip(eval_ages, y_draws, strict=True):
        lo, hi = _hdi(draws, hdi_prob)
        rows.append({"age": int(age), "median": round(float(np.median(draws)), 4),
                     "lo": round(lo, 4), "hi": round(hi, 4)})
    return rows


def diff_between_ages(
    idata: az.InferenceData, design: dict[str, Any], age_a: int = 21, age_b: int = 24, hdi_prob: float = 0.9,
) -> dict[str, Any]:
    """`y(age_a) - y(age_b)` with its 90% HDI ("arriving at 21 vs 24").
    Every term but `f(age)` is identical between the two ages for the same
    posterior draw, so it cancels exactly -- no need to add alpha/gamma_pos/
    u_nation back in, only the two ages' own spline/quadratic contrast."""
    X_eval_std = _eval_age_std([age_a, age_b], design)
    b_age = idata.posterior["b_age"].values.reshape(-1, X_eval_std.shape[1])
    diff_raw = ((X_eval_std[0] - X_eval_std[1]) @ b_age.T) * design["y_sd"]
    lo, hi = _hdi(diff_raw, hdi_prob)
    return {"age_a": age_a, "age_b": age_b, "median": round(float(np.median(diff_raw)), 4),
            "lo": round(lo, 4), "hi": round(hi, 4)}


def beta_summary(idata: az.InferenceData, design: dict[str, Any], hdi_prob: float = 0.9) -> dict[str, Any] | None:
    """beta (raw scale: y per unit of `origin_strength`, i.e. per unit of
    m_L) with its 90% HDI; `None` for a fit with `use_strength=False`
    (`beta` isn't in that model)."""
    if "beta" not in idata.posterior:
        return None
    beta_raw = idata.posterior["beta"].values.reshape(-1) * (design["y_sd"] / design["strength_sd"])
    lo, hi = _hdi(beta_raw, hdi_prob)
    return {"median": round(float(np.median(beta_raw)), 4), "lo": round(lo, 4), "hi": round(hi, 4)}


def home_nation_effect(
    idata: az.InferenceData, design: dict[str, Any], home_code: str, hdi_prob: float = 0.9,
) -> dict[str, Any] | None:
    """The home nation's own `u_nation` (raw npG+A/90 scale), 90% HDI, or
    `None` when the home nation has no rows in this corpus (all its
    exports were censored, e.g. a very small peer set)."""
    if home_code not in design["nation_categories"]:
        return None
    u_raw = idata.posterior["u_nation"].sel(nation=home_code).values.reshape(-1) * design["y_sd"]
    lo, hi = _hdi(u_raw, hdi_prob)
    return {"median": round(float(np.median(u_raw)), 4), "lo": round(lo, 4), "hi": round(hi, 4)}


def diagnostics_summary(idata: az.InferenceData) -> dict[str, Any]:
    """R-hat/ESS across the model's fixed-effect parameters plus the
    divergence count and `sigma_n`'s posterior median (same construction as
    `src.league_strength.diagnostics_summary`). `beta` is included only
    when present (the `use_strength=False` fit has none)."""
    var_names = [v for v in ("alpha", "b_age", "beta", "gamma_pos", "sigma_n", "sigma") if v in idata.posterior]
    summary = az.summary(idata, var_names=var_names, ci_prob=0.9)
    return {
        "max_rhat": round(float(summary["r_hat"].max()), 4),
        "min_ess_bulk": round(float(summary["ess_bulk"].min()), 1),
        "min_ess_tail": round(float(summary["ess_tail"].min()), 1),
        "n_divergences": int(idata.sample_stats["diverging"].values.sum()),
        "sigma_n_median": round(float(idata.posterior["sigma_n"].median()), 4),
    }


def ppc_summary(idata: az.InferenceData, design: dict[str, Any]) -> dict[str, Any]:
    """Observed vs. replicated `y` (raw npG+A/90 scale): mean, sd, 10th/90th
    percentile. Replicated statistics are computed per posterior-predictive
    draw, then averaged over draws (same pattern as
    `src.league_strength.ppc_summary`)."""
    rep_std = idata.posterior_predictive["y_std"].values
    rep_std = rep_std.reshape(-1, rep_std.shape[-1])
    rep = rep_std * design["y_sd"] + design["y_mean"]
    obs = design["y_std"] * design["y_sd"] + design["y_mean"]

    def _stats(a: np.ndarray) -> dict[str, float]:
        return {"mean": round(float(np.mean(a)), 4), "sd": round(float(np.std(a)), 4),
                "p10": round(float(np.percentile(a, 10)), 4), "p90": round(float(np.percentile(a, 90)), 4)}

    per_draw = np.array([[row.mean(), row.std(), np.percentile(row, 10), np.percentile(row, 90)] for row in rep])
    replicated = {"mean": round(float(per_draw[:, 0].mean()), 4), "sd": round(float(per_draw[:, 1].mean()), 4),
                 "p10": round(float(per_draw[:, 2].mean()), 4), "p90": round(float(per_draw[:, 3].mean()), 4)}
    return {"observed": _stats(obs), "replicated": replicated}


# =============================================================================
# Validation: leave-one-nation-out
# =============================================================================


def run_lono(
    corpus: pd.DataFrame, home_code: str, *, draws: int = LONO_DRAWS, tune: int = LONO_TUNE,
    chains: int = LONO_CHAINS, target_accept: float = TARGET_ACCEPT, seed: int | None = None,
) -> dict[str, Any]:
    """Refit the WITH-strength model excluding the home nation's own rows:
    does the age curve move? Lighter sampling budget (2 chains x 500 draws
    by default, same convention as `src.league_strength.run_oos_validation`)
    -- this refit exists to validate the model, its own posterior isn't
    reported beyond the comparison below. `n_excluded` is always reported,
    even when the home nation has no rows to exclude (`n_excluded = 0`,
    `diff_21_24`/`beta` absent) or the remainder is empty (shouldn't happen
    in the live data, guarded against regardless).
    """
    seed = config.RANDOM_SEED if seed is None else seed
    n_excluded = int((corpus["nation"] == home_code).sum())
    sub = corpus[corpus["nation"] != home_code].reset_index(drop=True)
    if sub.empty:
        return {"n_excluded": n_excluded, "n": 0}

    design = build_design(sub)
    t0 = time.time()
    idata = fit_model(design, use_strength=True, draws=draws, tune=tune, chains=chains,
                      target_accept=target_accept, seed=seed)
    runtime_s = round(time.time() - t0, 1)

    return {
        "n_excluded": n_excluded, "n": design["n"],
        "diff_21_24": diff_between_ages(idata, design),
        "beta": beta_summary(idata, design),
        "diagnostics": diagnostics_summary(idata),
        "runtime_s": runtime_s,
    }


# =============================================================================
# Figure
# =============================================================================


def render_figure(corpus: pd.DataFrame, curve: list[dict[str, Any]], home_code: str, out_path: Path) -> None:
    """The fitted curve with its 90% band, the home nation's own exports as
    points against every other peer export, and a rug of every corpus
    player's age at export along the bottom axis."""
    ages = [r["age"] for r in curve]
    med = [r["median"] for r in curve]
    lo = [r["lo"] for r in curve]
    hi = [r["hi"] for r in curve]

    fig, ax = plt.subplots(figsize=(8.5, 5.6))
    fig.patch.set_facecolor(CREAM)
    ax.set_facecolor(CREAM)

    ax.plot(ages, med, color=NAVY, lw=2.0, zorder=3, label="Fitted curve (90% band)")
    ax.fill_between(ages, lo, hi, color=NAVY, alpha=0.15, zorder=1, lw=0)

    other = corpus[corpus["nation"] != home_code]
    home = corpus[corpus["nation"] == home_code]
    ax.scatter(other["age_export"], other["y"], color=MUTED, s=16, alpha=0.55, zorder=2,
              label="Other peer exports", edgecolors="none")
    if not home.empty:
        ax.scatter(home["age_export"], home["y"], color=OXBLOOD, s=42, zorder=4,
                  edgecolors=CREAM, linewidths=0.6, label=f"{home_code} exports")

    ymin, ymax = ax.get_ylim()
    rug_y = ymin - 0.05 * (ymax - ymin)
    ax.plot(corpus["age_export"], np.full(len(corpus), rug_y), marker="|", linestyle="none",
           color=RULE, markersize=9, zorder=1, label="Age at export (all)")
    ax.set_ylim(rug_y - 0.03 * (ymax - ymin), ymax)

    ax.set_xlabel("Age at first top-9 season", fontsize=10, fontfamily="sans-serif", color=INK)
    ax.set_ylabel("Mean npG+A/90, league-adjusted (first two top-9 seasons)", fontsize=10,
                 fontfamily="sans-serif", color=INK)
    ax.set_title("Age at export and production", fontsize=13, fontfamily="serif", color=INK, loc="left")
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
    corpus: pd.DataFrame, design: dict[str, Any], curve: list[dict[str, Any]], y24: dict[str, Any],
    diff: dict[str, Any], beta: dict[str, Any] | None, home_effect: dict[str, Any] | None,
    diagnostics: dict[str, Any], ppc: dict[str, Any], no_strength: dict[str, Any], lono: dict[str, Any],
    home_code: str, fit_meta: dict[str, Any],
) -> dict[str, Any]:
    """Pure assembly of the JSON shape described in the module docstring; no
    fitting here, so this is testable on hand-built inputs. `curve` is the
    report's age table (19/21/23/25/27, spec's own evaluation ages); `y24`
    is the same `age_curve` computation at 24 alone, needed by slide 4b's
    "arriving at 21 ... those arriving at 24 ..." sentence but not part of
    the table."""
    age = corpus["age_export"]
    home_rows = corpus[corpus["nation"] == home_code]
    return {
        "n": int(len(corpus)),
        "age_range": {"min": float(age.min()), "max": float(age.max())},
        "n_seasons_counts": {str(k): int(v) for k, v in corpus["n_seasons"].value_counts().items()},
        "origin_source_counts": {str(k): int(v) for k, v in corpus["origin_source"].value_counts().items()},
        "use_spline": bool(design["use_spline"]), "knots": design["knots"],
        "age_curve": curve,
        "y24": y24,
        "diff_21_24": diff,
        "beta": beta,
        "home_nation_effect": home_effect,
        "home_median_age": float(home_rows["age_export"].median()) if len(home_rows) else None,
        "home_code": home_code,
        "diagnostics": diagnostics,
        "ppc": ppc,
        "no_strength": no_strength,
        "lono": lono,
        "fit": fit_meta,
    }


def main() -> None:
    logging_setup()
    config.ensure_dirs()

    cfg = config.leagues()
    peers = config.PEER_COUNTRIES
    groups = config.features()["groups"]
    features_by_group = {g: read_parquet(config.PROCESSED_DIR / f"features_{g}.parquet") for g in groups}
    tables = read_parquet(config.PROCESSED_DIR / "fbref_players.parquet")
    ls_path = config.PROCESSED_DIR / "league_strength.json"
    ls = json.loads(ls_path.read_text(encoding="utf-8")) if ls_path.exists() else {"leagues": []}
    m_l_map = {r["league"]: r["median"] for r in ls.get("leagues", [])}
    uefa_multipliers = config.league_quality()["multipliers"]

    corpus = build_corpus(features_by_group, tables, peers, cfg["headline"], m_l_map, uefa_multipliers)
    LOG.info("corpus: %d rows, %d nations, age range %.0f-%.0f", len(corpus), corpus["nation"].nunique(),
             corpus["age_export"].min(), corpus["age_export"].max())

    design = build_design(corpus)
    LOG.info("age design: %s (%s branch)", design["age_cols"], "spline" if design["use_spline"] else "quadratic")

    t0 = time.time()
    idata = fit_model(design, use_strength=True, seed=config.RANDOM_SEED)
    runtime_s = round(time.time() - t0, 1)
    LOG.info("main fit: %.1f s", runtime_s)

    curve = age_curve(idata, design)
    y24 = age_curve(idata, design, eval_ages=(24,))[0]
    diff = diff_between_ages(idata, design)
    beta = beta_summary(idata, design)
    home_effect = home_nation_effect(idata, design, config.HOME)
    diagnostics = diagnostics_summary(idata)
    ppc = ppc_summary(idata, design)
    LOG.info("curve: %s", curve)
    LOG.info("diff 21 vs 24: %s; beta: %s; home effect: %s", diff, beta, home_effect)
    LOG.info("diagnostics: %s", diagnostics)

    t0 = time.time()
    idata_ns = fit_model(design, use_strength=False, seed=config.RANDOM_SEED)
    runtime_ns_s = round(time.time() - t0, 1)
    diagnostics_ns = diagnostics_summary(idata_ns)
    no_strength = {
        "diagnostics": diagnostics_ns,
        "home_nation_effect": home_nation_effect(idata_ns, design, config.HOME),
        "runtime_s": runtime_ns_s,
    }
    LOG.info("no-strength fit: %.1f s, sigma_n %.4f vs %.4f with strength", runtime_ns_s,
             diagnostics_ns["sigma_n_median"], diagnostics["sigma_n_median"])

    lono = run_lono(corpus, config.HOME, seed=config.RANDOM_SEED)
    if lono.get("diff_21_24"):
        lono["shift_diff_21_24"] = round(lono["diff_21_24"]["median"] - diff["median"], 4)
    LOG.info("lono: %s", lono)

    fit_meta = {"n": design["n"], "runtime_s": runtime_s, "runtime_no_strength_s": runtime_ns_s,
               "runtime_lono_s": lono.get("runtime_s", 0.0)}
    result = assemble_output(corpus, design, curve, y24, diff, beta, home_effect, diagnostics, ppc,
                             no_strength, lono, config.HOME, fit_meta)

    out_json = config.PROCESSED_DIR / "export_age_model.json"
    out_json.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    LOG.info("wrote %s", out_json)

    render_figure(corpus, curve, config.HOME, config.OUTPUTS_DIR / "export_age_model.svg")
    LOG.info("done: %s", config.NATION)


if __name__ == "__main__":
    main()
