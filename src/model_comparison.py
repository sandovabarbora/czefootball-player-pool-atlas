"""Three models, one task, five seasons: rolling-origin model comparison
(Task 16, spec section 4b first bullet, M1 core).

Question (football -> analytical): what does a player's season tell us
about the next one, given where he plays, how old he is and -- for exports
-- at what age he moved? Predict next-season league-adjusted production
(`npg_p90_quality + ast_p90_quality` of season t+1) from season t, for
every player-season pair in the corpus with >= 450 minutes in both seasons,
all nationalities (this task, like Task 15's `league_strength`, is
nation-independent: `features_{FW,MF,DF}.parquet` already covers every
fetched nationality).

Rolling-origin evaluation (Hyndman and Athanasopoulos, 2021, chapter 5.10):
for each target season T in `ORIGINS`, train on pairs whose target season is
strictly before T, test on pairs whose target season equals T. This *is*
the "monitor performance over time" exhibit -- the per-origin RMSE/MAE table
makes drift visible season by season, rather than reporting one blended
number.

A real corpus limitation, not a bug: the earliest feature season on file is
2020-2021, so the earliest possible pair (t=2020-2021 -> target=2021-2022)
*is* the first origin -- there is no earlier target season to train on, so
origin 1's training set is empty by construction. `rolling_origin_split`
returns that empty frame faithfully; `main` fits only the two baselines for
that origin (both computable from season-t data alone, see below) and skips
the three learned models there, with a note in the JSON's `notes` list
rather than a silent zero-row fit.

Five models, same features, same splits:
  0. persistence: predict = the player's own composite value in season t
     (`predict_persistence`). No training needed.
  1. shrinkage to league mean: predict = an empirical-Bayes shrinkage of the
     historical (training) target mean for that league toward the overall
     training target mean, weight n/(n+10) (`predict_shrinkage_to_league_mean`);
     falls back to the test season's own value_t mean when training is
     empty (origin 1), since no historical target is available yet and using
     the test season's own *target* there would leak.
  2. hierarchical Bayesian regression (`fit_bayesian`/`predict_bayesian`):
     PyMC, non-centred parameterisation, target ~ Normal(mu, sigma);
     mu = alpha + beta.x (standardised numeric features, including the M2
     league-strength multiplier `m_L` as one more feature) + gamma_league
     (partial pooling) + delta_pos + u_player (partial pooling,
     sigma_u ~ HalfNormal(0.5)); NUTS, 2 chains x 800 draws per origin (see
     `main` for the runtime-budget reduction). Coverage from a normal
     approximation to the posterior predictive interval -- see
     `predict_bayesian`'s docstring for why an approximation, not full
     Monte Carlo sampling, was used.
  3. gradient boosting: scikit-learn `HistGradientBoostingRegressor`,
     default-ish params with early stopping; `league`/`pos_group` passed as
     pandas `category` dtype (sklearn's `categorical_features="from_dtype"`
     default, Pedregosa et al., 2011).
  4. small multilayer perceptron (not an "embedding model" -- PyTorch is not
     installed, so a learned league embedding is not available in sklearn;
     called what it is): `MLPRegressor` on one-hot league/pos_group +
     numeric features, hidden layers (64, 32), early stopping.

Output: `data/processed/<nation>/model_comparison.json` (`assemble_output`)
and figure `outputs/<nation>/model_comparison.svg` (RMSE per origin, one
line per model, persistence dashed).
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pymc as pm

from src import config
from src.logging_setup import setup as logging_setup
from src.utils import collapse_player_seasons, read_parquet

LOG = logging.getLogger(__name__)

MIN_MINUTES = 450
POS_GROUPS = ["FW", "MF", "DF"]
GROUPS = POS_GROUPS

NUMERIC_FEATURES = ["npg_p90_shrunk", "ast_p90_shrunk", "min_share", "age", "cards_p90", "league_multiplier"]
TARGET_LABEL = "npg_p90_quality + ast_p90_quality (season t+1)"

# The five rolling origins: target seasons 2021/22 -> 2025/26 (the brief's
# range). The corpus's current, in-progress season (2026-2027, see
# config/seasons.yaml's "current") is excluded as a target -- its stats are
# incomplete, not a fair evaluation target.
ORIGINS: list[str] = ["2021-2022", "2022-2023", "2023-2024", "2024-2025", "2025-2026"]


# =============================================================================
# Data: pairs and rolling-origin splits
# =============================================================================


def build_pairs(features_by_group: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """One row per player-season pair (season t -> season t+1) with
    `min >= MIN_MINUTES` in both seasons, all pos_groups, all nationalities.

    Season-t's `npg_p90_shrunk, ast_p90_shrunk, min_share, age, cards_p90,
    league, pos_group, league_multiplier` become the feature columns;
    `value_t` is season t's own `npg_p90_quality + ast_p90_quality`
    (used by the persistence baseline); `target` is season t+1's
    `npg_p90_quality + ast_p90_quality` (the label); `target_season` is
    season t+1's label, the column the rolling-origin split keys on.
    """
    frames = []
    for g, df in features_by_group.items():
        sub = df[df["min"] >= MIN_MINUTES].copy()
        if "pos_group" not in sub.columns:
            sub["pos_group"] = g
        frames.append(sub)
    corpus = pd.concat(frames, ignore_index=True)

    rate_cols = [c for c in (*NUMERIC_FEATURES, "npg_p90_quality", "ast_p90_quality") if c in corpus.columns]
    corpus = collapse_player_seasons(corpus, rate_cols=rate_cols)
    corpus["season_start"] = corpus["season"].str[:4].astype(int)
    corpus["value"] = corpus["npg_p90_quality"] + corpus["ast_p90_quality"]

    t_cols = ["player_key", "pos_group", "season_start", "league",
              *NUMERIC_FEATURES, "value"]
    left = corpus[t_cols].rename(columns={"value": "value_t"})
    left["season_start_next"] = left["season_start"] + 1
    right = corpus[["player_key", "pos_group", "season_start", "season", "value"]].rename(
        columns={"season": "target_season", "value": "target"})

    merged = left.merge(
        right, left_on=["player_key", "pos_group", "season_start_next"],
        right_on=["player_key", "pos_group", "season_start"], suffixes=("", "_tgt"),
    )
    cols = ["player_key", "pos_group", "league", "target_season", "value_t", "target", *NUMERIC_FEATURES]
    out = merged[cols].dropna(subset=[*NUMERIC_FEATURES, "value_t", "target"]).reset_index(drop=True)
    return out


def rolling_origin_split(pairs: pd.DataFrame, origin: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(train, test) for one rolling origin `origin` (a target-season label):
    train = pairs whose target season is strictly before `origin`, test =
    pairs whose target season equals `origin`. Season labels ("2021-2022",
    ...) sort lexicographically in chronological order, so plain string
    comparison is correct here (see `src.utils.season_label`).
    """
    train = pairs[pairs["target_season"] < origin].reset_index(drop=True)
    test = pairs[pairs["target_season"] == origin].reset_index(drop=True)
    return train, test


# =============================================================================
# Metrics
# =============================================================================


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((np.asarray(y_true) - np.asarray(y_pred)) ** 2)))


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(np.asarray(y_true) - np.asarray(y_pred))))


# =============================================================================
# Baselines 0 and 1
# =============================================================================


def predict_persistence(test: pd.DataFrame) -> pd.Series:
    """Baseline 0: next season's value = this season's own composite value."""
    return test["value_t"]


def predict_shrinkage_to_league_mean(train: pd.DataFrame, test: pd.DataFrame, k: int = 10) -> pd.Series:
    """Baseline 1: an empirical-Bayes shrinkage of the league's historical
    mean *target* (from `train`) toward the overall training mean, weight
    n_league / (n_league + k) -- the same K-phantom-observations logic as
    `src.features.bayesian_shrink`. A league absent from `train` falls back
    to the overall training mean (weight 0).

    Cold start (`train` empty, origin 1 only): there is no historical target
    to shrink toward yet, so the prediction falls back to the *test*
    season's own `value_t` mean -- a known, current-season quantity, not the
    (unknown, to-be-predicted) target, so this is not leakage.
    """
    if train.empty:
        return pd.Series(test["value_t"].mean(), index=test.index)

    league_mean = train.groupby("league")["target"].mean()
    n_league = train.groupby("league").size()
    global_mean = float(train["target"].mean())

    def _pred(league: str) -> float:
        n = int(n_league.get(league, 0))
        mu_l = float(league_mean.get(league, global_mean))
        weight = n / (n + k)
        return weight * mu_l + (1 - weight) * global_mean

    return test["league"].map(_pred)


# =============================================================================
# Model 2: hierarchical Bayesian regression
# =============================================================================

Z = 1.6448536269514722  # standard-normal 95th percentile -> a symmetric 90% interval


def fit_bayesian(
    train: pd.DataFrame, *, feature_cols: list[str] | None = None, draws: int = 800, tune: int = 800,
    chains: int = 2, target_accept: float = 0.9, seed: int | None = None, progressbar: bool = False,
    cores: int | None = None,
) -> tuple[pm.backends.base.MultiTrace | Any, dict[str, Any]]:
    """Fit target ~ Normal(mu, sigma), mu = alpha + beta.x (standardised
    numeric features, `feature_cols`, default `NUMERIC_FEATURES`; `main`
    passes `NUMERIC_FEATURES + ["m_l"]` -- the M2 league-strength offset,
    see `attach_m_l`) + gamma_league (partial pooling, non-centred) +
    delta_pos + u_player (partial pooling, non-centred, sigma_u ~
    HalfNormal(0.5)) on `train`.

    Returns `(idata, meta)`; `meta` carries everything `predict_bayesian`
    needs to score a *different* dataframe against this fit: `feature_cols`
    itself, the feature means/stds used to standardise (so test rows are
    standardised the same way, not refit), and the `league`/`pos`/`player`
    categories seen during training (so an unseen category at prediction
    time is detected rather than silently mis-indexed).
    """
    seed = config.RANDOM_SEED if seed is None else seed
    feature_cols = feature_cols or NUMERIC_FEATURES
    x_mean = train[feature_cols].mean()
    x_std = train[feature_cols].std().replace(0, 1.0)
    x = ((train[feature_cols] - x_mean) / x_std).to_numpy()

    league_cat = pd.Categorical(train["league"])
    pos_cat = pd.Categorical(train["pos_group"], categories=POS_GROUPS)
    player_cat = pd.Categorical(train["player_key"])
    y = train["target"].to_numpy()

    coords = {
        "feature": feature_cols, "league": list(league_cat.categories),
        "pos": list(pos_cat.categories), "player": list(player_cat.categories),
    }
    with pm.Model(coords=coords):
        alpha = pm.Normal("alpha", 0.0, 1.0)
        beta = pm.Normal("beta", 0.0, 1.0, dims="feature")

        sigma_league = pm.HalfNormal("sigma_league", 0.5)
        z_league = pm.Normal("z_league", 0.0, 1.0, dims="league")
        gamma_league = pm.Deterministic("gamma_league", z_league * sigma_league, dims="league")

        delta_pos = pm.Normal("delta_pos", 0.0, 0.5, dims="pos")

        sigma_player = pm.HalfNormal("sigma_player", 0.5)
        z_player = pm.Normal("z_player", 0.0, 1.0, dims="player")
        u_player = pm.Deterministic("u_player", z_player * sigma_player, dims="player")

        sigma = pm.HalfNormal("sigma", 0.5)

        mu = (alpha + pm.math.dot(x, beta) + gamma_league[league_cat.codes]
              + delta_pos[pos_cat.codes] + u_player[player_cat.codes])
        pm.Normal("y", mu=mu, sigma=sigma, observed=y)

        idata = pm.sample(draws=draws, tune=tune, chains=chains, target_accept=target_accept,
                          random_seed=seed, progressbar=progressbar, cores=cores or min(chains, 4))

    meta = {"feature_cols": feature_cols, "x_mean": x_mean, "x_std": x_std,
            "leagues": set(league_cat.categories), "players": set(player_cat.categories)}
    return idata, meta


def predict_bayesian(idata: Any, test: pd.DataFrame, meta: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Point prediction and a 90% interval per row of `test`.

    Point = posterior median of `mu` (fixed effects + the player's own
    `u_player` draw when the player was seen during training, else 0 -- the
    population average, since an unseen player's own offset is unknown).

    The 90% interval is a *normal approximation* to the posterior
    predictive, not full Monte Carlo sampling of `y_rep`: per row,
    `median(mu) +/- Z * sqrt(var(mu across draws) + sigma_resid_median^2 +
    [sigma_player_median^2 if the player is unseen])`. This is cheaper than
    drawing and summarising a full (draws x rows) `y_rep` array per origin
    (five origins, each needing its own predictive pass) and is standard
    practice for a within-runtime-budget report exhibit; it slightly
    understates tail coverage relative to exact sampling but is unbiased in
    the interval's centre and width to first order. Documented here, not
    hidden, per the "no overclaiming" brief.
    """
    feature_cols = meta["feature_cols"]
    x = ((test[feature_cols] - meta["x_mean"]) / meta["x_std"]).to_numpy()
    post = idata.posterior
    alpha = post["alpha"].values.reshape(-1)               # (draws,)
    beta = post["beta"].values.reshape(-1, len(feature_cols))  # (draws, k)
    n_draws = alpha.shape[0]

    fixed = alpha[None, :] + (x @ beta.T)                    # (n_test, draws)

    league_da = post["gamma_league"]
    pos_da = post["delta_pos"]
    league_vals = {str(lg): league_da.sel(league=lg).values.reshape(-1) for lg in league_da.coords["league"].values}
    pos_vals = {str(p): pos_da.sel(pos=p).values.reshape(-1) for p in pos_da.coords["pos"].values}
    u_da = post["u_player"]
    player_vals = {str(pl): u_da.sel(player=pl).values.reshape(-1) for pl in u_da.coords["player"].values}

    zeros = np.zeros(n_draws)
    n_test = len(test)
    mu = np.empty((n_test, n_draws))
    unseen_player = np.zeros(n_test, dtype=bool)
    for i, r in enumerate(test.itertuples()):
        gl = league_vals.get(str(r.league), zeros)
        ps = pos_vals.get(str(r.pos_group), zeros)
        up = player_vals.get(str(r.player_key))
        if up is None:
            up = zeros
            unseen_player[i] = True
        mu[i, :] = fixed[i, :] + gl + ps + up

    sigma_draws = post["sigma"].values.reshape(-1)
    sigma_resid = float(np.median(sigma_draws))
    sigma_player_draws = post["sigma_player"].values.reshape(-1)
    sigma_player_med = float(np.median(sigma_player_draws))

    point = np.median(mu, axis=1)
    epistemic_var = np.var(mu, axis=1)
    total_var = epistemic_var + sigma_resid ** 2 + np.where(unseen_player, sigma_player_med ** 2, 0.0)
    half_width = Z * np.sqrt(total_var)
    return point, point - half_width, point + half_width


# =============================================================================
# Models 3 and 4: gradient boosting and a small MLP
# =============================================================================


def _cast_categoricals(df: pd.DataFrame, categories: dict[str, list[str]]) -> pd.DataFrame:
    """`league`/`pos_group` as pandas `category` dtype with a *fixed*
    category set (the corpus-wide list of leagues/pos groups, not just
    those seen in one origin's train split) -- this is declaring the
    category space, not using target information, and it is what lets
    HistGradientBoostingRegressor's `categorical_features="from_dtype"`
    and the one-hot encoder handle a league/pos level that a later origin's
    smaller training set happened not to include.
    """
    out = df.copy()
    for col, cats in categories.items():
        out[col] = pd.Categorical(out[col], categories=cats)
    return out


def fit_predict_gbm(train: pd.DataFrame, test: pd.DataFrame, categories: dict[str, list[str]],
                    seed: int | None = None) -> np.ndarray:
    """`HistGradientBoostingRegressor`, default-ish params, early stopping;
    `league`/`pos_group` as `category` dtype (Pedregosa et al., 2011)."""
    from sklearn.ensemble import HistGradientBoostingRegressor

    cols = [*NUMERIC_FEATURES, "league", "pos_group"]
    x_train = _cast_categoricals(train[cols], categories)
    x_test = _cast_categoricals(test[cols], categories)
    model = HistGradientBoostingRegressor(early_stopping=True, random_state=config.RANDOM_SEED if seed is None else seed)
    model.fit(x_train, train["target"])
    return model.predict(x_test)


def fit_predict_mlp(train: pd.DataFrame, test: pd.DataFrame, categories: dict[str, list[str]],
                    seed: int | None = None) -> np.ndarray:
    """A small multilayer perceptron (`MLPRegressor`, not an "embedding
    model" -- PyTorch is not installed, so a learned league embedding isn't
    available in sklearn): one-hot `league`/`pos_group` + standardised
    numeric features, hidden layers (64, 32), early stopping."""
    from sklearn.compose import ColumnTransformer
    from sklearn.neural_network import MLPRegressor
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    pre = ColumnTransformer([
        ("num", StandardScaler(), NUMERIC_FEATURES),
        ("cat", OneHotEncoder(categories=[categories["league"], categories["pos_group"]], handle_unknown="ignore"),
         ["league", "pos_group"]),
    ])
    pipe = Pipeline([
        ("pre", pre),
        ("mlp", MLPRegressor(hidden_layer_sizes=(64, 32), early_stopping=True,
                             random_state=config.RANDOM_SEED if seed is None else seed, max_iter=500)),
    ])
    pipe.fit(train[[*NUMERIC_FEATURES, "league", "pos_group"]], train["target"])
    return pipe.predict(test[[*NUMERIC_FEATURES, "league", "pos_group"]])


# =============================================================================
# Assembly
# =============================================================================


def assemble_output(target: str, origins: list[str], rows: list[dict[str, Any]],
                    pooled: list[dict[str, Any]], winner_pooled: str, notes: list[str]) -> dict[str, Any]:
    """Pure assembly of the JSON shape described in the module docstring;
    no fitting here, so this is testable on hand-built inputs."""
    return {"target": target, "origins": origins, "rows": rows, "pooled": pooled,
            "winner_pooled": winner_pooled, "notes": notes}


# =============================================================================
# Figure
# =============================================================================

MODEL_ORDER = ["persistence", "shrinkage_league_mean", "bayesian", "gbm", "mlp"]
MODEL_LABELS = {
    "persistence": "Persistence", "shrinkage_league_mean": "Shrinkage to league mean",
    "bayesian": "Hierarchical Bayesian", "gbm": "Gradient boosting", "mlp": "Small MLP",
}


def render_figure(rows: list[dict[str, Any]], out_path: Path) -> None:
    """RMSE per origin season, one line per model (palette), persistence dashed."""
    import matplotlib.pyplot as plt

    from src.international_benchmark import CREAM, INK, MUTED, NAVY, NAVY_DEEP, OXBLOOD, RULE
    from src.utils import season_label

    colors = {"persistence": RULE, "shrinkage_league_mean": MUTED, "bayesian": NAVY,
             "gbm": OXBLOOD, "mlp": NAVY_DEEP}
    df = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(8.0, 4.6))
    fig.patch.set_facecolor(CREAM)
    ax.set_facecolor(CREAM)

    for model in MODEL_ORDER:
        sub = df[df["model"] == model].sort_values("origin")
        if sub.empty:
            continue
        xs = [season_label(o) for o in sub["origin"]]
        ax.plot(xs, sub["rmse"], color=colors[model], lw=2.2,
               linestyle="--" if model == "persistence" else "-",
               marker="o", markersize=4, label=MODEL_LABELS[model])

    ax.set_ylabel("RMSE (npG+A per 90, quality-adjusted)", fontsize=10, fontfamily="sans-serif", color=INK)
    ax.set_xlabel("Target season (origin)", fontsize=10, fontfamily="sans-serif", color=INK)
    ax.set_title("Model comparison: RMSE by origin season", fontsize=13, fontfamily="serif", color=INK, loc="left")
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
# Assembly / main
# =============================================================================


def attach_m_l(pairs: pd.DataFrame, league_strength: dict[str, Any]) -> pd.DataFrame:
    """Add `m_l`: season t's league's M2 league-strength multiplier (the
    posterior median from `league_strength.json`, Task 15), mapped by
    `league`. A league absent from `league_strength.json` (shouldn't happen
    -- both stages read the same `features_*.parquet` corpus) falls back to
    1.0 (Premier-League-equivalent, the model's own reference point)."""
    m_l = {r["league"]: r["median"] for r in league_strength.get("leagues", [])}
    out = pairs.copy()
    out["m_l"] = out["league"].map(m_l).fillna(1.0)
    return out


# The Bayesian fit's runtime budget: 2 chains x `BAYES_DRAWS` draws per
# origin, and each origin's *training* rows subsampled to at most
# `BAYES_MAX_TRAIN` (seeded) before fitting -- GBM/MLP fit the full training
# set (they are fast); the Bayesian model's player-level random effect does
# not, so it is the one that needs a runtime lever. Reported in `main`'s log
# and the JSON's `notes` (the brief's "reduce draws or subsample players if
# needed and say so").
BAYES_DRAWS = 400
BAYES_TUNE = 400
BAYES_CHAINS = 2
BAYES_MAX_TRAIN = 2500


def _subsample(df: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    if len(df) <= n:
        return df
    return df.sample(n=n, random_state=seed).reset_index(drop=True)


def main() -> None:
    logging_setup()
    config.ensure_dirs()
    t_start = time.time()

    features_by_group = {g: read_parquet(config.PROCESSED_DIR / f"features_{g}.parquet") for g in GROUPS}
    pairs = build_pairs(features_by_group)
    LOG.info("pairs corpus: %d rows, %d players, %d target seasons", len(pairs),
             pairs["player_key"].nunique(), pairs["target_season"].nunique())

    league_strength = json.loads((config.PROCESSED_DIR / "league_strength.json").read_text(encoding="utf-8")) \
        if (config.PROCESSED_DIR / "league_strength.json").exists() else {}
    pairs = attach_m_l(pairs, league_strength)
    categories = {"league": sorted(pairs["league"].unique()), "pos_group": POS_GROUPS}
    bayes_features = [*NUMERIC_FEATURES, "m_l"]

    rows: list[dict[str, Any]] = []
    notes = [
        f"Bayesian model: {BAYES_CHAINS} chains x {BAYES_DRAWS} draws per origin (reduced from a "
        f"league_strength.py-style 800+ to keep 5 origins' worth of fits under the runtime budget); "
        f"training rows subsampled to at most {BAYES_MAX_TRAIN} (seeded, config.RANDOM_SEED) when an "
        f"origin's training set is larger.",
        "Origin 2021-2022's training set is empty by construction (the corpus's earliest feature season, "
        "2020-2021, makes 2021-2022 the first possible target season) -- only the two baselines are "
        "reported for that origin.",
        "The M2 league-strength multiplier m_L (Task 15, league_strength.json) is used as an extra "
        "feature for the Bayesian model only, alongside the config-based league_multiplier already in "
        "every model's feature set.",
    ]

    for origin in ORIGINS:
        train, test = rolling_origin_split(pairs, origin)
        LOG.info("origin %s: %d train, %d test", origin, len(train), len(test))

        pred = predict_persistence(test)
        rows.append({"model": "persistence", "origin": origin, "n_test": len(test),
                     "rmse": rmse(test["target"], pred), "mae": mae(test["target"], pred), "coverage90": None})

        pred = predict_shrinkage_to_league_mean(train, test)
        rows.append({"model": "shrinkage_league_mean", "origin": origin, "n_test": len(test),
                     "rmse": rmse(test["target"], pred), "mae": mae(test["target"], pred), "coverage90": None})

        if train.empty:
            LOG.info("origin %s: empty training set, skipping the three learned models", origin)
            continue

        bayes_train = _subsample(train, BAYES_MAX_TRAIN, config.RANDOM_SEED)
        t0 = time.time()
        idata, meta = fit_bayesian(bayes_train, feature_cols=bayes_features, draws=BAYES_DRAWS, tune=BAYES_TUNE,
                                   chains=BAYES_CHAINS, seed=config.RANDOM_SEED)
        point, lo, hi = predict_bayesian(idata, test, meta)
        LOG.info("origin %s: bayesian fit %.1f s (%d train rows)", origin, time.time() - t0, len(bayes_train))
        coverage = float(((test["target"].to_numpy() >= lo) & (test["target"].to_numpy() <= hi)).mean())
        rows.append({"model": "bayesian", "origin": origin, "n_test": len(test),
                     "rmse": rmse(test["target"], point), "mae": mae(test["target"], point), "coverage90": coverage})

        pred = fit_predict_gbm(train, test, categories, seed=config.RANDOM_SEED)
        rows.append({"model": "gbm", "origin": origin, "n_test": len(test),
                     "rmse": rmse(test["target"], pred), "mae": mae(test["target"], pred), "coverage90": None})

        pred = fit_predict_mlp(train, test, categories, seed=config.RANDOM_SEED)
        rows.append({"model": "mlp", "origin": origin, "n_test": len(test),
                     "rmse": rmse(test["target"], pred), "mae": mae(test["target"], pred), "coverage90": None})

    pooled = []
    for model in MODEL_ORDER:
        model_rows = [r for r in rows if r["model"] == model]
        if not model_rows:
            continue
        n_test = sum(r["n_test"] for r in model_rows)
        w_rmse = float(np.sqrt(sum(r["rmse"] ** 2 * r["n_test"] for r in model_rows) / n_test))
        w_mae = float(sum(r["mae"] * r["n_test"] for r in model_rows) / n_test)
        cov_rows = [r for r in model_rows if r["coverage90"] is not None]
        cov = float(sum(r["coverage90"] * r["n_test"] for r in cov_rows) / sum(r["n_test"] for r in cov_rows)) \
            if cov_rows else None
        pooled.append({"model": model, "n_test": n_test, "rmse": round(w_rmse, 4), "mae": round(w_mae, 4),
                       "coverage90": round(cov, 4) if cov is not None else None})

    winner = min(pooled, key=lambda r: r["rmse"])["model"]
    gbm_row = next((r for r in pooled if r["model"] == "gbm"), None)
    mlp_row = next((r for r in pooled if r["model"] == "mlp"), None)
    if gbm_row and mlp_row and mlp_row["rmse"] >= gbm_row["rmse"]:
        notes.append(f"The MLP does not beat gradient boosting on pooled RMSE "
                     f"({mlp_row['rmse']} vs {gbm_row['rmse']}).")

    winner_rows = sorted((r for r in rows if r["model"] == winner), key=lambda r: r["origin"])
    if len(winner_rows) >= 2:
        drift = max(abs(a["rmse"] - b["rmse"]) for a, b in zip(winner_rows, winner_rows[1:], strict=False))
        notes.append(f"Largest season-to-season RMSE change for the winner ({winner}): {round(drift, 4)}.")

    for r in rows:
        r["rmse"] = round(r["rmse"], 4)
        r["mae"] = round(r["mae"], 4)
        if r["coverage90"] is not None:
            r["coverage90"] = round(r["coverage90"], 4)

    result = assemble_output(target=TARGET_LABEL, origins=ORIGINS, rows=rows, pooled=pooled,
                             winner_pooled=winner, notes=notes)

    out_json = config.PROCESSED_DIR / "model_comparison.json"
    out_json.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    LOG.info("wrote %s", out_json)

    render_figure(rows, config.OUTPUTS_DIR / "model_comparison.svg")

    LOG.info("pooled: %s", pooled)
    LOG.info("winner: %s", winner)
    LOG.info("done: %s, %.1f s total", config.NATION, time.time() - t_start)


if __name__ == "__main__":
    main()
