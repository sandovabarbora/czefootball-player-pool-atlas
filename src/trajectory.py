"""Season-over-season trajectory for the player pool.

A player qualifies for trajectory analysis when they played >= 900 minutes
in BOTH the previous season (`config.seasons()["previous"]`) and the
metrics season (`config.seasons()["metrics"]`), joined on `player_key`.
Below that threshold, two data points cannot distinguish a trend from
noise. Each season frame is first collapsed to one row per
(player_key, season, pos_group) with `src.utils.collapse_player_seasons`
(minutes summed, rates minutes-weighted), so a mid-season transfer neither
fails the gate on a split season nor yields two trajectory rows.

Metric: `npg_p90_quality + ast_p90_quality` (league-quality-adjusted
non-penalty-goal + assist rate). `delta` = metrics-season value minus
previous-season value. `direction` is `improving` when delta > +0.05,
`declining` when delta < -0.05, else `stable`.

Inputs:
  data/processed/features_{FW,MF,DF}.parquet

Output:
  data/processed/trajectory_{FW,MF,DF}.parquet
      player_key, player, league (metrics season), nation, home_eligible,
      nt_flag, min_prev, min_curr, npg_ast_quality_prev,
      npg_ast_quality_curr, delta, direction
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from src import config
from src.logging_setup import setup as logging_setup
from src.utils import collapse_player_seasons, read_parquet, write_parquet

LOG = logging.getLogger(__name__)

MIN_MINUTES = 900
DIRECTION_THRESHOLD = 0.05
RATE_COLS: list[str] = ["npg_p90_quality", "ast_p90_quality"]

OUTPUT_COLS: list[str] = [
    "player_key", "player", "league", "nation", "home_eligible", "nt_flag",
    "min_prev", "min_curr", "npg_ast_quality_prev", "npg_ast_quality_curr",
    "delta", "direction",
]


def compute_trajectory(features: pd.DataFrame, group: str) -> pd.DataFrame:
    """Build trajectory rows for one position group's player pool."""
    seasons = config.seasons()
    prev_season, metrics_season = seasons["previous"], seasons["metrics"]

    f_prev = features[features["season"] == prev_season].copy()
    f_metrics = features[features["season"] == metrics_season].copy()
    LOG.info("%s: trajectory %s -> %s (%d rows prev, %d rows metrics)",
              group, prev_season, metrics_season, len(f_prev), len(f_metrics))

    # A mid-season transfer gives one player two rows per season (one per
    # club). Collapse them first so the minutes gate sees the season total
    # (500 + 500 passes; it wouldn't as two rows) and so the player_key join
    # below cannot fan out into duplicate trajectory rows.
    f_prev = collapse_player_seasons(f_prev, rate_cols=RATE_COLS)
    f_metrics = collapse_player_seasons(f_metrics, rate_cols=RATE_COLS)

    f_prev = f_prev[f_prev["min"] >= MIN_MINUTES].copy()
    f_metrics = f_metrics[f_metrics["min"] >= MIN_MINUTES].copy()

    for f in (f_prev, f_metrics):
        f["npg_ast_quality"] = f["npg_p90_quality"] + f["ast_p90_quality"]

    prev_keep = f_prev[["player_key", "min", "npg_ast_quality"]].rename(
        columns={"min": "min_prev", "npg_ast_quality": "npg_ast_quality_prev"}
    )
    metrics_keep = f_metrics[
        ["player_key", "player", "league", "nation", "home_eligible", "nt_flag",
         "min", "npg_ast_quality"]
    ].rename(columns={"min": "min_curr", "npg_ast_quality": "npg_ast_quality_curr"})

    joined = prev_keep.merge(metrics_keep, on="player_key", how="inner")
    LOG.info("%s: %d players with >=%d min in both seasons", group, len(joined), MIN_MINUTES)

    if joined.empty:
        return pd.DataFrame(columns=OUTPUT_COLS)

    joined["delta"] = joined["npg_ast_quality_curr"] - joined["npg_ast_quality_prev"]
    joined["direction"] = np.where(
        joined["delta"] > DIRECTION_THRESHOLD, "improving",
        np.where(joined["delta"] < -DIRECTION_THRESHOLD, "declining", "stable"),
    )
    return joined[OUTPUT_COLS]


def main() -> None:
    logging_setup()
    config.ensure_dirs()

    for group in config.features()["groups"]:
        features_df = read_parquet(config.PROCESSED_DIR / f"features_{group}.parquet")
        traj = compute_trajectory(features_df, group)
        write_parquet(traj, config.PROCESSED_DIR / f"trajectory_{group}.parquet")

        LOG.info("=== %s trajectory summary ===", group)
        LOG.info("rows: %d, home_eligible: %d", len(traj), int(traj["home_eligible"].sum()) if len(traj) else 0)
        if traj.empty:
            continue
        LOG.info("by direction: %s", traj["direction"].value_counts().to_dict())


if __name__ == "__main__":
    main()
