"""Per-90 features, Bayesian shrinkage and league-quality projection per position group.

Reads:  data/processed/fbref_players.parquet, pool.parquet, nt_flags.parquet
Writes: data/processed/features_FW.parquet, features_MF.parquet, features_DF.parquet

Rates are per 90 minutes; shrinkage uses K = 900 phantom minutes:
    shrunk = (count + K/90 * cohort_median_p90) / (minutes/90 + K/90)

The shrinkage cohort is (league, season) -- not league alone -- because
fbref_players.parquet spans multiple seasons per league and per-season
scoring levels differ (e.g. a league's median npg_p90 in 2023-2024 is not a
good prior for 2024-2025). Every season present in fbref_players.parquet is
processed here; season selection for a particular analysis (metrics season,
trajectory, analog corpus) happens downstream.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from src import config
from src.utils import normalize_name, read_parquet, write_parquet

LOG = logging.getLogger(__name__)
FEATURES = ["npg_p90", "ast_p90", "min_share", "age", "cards_p90"]
RATE_FEATURES = {"npg_p90": "npg", "ast_p90": "ast", "cards_p90": "cards"}


def per90(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["npg"] = out["gls"] - out["pk"]
    out["cards"] = out["crdy"] + 2 * out["crdr"]
    n90 = out["min"] / 90.0
    for feat, cnt in RATE_FEATURES.items():
        out[feat] = np.where(n90 > 0, out[cnt] / n90, np.nan)
    out["min_share"] = out["min"] / (out["team_matches"] * 90.0)
    return out


def bayesian_shrink(df: pd.DataFrame, k_minutes: int = 900) -> pd.DataFrame:
    """Shrink each rate feature toward its (league, season) cohort median.

    Groups by ["league", "season"] when a `season` column is present, else
    by ["league"] alone (e.g. the brief's single-season toy fixtures).
    """
    out = df.copy()
    k90 = k_minutes / 90.0
    group_cols = ["league", "season"] if "season" in out.columns else ["league"]
    for feat, cnt in RATE_FEATURES.items():
        out[f"{feat}_shrunk"] = np.nan
        for _, sub in out.groupby(group_cols):
            well = sub[sub["min"] >= k_minutes]
            med = float(well[feat].median()) if len(well) else float(sub[feat].median())
            out.loc[sub.index, f"{feat}_shrunk"] = (sub[cnt] + k90 * med) / (sub["min"] / 90.0 + k90)
    out["min_share_shrunk"] = out["min_share"]
    if "age" in out.columns:
        out["age_shrunk"] = out["age"]
    return out


def add_quality(df: pd.DataFrame) -> pd.DataFrame:
    mult = config.league_quality()["multipliers"]
    out = df.copy()
    out["league_multiplier"] = out["league"].map(mult).astype(float)
    for feat in ("npg_p90", "ast_p90"):
        out[f"{feat}_quality"] = out[f"{feat}_shrunk"] * out["league_multiplier"]
    for feat in ("min_share", "age", "cards_p90"):  # not production: unscaled
        if f"{feat}_shrunk" in out.columns:
            out[f"{feat}_quality"] = out[f"{feat}_shrunk"]
    return out


def zscore(df: pd.DataFrame, cols) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        x = out[c].astype(float)
        sd = x.std()
        out[f"{c}_z"] = 0.0 if not np.isfinite(sd) or sd == 0 else (x - x.mean()) / sd
    return out


def _team_matches(tables: pd.DataFrame) -> pd.DataFrame:
    tm = tables.groupby(["league", "season", "team"])["mp"].max().rename("team_matches").reset_index()
    return tables.merge(tm, on=["league", "season", "team"], how="left")


def _fill_missing_age(df: pd.DataFrame) -> pd.DataFrame:
    """Fill missing `age` with `int(season[:4]) + 1 - born` (FBref snapshot age).

    Stays NaN when `born` is also missing (nothing to derive from).
    """
    out = df.copy()
    missing = out["age"].isna()
    if missing.any():
        season_start = out.loc[missing, "season"].str.slice(0, 4).astype(int)
        out.loc[missing, "age"] = season_start + 1 - out.loc[missing, "born"]
    return out


def _attach_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Attach czech_eligible / nt_flag / nt_events.

    Join key for pool membership is `player_key` (normalized name + birth
    year), not `fbref_id` -- FBref player-season tables carry no id, and
    `player_key` is the canonical cross-source key (see src/utils.py).

    National-team flag matches `normalize_name(player)` against
    `nt_flags.player_norm`, additionally requiring `born` to match when the
    matched nt_flags row carries a `born` value -- this guards against
    namesakes (two different people who normalize to the same name).
    """
    pool = read_parquet(config.PROCESSED_DIR / "pool.parquet")
    nt = read_parquet(config.PROCESSED_DIR / "nt_flags.parquet")
    out = df.copy()
    out["czech_eligible"] = out["nation"].eq("CZE") | out["player_key"].isin(pool.player_key)
    out["player_norm"] = out["player"].map(normalize_name)

    candidates = (
        out[["player_norm", "born"]]
        .reset_index()
        .merge(nt[["player_norm", "born", "event"]], on="player_norm", how="inner", suffixes=("", "_nt"))
    )
    born_ok = candidates["born_nt"].isna() | (candidates["born_nt"] == candidates["born"])
    matched = candidates[born_ok]
    events = matched.groupby("index")["event"].agg(lambda s: " · ".join(sorted(set(s))))

    out["nt_events"] = out.index.map(events).fillna("")
    out["nt_flag"] = out["nt_events"].ne("")
    return out.drop(columns=["player_norm"])


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    cfg = config.features()
    tables = read_parquet(config.PROCESSED_DIR / "fbref_players.parquet")
    tables = _fill_missing_age(tables)
    tables = _team_matches(tables)
    tables["pos_group"] = tables["pos"].where(tables["pos"].isin(cfg["groups"]))
    tables = tables.dropna(subset=["pos_group"])
    tables = tables[tables["min"] >= cfg["min_minutes"]]
    for group in cfg["groups"]:
        sub = tables[tables.pos_group == group]
        sub = zscore(
            add_quality(bayesian_shrink(per90(sub), cfg["phantom_minutes"])),
            [f"{f}_shrunk" for f in FEATURES] + [f"{f}_quality" for f in FEATURES],
        )
        sub = _attach_flags(sub)
        write_parquet(sub, config.PROCESSED_DIR / f"features_{group}.parquet")
        LOG.info(
            "%s: %d player-seasons, %d Czech, %d NT-flagged",
            group,
            len(sub),
            int(sub.czech_eligible.sum()),
            int(sub.nt_flag.sum()),
        )


if __name__ == "__main__":
    main()
