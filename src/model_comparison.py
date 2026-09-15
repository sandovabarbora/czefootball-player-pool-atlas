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
