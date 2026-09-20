"""League strength from the transfer graph (M2): a hierarchical Bayesian model
identified from league movers, PyMC 5.

Why movers. A naive hierarchical Poisson fit on *all* players (the controller
spike, `/private/tmp/.../spike_pymc.py`-style) recovers each league's *goal
environment*, not its strength: with one row per player, per-player effects
are shrunk hard toward a common mean and the league effect absorbs whatever
talent mix that league happens to field (Eredivisie's open, high-scoring
football reads as "strongest league", Serie A's tight defending as
"weakest" -- the opposite of the UEFA ranking). Identification of *strength*
(as opposed to *environment*) needs a within-player contrast: the same
player's rate before and after a league change tells you how much of the
change is the player and how much is the league. Restricting the corpus to
movers -- players observed in >= 2 distinct leagues -- is what buys that
contrast; a wide `sigma_u` prior on the player effect (HalfNormal(2), see
`fit_model`) then lets each mover's own two-or-more rows do almost all the
identifying work, rather than being pooled away.

This is the same logic behind adjusted plus-minus / RAPM ratings in other
team sports (Kharrat, McHale and Pena, 2020; see also Hvattum, 2019's
review): within-subject variation, not cross-sectional level, isolates the
effect of interest.

Data (`build_movers`): `features_{FW,MF,DF}.parquet` for the running nation
(these already cover every fetched nationality, not just the home one --
this model is nation-independent), rows with `min >= 450` and `born` known,
`src.utils.collapse_player_seasons` applied (same-season, different-club
duplicates collapsed to one row; see that function's docstring -- `min` is
summed across the season's clubs but `npg`/`ast` are taken from the
most-minutes club only, a known, accepted approximation shared with every
other caller of this utility), restricted to players with >= 2 distinct
leagues across their qualifying rows ("movers").

Model (`fit_model`), PyMC 5, non-centred parameterisation throughout:

    y ~ Poisson(exp(alpha + b_league + b_pos + b_age*age_c + b_age2*age_c^2
                     + u_player) * exposure)

    y            = npg + ast (non-penalty goals + assists), integer
    exposure     = minutes / 90
    age_c        = (age - 26) / 5, age = season-start year - birth year
    alpha        ~ Normal(-2, 1)
    b_league     = z_league * sigma_league,  z_league ~ Normal(0, 1),
                   sigma_league ~ HalfNormal(0.5)          (non-centred)
    b_pos        ~ Normal(0, 1), one per FW/MF/DF
    b_age,b_age2 ~ Normal(0, 0.5)
    u_player     = z_player * sigma_player,  z_player ~ Normal(0, 1),
                   sigma_player ~ HalfNormal(2)             (non-centred,
                   deliberately wide -- player effects are meant to be
                   close to unpooled; the within-player contrast is the
                   whole identification strategy, see above)

Sampled with NUTS (Hoffman and Gelman, 2014), 4 chains x 1000 draws after
1000 tune, target_accept 0.9, `random_seed = config.RANDOM_SEED` -- PyMC
(Abril-Pla et al., 2023), diagnostics and the posterior predictive check via
ArviZ (Kumar et al., 2019).

Strength scale: `m_L = exp(beta_ENG - beta_L)`, the rate multiplier that
converts a rate observed in league L to its Premier-League-equivalent rate
(m_ENG = 1 by construction; a league easier to score in than the Premier
League has beta_L > beta_ENG, hence m_L < 1).

Validation (`ppc_summary`, `run_oos_validation`, `spearman_check`):

  1. Posterior predictive check: replicated `y` against observed `y`, one
     summary statistic each (share of zeros, mean, 90th percentile) plus a
     figure -- posterior predictive checking generally follows Gelman et al.
     (2013); the log/WAIC-style model-evaluation literature this sits in is
     surveyed in Vehtari, Gelman and Gabry (2017).
  2. Out-of-sample: refit on seasons before the metrics season, score each
     mover's first metrics-season row after a league change against three
     predictors -- "same rate as before", rate x UEFA-multiplier ratio, and
     the model -- by mean Poisson log predictive density and MAE on the
     per-90 rate (`score_predictions`, pure and unit-testable on a toy
     table).
  3. Spearman rank correlation between the model's league medians and
     `config/league_quality.yaml`'s UEFA-coefficient-derived multipliers,
     plus the three largest disagreements.

Output: `data/processed/<nation>/league_strength.json` and two figures,
`outputs/<nation>/league_strength.svg` (dot + 90% HDI per league, sorted,
UEFA multiplier as a hollow marker) and
`outputs/<nation>/league_strength_ppc.svg` (observed vs. replicated `y`).
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
from scipy.stats import poisson as poisson_dist
from scipy.stats import spearmanr

from src import config
from src.figstyle import CREAM, CREAM_TINT, INK, NAVY, OXBLOOD, RULE, use_style
from src.logging_setup import setup as logging_setup
from src.utils import collapse_player_seasons, read_parquet, season_label

LOG = logging.getLogger(__name__)

MIN_MINUTES = 450
REFERENCE_LEAGUE = "ENG-Premier League"
POS_GROUPS = ["FW", "MF", "DF"]
GROUPS = POS_GROUPS  # alias used by main()

# Matplotlib defaults shared with the rest of the report's figures.
use_style()


# =============================================================================
# Data
# =============================================================================


def build_movers(features_by_group: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """FW+MF+DF rows with `min >= MIN_MINUTES` and `born` known, collapsed by
    `collapse_player_seasons`, restricted to players in >= 2 distinct
    leagues ("movers"). Adds `y` (npg+ast), `exposure` (min/90), `age`
    (season-start year - birth year) and `age_c` ((age-26)/5).
    """
    frames = []
    for g, df in features_by_group.items():
        sub = df[(df["min"] >= MIN_MINUTES) & df["born"].notna()].copy()
        if "pos_group" not in sub.columns:
            sub["pos_group"] = g
        frames.append(sub)
    corpus = pd.concat(frames, ignore_index=True)
    shrunk = [c for c in ("npg_p90_shrunk", "ast_p90_shrunk") if c in corpus.columns]
    corpus = collapse_player_seasons(corpus, rate_cols=shrunk)

    leagues_per_player = corpus.groupby("player_key")["league"].nunique()
    mover_keys = set(leagues_per_player[leagues_per_player >= 2].index)
    movers = corpus[corpus["player_key"].isin(mover_keys)].copy().reset_index(drop=True)

    movers["y"] = (movers["npg"] + movers["ast"]).clip(lower=0).astype(int)
    movers["exposure"] = movers["min"] / 90.0
    movers["age"] = movers["season"].str[:4].astype(int) - movers["born"].astype(int)
    movers["age_c"] = (movers["age"].astype(float) - 26.0) / 5.0
    return movers


def count_transitions(movers: pd.DataFrame) -> pd.DataFrame:
    """One row per adjacent-season league change for each mover (rows sorted
    by season -- season labels ("2020-2021", ...) sort lexicographically in
    chronological order). A "transition" is a pair of consecutive
    *qualifying* rows (>= MIN_MINUTES, collapsed) for one player whose league
    differs; seasons in between where the player didn't qualify are simply
    skipped, not treated as a gap.
    """
    rows = []
    for key, g in movers.sort_values("season").groupby("player_key"):
        prev = None
        for _, r in g.iterrows():
            if prev is not None and prev["league"] != r["league"]:
                rows.append({
                    "player_key": key, "from_league": prev["league"], "to_league": r["league"],
                    "from_season": prev["season"], "to_season": r["season"],
                })
            prev = r
    return pd.DataFrame(rows, columns=["player_key", "from_league", "to_league", "from_season", "to_season"])


def n_transitions_by_league(transitions: pd.DataFrame) -> dict[str, int]:
    """Number of transitions touching each league, as origin or destination."""
    counts: dict[str, int] = {}
    if transitions.empty:
        return counts
    for col in ("from_league", "to_league"):
        for lg, n in transitions[col].value_counts().items():
            counts[lg] = counts.get(lg, 0) + int(n)
    return counts


# =============================================================================
# Model
# =============================================================================


def fit_model(
    movers: pd.DataFrame, *, draws: int = 1000, tune: int = 1000, chains: int = 4,
    target_accept: float = 0.9, seed: int | None = None, progressbar: bool = False,
    cores: int | None = None,
) -> az.InferenceData:
    """Fit the hierarchical Poisson model on a movers frame (see module
    docstring). Returns an InferenceData with `league`/`pos`/`player` dims
    on `b_league`/`b_pos`/`u_player`, `posterior_predictive.y` and
    `sample_stats.diverging`.
    """
    seed = config.RANDOM_SEED if seed is None else seed
    leagues_cat = pd.Categorical(movers["league"])
    pos_cat = pd.Categorical(movers["pos_group"], categories=POS_GROUPS)
    if pos_cat.isna().any():
        raise ValueError(f"pos_group has values outside {POS_GROUPS}")
    player_cat = pd.Categorical(movers["player_key"])

    coords = {
        "league": list(leagues_cat.categories),
        "pos": list(pos_cat.categories),
        "player": list(player_cat.categories),
    }
    age_c = movers["age_c"].to_numpy()
    exposure = movers["exposure"].to_numpy()
    y = movers["y"].to_numpy()

    with pm.Model(coords=coords):
        alpha = pm.Normal("alpha", -2.0, 1.0)

        sigma_league = pm.HalfNormal("sigma_league", 0.5)
        z_league = pm.Normal("z_league", 0.0, 1.0, dims="league")
        b_league = pm.Deterministic("b_league", z_league * sigma_league, dims="league")

        b_pos = pm.Normal("b_pos", 0.0, 1.0, dims="pos")

        b_age = pm.Normal("b_age", 0.0, 0.5)
        b_age2 = pm.Normal("b_age2", 0.0, 0.5)

        sigma_player = pm.HalfNormal("sigma_player", 2.0)
        z_player = pm.Normal("z_player", 0.0, 1.0, dims="player")
        u_player = pm.Deterministic("u_player", z_player * sigma_player, dims="player")

        lam = pm.math.exp(
            alpha + b_league[leagues_cat.codes] + b_pos[pos_cat.codes]
            + b_age * age_c + b_age2 * age_c**2 + u_player[player_cat.codes]
        ) * exposure
        pm.Poisson("y", mu=lam, observed=y)

        idata = pm.sample(
            draws=draws, tune=tune, chains=chains, target_accept=target_accept,
            random_seed=seed, progressbar=progressbar, cores=cores or min(chains, 4),
        )
        pm.sample_posterior_predictive(idata, random_seed=seed, progressbar=progressbar, extend_inferencedata=True)

    return idata


def _hdi(samples: np.ndarray, prob: float = 0.9) -> tuple[float, float]:
    """Highest-density interval of a 1-D sample: the narrowest interval
    covering `prob` mass (the standard HDI construction; implemented
    directly rather than via `az.hdi` so the result doesn't depend on that
    function's array-vs-xarray dispatch across ArviZ versions)."""
    s = np.sort(np.asarray(samples))
    n = len(s)
    n_in = max(int(np.floor(prob * n)), 1)
    n_out = n - n_in
    if n_out <= 0:
        return float(s[0]), float(s[-1])
    widths = s[n_in:] - s[:n_out]
    lo = int(np.argmin(widths))
    return float(s[lo]), float(s[lo + n_in])


def league_strength_table(
    idata: az.InferenceData, transitions_counts: dict[str, int], uefa_multipliers: dict[str, float],
    reference: str = REFERENCE_LEAGUE, hdi_prob: float = 0.9,
) -> pd.DataFrame:
    """m_L = exp(beta_ref - beta_L) per league: median, 90% HDI, the number
    of transitions touching the league, and its UEFA multiplier. Sorted by
    median descending.
    """
    b = idata.posterior["b_league"]
    leagues = [str(x) for x in b.coords["league"].values]
    if reference not in leagues:
        raise ValueError(f"reference league {reference!r} not among fitted leagues {leagues}")
    b_ref = b.sel(league=reference).values.reshape(-1)
    rows = []
    for lg in leagues:
        b_l = b.sel(league=lg).values.reshape(-1)
        m = np.exp(b_ref - b_l)
        lo, hi = _hdi(m, hdi_prob)
        rows.append({
            "league": lg, "median": round(float(np.median(m)), 4),
            "hdi_lo": round(lo, 4), "hdi_hi": round(hi, 4),
            "n_transitions": int(transitions_counts.get(lg, 0)),
            "uefa": float(uefa_multipliers.get(lg)) if lg in uefa_multipliers else None,
        })
    return pd.DataFrame(rows).sort_values("median", ascending=False).reset_index(drop=True)


def diagnostics_summary(idata: az.InferenceData) -> dict[str, Any]:
    """R-hat/ESS across the model's parameters plus the divergence count."""
    summary = az.summary(idata, var_names=["alpha", "b_league", "b_pos", "b_age", "b_age2",
                                            "sigma_league", "sigma_player"], ci_prob=0.9)
    return {
        "max_rhat": round(float(summary["r_hat"].max()), 4),
        "min_ess_bulk": round(float(summary["ess_bulk"].min()), 1),
        "min_ess_tail": round(float(summary["ess_tail"].min()), 1),
        "n_divergences": int(idata.sample_stats["diverging"].values.sum()),
        "sigma_league_median": round(float(idata.posterior["sigma_league"].median()), 4),
        "sigma_player_median": round(float(idata.posterior["sigma_player"].median()), 4),
    }


# =============================================================================
# Validation 1: posterior predictive check
# =============================================================================


def _y_stats(y: np.ndarray) -> dict[str, float]:
    y = np.asarray(y)
    return {
        "zero_share": round(float((y == 0).mean()), 4),
        "mean": round(float(y.mean()), 4),
        "p90": round(float(np.percentile(y, 90)), 4),
    }


def ppc_summary(idata: az.InferenceData, observed_y: np.ndarray) -> dict[str, Any]:
    """Observed vs. replicated `y`: share of zeros, mean, 90th percentile.
    The replicated statistics are each computed per posterior-predictive
    draw, then averaged over draws.
    """
    rep = idata.posterior_predictive["y"].values  # (chain, draw, obs)
    rep = rep.reshape(-1, rep.shape[-1])
    per_draw = np.array([[
        (row == 0).mean(), row.mean(), np.percentile(row, 90),
    ] for row in rep])
    replicated = {
        "zero_share": round(float(per_draw[:, 0].mean()), 4),
        "mean": round(float(per_draw[:, 1].mean()), 4),
        "p90": round(float(per_draw[:, 2].mean()), 4),
    }
    return {"observed": _y_stats(observed_y), "replicated": replicated}


def render_ppc_figure(idata: az.InferenceData, observed_y: np.ndarray, out_path: Path) -> None:
    """Bar chart of the observed vs. mean-replicated count distribution
    (y = 0, 1, 2, 3, 4, 5+)."""
    rep = idata.posterior_predictive["y"].values.reshape(-1, idata.posterior_predictive["y"].shape[-1])
    bins = [0, 1, 2, 3, 4, 5]
    labels = ["0", "1", "2", "3", "4", "5+"]

    def _counts(y: np.ndarray) -> np.ndarray:
        y = np.clip(y, 0, 5)
        return np.array([(y == b).mean() for b in bins])

    obs_share = _counts(np.asarray(observed_y))
    rep_share = np.array([_counts(row) for row in rep]).mean(axis=0)

    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    fig.patch.set_facecolor(CREAM)
    ax.set_facecolor(CREAM)
    x = np.arange(len(labels))
    w = 0.36
    ax.bar(x - w / 2, obs_share, width=w, color=NAVY, label="Observed")
    ax.bar(x + w / 2, rep_share, width=w, color=OXBLOOD, alpha=0.85, label="Replicated (posterior mean)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10, fontfamily="sans-serif", color=INK)
    ax.set_ylabel("Share of player-seasons", fontsize=10, fontfamily="sans-serif", color=INK)
    ax.set_xlabel("npG + A that season", fontsize=10, fontfamily="sans-serif", color=INK)
    ax.set_title("Posterior predictive check", fontsize=13, fontfamily="sans-serif", color=INK, loc="left")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(RULE)
    ax.tick_params(colors=INK)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK)
    plt.tight_layout()
    plt.savefig(out_path, format="svg", facecolor=CREAM, edgecolor="none")
    plt.close(fig)
    LOG.info("wrote %s", out_path)


# =============================================================================
# Validation 2: out-of-sample on the last season
# =============================================================================


def score_predictions(df: pd.DataFrame, method_cols: dict[str, str]) -> pd.DataFrame:
    """Score a table of OOS predictions.

    `df` needs `y` (observed count) and `exposure` (minutes/90) columns plus
    one predicted-rate column per method (named in `method_cols`, {method
    name: column name}). For each method: mean Poisson log predictive
    density (log pmf of the observed `y` under a Poisson with mean
    `rate * exposure`) and MAE between the predicted rate and the observed
    rate (`y / exposure`).
    """
    obs_rate = df["y"] / df["exposure"]
    rows = []
    for name, col in method_cols.items():
        rate = df[col].clip(lower=1e-6)
        lam = (rate * df["exposure"]).clip(lower=1e-6)
        logpd = float(poisson_dist.logpmf(df["y"], lam).mean())
        mae = float((rate - obs_rate).abs().mean())
        rows.append({"method": name, "log_pred_density": round(logpd, 4), "mae": round(mae, 4)})
    return pd.DataFrame(rows, columns=["method", "log_pred_density", "mae"])


def build_oos_candidates(movers: pd.DataFrame, metrics_season: str) -> pd.DataFrame:
    """Movers whose metrics-season row is their first after a league change
    into that season. For each, the previous (pre-metrics) row's league and
    per-90 rate, and the metrics-season row's league, y, exposure, pos_group
    and age_c.
    """
    rows = []
    for key, g in movers.sort_values("season").groupby("player_key"):
        g = g.reset_index(drop=True)
        metrics_idx = g.index[g["season"] == metrics_season]
        if len(metrics_idx) == 0:
            continue
        i = int(metrics_idx[0])
        if i == 0:
            continue  # no prior row to predict from
        prev, cur = g.loc[i - 1], g.loc[i]
        if prev["league"] == cur["league"]:
            continue  # not a league change landing in the metrics season
        # the baselines start from the pipeline's own shrunk rate (empirical
        # Bayes toward the league median, K minutes) when it is available: a raw
        # zero-goal season would otherwise predict a rate of zero and the
        # Poisson log score would punish the baselines for that, not for the
        # league adjustment under test
        if "npg_p90_shrunk" in g.columns and pd.notna(prev.get("npg_p90_shrunk")):
            prev_rate = float(prev["npg_p90_shrunk"]) + float(prev.get("ast_p90_shrunk", 0.0) or 0.0)
        else:
            prev_rate = (prev["npg"] + prev["ast"]) / (prev["min"] / 90.0)
        rows.append({
            "player_key": key, "pos_group": cur["pos_group"],
            "prev_league": prev["league"], "prev_rate": float(prev_rate),
            "new_league": cur["league"], "y": int(cur["y"]), "exposure": float(cur["exposure"]),
            "age_c": float(cur["age_c"]),
        })
    return pd.DataFrame(rows, columns=["player_key", "pos_group", "prev_league", "prev_rate",
                                        "new_league", "y", "exposure", "age_c"])


def _model_point_estimates(idata: az.InferenceData) -> dict[str, Any]:
    """Posterior medians of every fixed and random effect, for a
    point-prediction OOS rate (not full posterior predictive)."""
    post = idata.posterior
    return {
        "alpha": float(post["alpha"].median()),
        "b_age": float(post["b_age"].median()),
        "b_age2": float(post["b_age2"].median()),
        "b_league": {str(lg): float(post["b_league"].sel(league=lg).median())
                     for lg in post.coords["league"].values},
        "b_pos": {str(p): float(post["b_pos"].sel(pos=p).median()) for p in post.coords["pos"].values},
        "u_player": {str(pl): float(post["u_player"].sel(player=pl).median())
                     for pl in post.coords["player"].values},
    }


def attach_model_predictions(oos: pd.DataFrame, point: dict[str, Any]) -> pd.DataFrame:
    """Model-predicted rate per OOS row from posterior-median point
    estimates (`_model_point_estimates`); a player absent from the training
    fit's `player` coordinate (shouldn't happen by construction, since every
    OOS candidate has a pre-metrics row) falls back to `u_player = 0`."""
    out = oos.copy()

    def _rate(r: pd.Series) -> float:
        u = point["u_player"].get(r["player_key"], 0.0)
        b_l = point["b_league"].get(r["new_league"], 0.0)
        b_p = point["b_pos"].get(r["pos_group"], 0.0)
        log_rate = point["alpha"] + b_l + b_p + point["b_age"] * r["age_c"] + point["b_age2"] * r["age_c"] ** 2 + u
        return float(np.exp(log_rate))

    out["rate_model"] = out.apply(_rate, axis=1)
    return out


def uefa_ratio(moves: pd.DataFrame, multipliers: dict[str, float]) -> pd.Series:
    """m_prev / m_new for each move — the factor a conserved PL-equivalent rate
    implies for the raw rate in the new league."""
    return moves.apply(
        lambda r: multipliers.get(r["prev_league"], np.nan) / multipliers.get(r["new_league"], np.nan),
        axis=1,
    )


def run_oos_validation(
    movers: pd.DataFrame, metrics_season: str, uefa_multipliers: dict[str, float],
    *, draws: int = 500, tune: int = 500, chains: int = 2, target_accept: float = 0.9,
    seed: int | None = None,
) -> dict[str, Any]:
    """Refit on seasons before `metrics_season`, score the resulting model
    against the naive and UEFA-ratio baselines on the metrics-season league
    changes. Lighter sampling budget than the headline fit (2 chains x 500
    draws by default) -- this refit exists to validate the model, its own
    posterior isn't reported.
    """
    train = movers[movers["season"] < metrics_season].reset_index(drop=True)
    candidates = build_oos_candidates(movers, metrics_season)
    if candidates.empty or train.empty:
        return {"metrics_season": metrics_season, "n_candidates": 0, "rows": [], "refit_runtime_s": 0.0}

    t0 = time.time()
    train_idata = fit_model(train, draws=draws, tune=tune, chains=chains,
                            target_accept=target_accept, seed=seed)
    runtime_s = round(time.time() - t0, 1)

    point = _model_point_estimates(train_idata)
    scored = attach_model_predictions(candidates, point)
    scored["rate_naive"] = scored["prev_rate"]
    # multiplier convention (features.py): quality_rate = raw_rate_L × m_L, so a
    # player whose PL-equivalent rate is conserved across a move scores
    # raw_new = raw_prev × m_prev / m_new (more in a weaker league, less in a stronger one)
    scored["rate_uefa"] = scored["prev_rate"] * uefa_ratio(scored, uefa_multipliers)
    scored = scored.dropna(subset=["rate_uefa"])

    table = score_predictions(scored, {"naive": "rate_naive", "uefa": "rate_uefa", "model": "rate_model"})
    return {
        "metrics_season": metrics_season, "n_candidates": int(len(scored)),
        "rows": table.to_dict(orient="records"), "refit_runtime_s": runtime_s,
    }


# =============================================================================
# Validation 3: rank correlation with UEFA multipliers
# =============================================================================


def spearman_check(table: pd.DataFrame) -> dict[str, Any]:
    """Spearman rank correlation between the model's league medians and
    their UEFA multipliers, over leagues with both."""
    sub = table.dropna(subset=["uefa"])
    if len(sub) < 3:
        return {"rho": None, "p": None, "n": int(len(sub))}
    rho, p = spearmanr(sub["median"], sub["uefa"])
    return {"rho": round(float(rho), 4), "p": round(float(p), 6), "n": int(len(sub))}


def top_disagreements(table: pd.DataFrame, n: int = 3) -> list[dict[str, Any]]:
    """The `n` leagues where the model's rank (by median, strongest first)
    and the UEFA rank (by multiplier, strongest first) disagree the most."""
    sub = table.dropna(subset=["uefa"]).copy()
    if sub.empty:
        return []
    sub["model_rank"] = sub["median"].rank(ascending=False, method="min").astype(int)
    sub["uefa_rank"] = sub["uefa"].rank(ascending=False, method="min").astype(int)
    sub["rank_diff"] = (sub["model_rank"] - sub["uefa_rank"]).abs()
    top = sub.sort_values(["rank_diff", "league"], ascending=[False, True]).head(n)
    return [
        {"league": r.league, "model_rank": int(r.model_rank), "uefa_rank": int(r.uefa_rank),
         "model_median": float(r.median), "uefa": float(r.uefa), "rank_diff": int(r.rank_diff)}
        for r in top.itertuples(index=False)
    ]


# =============================================================================
# Figure
# =============================================================================


def render_strength_figure(table: pd.DataFrame, out_path: Path) -> None:
    """Dot + 90% HDI per league, sorted by median descending; the UEFA
    multiplier as a hollow marker alongside."""
    rows = table.sort_values("median", ascending=True).reset_index(drop=True)
    n = len(rows)
    fig, ax = plt.subplots(figsize=(8.0, max(3.5, 0.42 * n + 1.2)))
    fig.patch.set_facecolor(CREAM)
    ax.set_facecolor(CREAM)

    y = np.arange(n)
    for i, r in rows.iterrows():
        ax.plot([r["hdi_lo"], r["hdi_hi"]], [i, i], color=RULE, lw=2.2, zorder=1)
    ax.scatter(rows["median"], y, s=46, color=NAVY, zorder=3, label="Model median (90% HDI)")
    has_uefa = rows["uefa"].notna()
    ax.scatter(rows.loc[has_uefa, "uefa"], y[has_uefa.values], s=52, facecolors="none",
              edgecolors=OXBLOOD, linewidths=1.6, zorder=4, label="UEFA multiplier")

    ax.set_yticks(y)
    ax.set_yticklabels(rows["league"], fontsize=9.5, fontfamily="sans-serif", color=INK)
    ax.axvline(1.0, color=CREAM_TINT, lw=10, zorder=0)
    ax.set_xlabel("m_L  ·  Premier-League-equivalent rate multiplier", fontsize=10,
                 fontfamily="sans-serif", color=INK)
    ax.set_title("League strength: two estimates", fontsize=13, fontfamily="sans-serif", color=INK, loc="left")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(RULE)
    ax.tick_params(colors=INK)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK, loc="lower right")
    plt.tight_layout()
    plt.savefig(out_path, format="svg", facecolor=CREAM, edgecolor="none")
    plt.close(fig)
    LOG.info("wrote %s", out_path)


# =============================================================================
# Assembly / main
# =============================================================================


def assemble_output(
    table: pd.DataFrame, diagnostics: dict[str, Any], ppc: dict[str, Any], oos: dict[str, Any],
    spearman: dict[str, Any], disagreements: list[dict[str, Any]], fit_meta: dict[str, Any],
) -> dict[str, Any]:
    """Pure assembly of the JSON shape described in the module docstring;
    no fitting here, so this is testable on hand-built inputs."""
    return {
        "leagues": table[["league", "median", "hdi_lo", "hdi_hi", "n_transitions", "uefa"]].to_dict(orient="records"),
        "diagnostics": diagnostics,
        "ppc": ppc,
        "oos": oos,
        "spearman": spearman,
        "disagreements": disagreements,
        "fit": fit_meta,
    }


def main() -> None:
    logging_setup()
    config.ensure_dirs()

    features_by_group = {g: read_parquet(config.PROCESSED_DIR / f"features_{g}.parquet") for g in GROUPS}
    movers = build_movers(features_by_group)
    LOG.info("movers corpus: %d rows, %d players, %d seasons", len(movers), movers["player_key"].nunique(),
             movers["season"].nunique())

    transitions = count_transitions(movers)
    transitions_counts = n_transitions_by_league(transitions)
    LOG.info("%d transitions across %d league pairs", len(transitions),
             transitions[["from_league", "to_league"]].drop_duplicates().shape[0] if not transitions.empty else 0)

    uefa_multipliers = config.league_quality()["multipliers"]

    t0 = time.time()
    idata = fit_model(movers, seed=config.RANDOM_SEED)
    runtime_s = round(time.time() - t0, 1)
    LOG.info("main fit: %.1f s", runtime_s)

    table = league_strength_table(idata, transitions_counts, uefa_multipliers)
    diagnostics = diagnostics_summary(idata)
    LOG.info("diagnostics: %s", diagnostics)
    LOG.info("m_L table:\n%s", table.to_string(index=False))

    ppc = ppc_summary(idata, movers["y"].to_numpy())
    LOG.info("ppc: %s", ppc)

    metrics_season = config.seasons()["metrics"]
    oos = run_oos_validation(movers, metrics_season, uefa_multipliers, seed=config.RANDOM_SEED)
    LOG.info("oos (%d candidates): %s", oos["n_candidates"], oos["rows"])

    spearman = spearman_check(table)
    disagreements = top_disagreements(table)
    LOG.info("spearman rho=%s (n=%s); disagreements=%s", spearman["rho"], spearman["n"], disagreements)

    fit_meta = {
        "rows": int(len(movers)), "players": int(movers["player_key"].nunique()),
        "seasons": int(movers["season"].nunique()), "runtime_s": runtime_s,
    }
    result = assemble_output(table, diagnostics, ppc, oos, spearman, disagreements, fit_meta)

    out_json = config.PROCESSED_DIR / "league_strength.json"
    out_json.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    LOG.info("wrote %s", out_json)

    render_strength_figure(table, config.OUTPUTS_DIR / "league_strength.svg")
    render_ppc_figure(idata, movers["y"].to_numpy(), config.OUTPUTS_DIR / "league_strength_ppc.svg")

    LOG.info("done: %s (%s metrics season)", config.NATION, season_label(metrics_season))


if __name__ == "__main__":
    main()
