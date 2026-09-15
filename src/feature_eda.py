"""Task 17: "From raw tables to a feature vector" — wrangling, EDA and
feature engineering shown, not claimed (spec §4c).

Reads:  data/processed/<nation>/fbref_players.parquet, features_{FW,MF,DF}.parquet
Writes: data/processed/<nation>/feature_eda.json,
        outputs/<nation>/eda_distributions.svg, outputs/<nation>/eda_shrinkage.svg

Four things, one worked example:

1. One raw row: the home nation's player with the most metrics-season
   minutes, shown as its raw FBref columns (`pick_raw_and_feature_row`) next
   to the same player's feature row after per-90 -> Bayesian shrinkage ->
   league-quality projection -> z-score (`feature_row_dict`). The raw-row
   search is restricted to players who actually made it into the feature
   pipeline (min >= `feature_definitions.yaml::min_minutes`, a FW/MF/DF
   position), so a pairing always exists.

2. The cleaning ledger is not recomputed here — `data_quality.json` already
   carries it, and `render.py` links `#features-from-raw` to `#data-quality`
   rather than duplicating the counts.

3. Five kept features, five rejected candidates, corpus-wide (every fetched
   nationality) on the metrics-season feature-pipeline output — the same
   population every other chapter-IV number in this report describes:
     - `gls_p90` vs `npg_p90`: penalties inflate a few takers
       (`penalty_share_stat`) -> replaced by npg_p90.
     - `mp` (appearances) vs `min`: a start can be a substitute cameo
       (`starts_proxy_stat`) -> replaced by minutes share.
     - `crdr_p90` (red cards): most player-seasons have none
       (`red_card_zero_share_stat`) -> folded into cards (yellow + 2*red).
     - `age`: median production visibly differs by age band
       (`age_production_curve_stat`) -> kept as a feature.
     - `born` (raw column): occasionally missing corpus-wide
       (`missingness_stat`) -> kept anyway, since `player_key` (the
       cross-source join key, see `src.utils.player_key`) needs it.

4. Two EDA figures: `render_distributions_figure` (the five raw per-90
   features' distributions per league, the picture that motivates league
   adjustment) and `render_shrinkage_figure` (raw vs shrunk npG/90 against
   minutes, the picture that motivates shrinkage).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import skew

from src import config
from src.features import FEATURES
from src.international_benchmark import CREAM, INK, MUTED, NAVY, NAVY_DEEP, OXBLOOD, RULE
from src.logging_setup import setup as logging_setup
from src.utils import read_parquet

LOG = logging.getLogger(__name__)

GROUPS = ["FW", "MF", "DF"]
RAW_COLUMNS = ["league", "season", "team", "player", "nation", "pos", "born", "age",
               "mp", "min", "gls", "ast", "pk", "crdy", "crdr"]
_INT_RAW_COLUMNS = {"born", "age", "mp", "min", "gls", "ast", "pk", "crdy", "crdr"}
AGE_BAND_ORDER = ["U22", "23-25", "26-29", "30+"]

plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["Spectral", "Cambria", "Georgia", "Times New Roman", "DejaVu Serif"]
plt.rcParams["font.sans-serif"] = ["Bricolage Grotesque", "Helvetica Neue", "Arial", "DejaVu Sans"]
plt.rcParams["text.color"] = INK


# =============================================================================
# 1. The raw row and the feature row
# =============================================================================


def pick_raw_and_feature_row(
    tables: pd.DataFrame, features_by_group: dict[str, pd.DataFrame], metrics_season: str,
) -> tuple[pd.Series, pd.Series]:
    """The home nation's raw row with the most metrics-season minutes among
    players who also made it into the feature pipeline, plus that player's
    own feature row.

    Restricting to players present in some `features_{group}` frame (not
    every home-nation row in `fbref_players.parquet`) guarantees the second
    half of the pairing exists -- a raw row below the inclusion floor, at a
    goalkeeper position, or in a league without season tables would
    otherwise have no feature row to show next to it.
    """
    feat_all = pd.concat(features_by_group.values(), ignore_index=True) if features_by_group else pd.DataFrame()
    feat_metrics = feat_all[feat_all["season"] == metrics_season] if not feat_all.empty else feat_all
    eligible_keys = set(feat_metrics["player_key"]) if not feat_metrics.empty else set()

    home_rows = tables[
        (tables["nation"] == config.HOME) & (tables["season"] == metrics_season)
        & tables["player_key"].isin(eligible_keys)
    ]
    if home_rows.empty:
        raise ValueError(f"no {config.HOME} player with both a raw row and a feature row in {metrics_season}")
    raw = home_rows.sort_values("min", ascending=False).iloc[0]

    same_player = feat_metrics[feat_metrics["player_key"] == raw["player_key"]]
    same_team = same_player[same_player["team"] == raw["team"]]
    feat = (same_team if not same_team.empty else same_player).iloc[0]
    return raw, feat


def raw_row_dict(row: pd.Series) -> dict[str, Any]:
    """`row` (a `fbref_players.parquet` row) -> a plain dict over
    `RAW_COLUMNS`, in FBref's own column order, ints where FBref's own dtype
    is integer-like and `None` for a missing value (age/born can be NA)."""
    out: dict[str, Any] = {}
    for col in RAW_COLUMNS:
        v = row[col]
        if pd.isna(v):
            out[col] = None
        elif col in _INT_RAW_COLUMNS:
            out[col] = int(v)
        else:
            out[col] = str(v)
    return out


def feature_row_dict(row: pd.Series) -> dict[str, Any]:
    """`row` (a `features_{group}.parquet` row) -> `{player, pos_group,
    <feature>: {raw, shrunk, quality, z}}` for each of `src.features.FEATURES`
    -- the pipeline's four stages for that one player's season."""
    out: dict[str, Any] = {"player": str(row["player"]), "pos_group": str(row["pos_group"])}
    for f in FEATURES:
        stages = {"raw": row[f], "shrunk": row[f"{f}_shrunk"],
                  "quality": row[f"{f}_quality"], "z": row[f"{f}_quality_z"]}
        out[f] = {k: (round(float(v), 4) if pd.notna(v) else None) for k, v in stages.items()}
    return out
