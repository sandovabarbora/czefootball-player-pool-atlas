"""Per-game features for forwards across NHL + Liiga + Extraliga.

Design decision (locked this session):
  - Cross-league projection uses PER-GAME rates (G/GP, A/GP, P/GP, shots/GP,
    PIM/GP). Brief §4.3 explicitly permits "league equivalent for European
    leagues where granularity is coarser" — Liiga and Extraliga only expose
    season totals (no per-game TOI), so per-60 5v5 isn't computable for them.
  - Per-60 5v5 stays as NHL-only ENRICHMENT (written to a separate parquet,
    shown in tooltips + technical section, not in main projection).
  - xG dropped from main projection (locked critique decision).
  - Style + quality projections built side-by-side. Style: z-scored within
    position, no multipliers. Quality: same z-score, but raw rates first
    multiplied by league quality factor.

Bayesian shrinkage:
  Per-game rates are noisy when GP is small (Frolo 1 GP, Kos 4 GP).
  Empirical Bayes shrinks each player's rate toward the (position, league)
  cohort median, with the pull strength controlled by a phantom-games
  parameter K=10. When GP=1, the shrunk rate is ~91% cohort median + 9%
  player. When GP=50, it's ~83% player + 17% prior.

Inputs:
  data/processed/players.parquet  (canonical pool, czech_eligible_flag set)
  data/raw/nhl_skaters_{2024,2025}.parquet
  data/raw/liiga_skaters_{2024,2025}.parquet
  data/raw/extraliga_skaters_{2025}.parquet
  data/raw/moneypuck_skaters_{2024,2025}.parquet  (NHL-only enrichment)

Outputs:
  data/processed/features_forwards.parquet
    One row per (canonical_id, season). Columns: per-game raw rates,
    shrunk rates, league, age, multiplier, z-scored style + quality variants.
  data/processed/features_forwards_nhl_extras.parquet
    NHL+MoneyPuck enrichment (5v5 per-60, xG, on-ice corsi/fenwick).
"""

from __future__ import annotations

import logging
from typing import Iterable

import numpy as np
import pandas as pd

from src import config
from src.logging_setup import setup as logging_setup
from src.utils import read_parquet, write_parquet

LOG = logging.getLogger(__name__)

PHANTOM_GAMES = 10  # Bayesian shrinkage strength
MIN_GP_FOR_INCLUSION = 1  # rows with 0 GP are dropped

PER_GAME_METRICS: tuple[str, ...] = (
    "goals_per_gp",
    "assists_per_gp",
    "points_per_gp",
    "shots_per_gp",
    "pim_per_gp",
)

# Metrics that get multiplied by league quality factor in the quality projection
SCALED_METRICS: tuple[str, ...] = (
    "goals_per_gp",
    "assists_per_gp",
    "points_per_gp",
    "shots_per_gp",
    # PIM intentionally NOT scaled — it's a behavior signal, not production
)


# --- Per-source aggregation -------------------------------------------------


def _agg_nhl(season: int) -> pd.DataFrame:
    """NHL skater stats → (canonical_player_id, season, GP, G, A, P, shots, PIM).

    NHL club-stats has one row per player-team-season; mid-season trades show
    a player on multiple teams. Aggregate to one row per player.
    """
    path = config.RAW_DIR / f"nhl_skaters_{season}.parquet"
    if not path.exists():
        return pd.DataFrame()
    df = read_parquet(path)
    if df.empty:
        return df
    agg = df.groupby("playerId", as_index=False).agg({
        "gamesPlayed": "sum",
        "goals": "sum",
        "assists": "sum",
        "points": "sum",
        "shots": "sum",
        "penaltyMinutes": "sum",
    })
    agg = agg.rename(columns={
        "playerId": "source_player_id",
        "gamesPlayed": "GP",
        "goals": "G",
        "assists": "A",
        "points": "P",
        "shots": "shots",
        "penaltyMinutes": "PIM",
    })
    agg["league"] = "nhl"
    agg["season"] = season
    return agg


def _agg_liiga(season: int) -> pd.DataFrame:
    """Liiga skater stats → unified schema."""
    path = config.RAW_DIR / f"liiga_skaters_{season}.parquet"
    if not path.exists():
        return pd.DataFrame()
    df = read_parquet(path)
    if df.empty:
        return df
    # Liiga parquet already filtered to a single season (per fetch_liiga main()),
    # but some players may have multiple rows if they appear in multiple Liiga
    # seasons in the parquet — defensively aggregate.
    agg = df.groupby("player_id", as_index=False).agg({
        "gp": "sum",
        "goals": "sum",
        "assists": "sum",
        "points": "sum",
        "shots": "sum",
        "pim": "sum",
    })
    agg = agg.rename(columns={
        "player_id": "source_player_id",
        "gp": "GP",
        "goals": "G",
        "assists": "A",
        "points": "P",
        "shots": "shots",
        "pim": "PIM",
    })
    agg["league"] = "liiga"
    agg["season"] = season
    return agg


def _agg_extraliga(season: int) -> pd.DataFrame:
    """Extraliga skater stats → unified schema. Shots are NOT available on
    hokej.cz team /statistiky page; column is NA."""
    path = config.RAW_DIR / f"extraliga_skaters_{season}.parquet"
    if not path.exists():
        return pd.DataFrame()
    df = read_parquet(path)
    if df.empty:
        return df
    agg = df.groupby("player_id", as_index=False).agg({
        "GP": "sum",
        "G": "sum",
        "A": "sum",
        "P": "sum",
        "PIM": "sum",
    })
    agg = agg.rename(columns={"player_id": "source_player_id"})
    # hokej.cz team /statistiky table doesn't expose shots; column is NaN
    # but typed Float64 so concat with other sources keeps consistent dtype.
    agg["shots"] = pd.array([pd.NA] * len(agg), dtype="Float64")
    agg["league"] = "extraliga"
    agg["season"] = season
    return agg


def aggregate_player_seasons(seasons: Iterable[int]) -> pd.DataFrame:
    """Combine per-source stats into one (source_player_id, league, season) frame."""
    frames: list[pd.DataFrame] = []
    for season in seasons:
        for agg_fn in (_agg_nhl, _agg_liiga, _agg_extraliga):
            df = agg_fn(season)
            if not df.empty:
                frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


# --- Canonical join ---------------------------------------------------------


def attach_canonical_ids(stats: pd.DataFrame, canonical: pd.DataFrame) -> pd.DataFrame:
    """Add canonical_id to each per-source stats row.

    Joins on (league, source_player_id) → canonical_id. Drops rows that don't
    map to any canonical player (shouldn't happen if crosswalk is complete).
    """
    # Build (league, source_id) -> canonical_id maps from each ID column
    maps: list[pd.DataFrame] = []
    for league, col in (("nhl", "nhl_id"), ("liiga", "liiga_id"), ("extraliga", "extraliga_id")):
        m = canonical[canonical[col].notna()][["canonical_id", col]].copy()
        m = m.rename(columns={col: "source_player_id"})
        m["league"] = league
        m["source_player_id"] = m["source_player_id"].astype("Int64")
        maps.append(m)
    id_map = pd.concat(maps, ignore_index=True)

    out = stats.merge(id_map, on=["league", "source_player_id"], how="left")
    n_unmapped = out["canonical_id"].isna().sum()
    if n_unmapped:
        LOG.warning("%d stat rows could not be mapped to a canonical_id", n_unmapped)
    return out.dropna(subset=["canonical_id"])


# --- Per-game features + Bayesian shrinkage ---------------------------------


def compute_per_game_rates(df: pd.DataFrame) -> pd.DataFrame:
    """Add G/GP, A/GP, P/GP, shots/GP, PIM/GP columns. Filters out GP<1."""
    df = df[df["GP"].astype(float) >= MIN_GP_FOR_INCLUSION].copy()
    df["GP"] = df["GP"].astype(float)
    for src, tgt in (("G", "goals_per_gp"), ("A", "assists_per_gp"),
                     ("P", "points_per_gp"), ("PIM", "pim_per_gp")):
        df[tgt] = df[src].astype(float) / df["GP"]
    # shots may be NA for Extraliga
    if "shots" in df.columns:
        df["shots_per_gp"] = df["shots"].astype("Float64") / df["GP"]
    else:
        df["shots_per_gp"] = pd.NA
    return df


def bayesian_shrink(df: pd.DataFrame, k: int = PHANTOM_GAMES) -> pd.DataFrame:
    """Shrink each rate toward its (league) cohort median.

        shrunk_rate = (player_count + k * cohort_median) / (player_gp + k)

    The cohort median is computed over the SAME-LEAGUE players with enough GP
    (>= k) to be considered "well-measured". This keeps the prior from being
    biased by the same noisy small-sample players we're trying to correct.
    """
    out = df.copy()
    for metric, raw_count_col in (
        ("goals_per_gp", "G"),
        ("assists_per_gp", "A"),
        ("points_per_gp", "P"),
        ("shots_per_gp", "shots"),
        ("pim_per_gp", "PIM"),
    ):
        shrunk_col = f"{metric}_shrunk"
        out[shrunk_col] = np.nan

        # Per-league cohort medians (computed from well-measured players only)
        for league, sub in out.groupby("league"):
            well_measured = sub[sub["GP"] >= k]
            if metric == "shots_per_gp":
                # shots may be NA for Extraliga — skip cohort calc if so
                if well_measured[metric].notna().sum() == 0:
                    continue
                cohort_median = float(well_measured[metric].dropna().median())
            else:
                cohort_median = float(well_measured[metric].median())
            if not np.isfinite(cohort_median):
                continue
            mask = out["league"] == league
            player_counts = out.loc[mask, raw_count_col].astype("Float64")
            player_gp = out.loc[mask, "GP"].astype("Float64")
            shrunk = (player_counts + k * cohort_median) / (player_gp + k)
            out.loc[mask, shrunk_col] = shrunk.astype(float)
    return out


# --- League quality multipliers + projections -------------------------------


def add_quality_adjusted(df: pd.DataFrame) -> pd.DataFrame:
    """Add `*_quality` columns: shrunk rates multiplied by league multiplier."""
    cfg = config.league_quality()
    multipliers: dict[str, float] = cfg["multipliers"]
    df = df.copy()
    df["league_multiplier"] = df["league"].map(multipliers).astype(float)
    for metric in SCALED_METRICS:
        shrunk = f"{metric}_shrunk"
        quality = f"{metric}_quality"
        if shrunk in df.columns:
            df[quality] = df[shrunk] * df["league_multiplier"]
    # PIM stays unscaled (behavior signal, not production)
    df["pim_per_gp_quality"] = df["pim_per_gp_shrunk"]
    return df


def z_score_within_position(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    """Z-score each column across all forward rows (position normalization
    happens implicitly because this is the forwards module)."""
    out = df.copy()
    for col in columns:
        if col not in out.columns:
            continue
        x = out[col].astype("Float64")
        mu = x.mean()
        sigma = x.std()
        if not np.isfinite(sigma) or sigma == 0:
            out[f"{col}_z"] = 0.0
        else:
            out[f"{col}_z"] = ((x - mu) / sigma).astype(float)
    return out


# --- NHL-only enrichment ----------------------------------------------------


def build_nhl_extras(canonical: pd.DataFrame, seasons: Iterable[int]) -> pd.DataFrame:
    """MoneyPuck 5v5 + special-teams per-60 metrics for NHL Czechs only.

    Filters MoneyPuck to:
      - playerId ∈ canonical NHL Czechs
      - situation ∈ {5on5, 5on4 (PP-for), 4on5 (PK-for)}
    Wide-pivots so each player-season has columns like g60_5on5, a60_5on5,
    xg60_5on5, points60_5on4 (PP), etc.
    """
    nhl_ids = set(canonical.loc[canonical["nhl_id"].notna(), "nhl_id"].astype(int).tolist())
    frames: list[pd.DataFrame] = []
    for season in seasons:
        path = config.RAW_DIR / f"moneypuck_skaters_{season}.parquet"
        if not path.exists():
            continue
        df = read_parquet(path)
        df = df[df["playerId"].isin(nhl_ids)].copy()
        df["season"] = season
        keep = ["playerId", "season", "situation", "games_played", "icetime",
                "I_F_goals", "I_F_primaryAssists", "I_F_shotsOnGoal", "I_F_xGoals",
                "I_F_points", "onIce_xGoalsPercentage", "onIce_corsiPercentage"]
        keep = [c for c in keep if c in df.columns]
        frames.append(df[keep])
    if not frames:
        return pd.DataFrame()
    long = pd.concat(frames, ignore_index=True)

    # Compute per-60 from icetime (which is in SECONDS)
    long["minutes"] = long["icetime"] / 60.0
    for src, tgt in (("I_F_goals", "g60"),
                     ("I_F_primaryAssists", "a1_60"),
                     ("I_F_shotsOnGoal", "shots60"),
                     ("I_F_xGoals", "xg60"),
                     ("I_F_points", "points60")):
        if src in long.columns:
            long[tgt] = long[src] / (long["minutes"] / 60.0)

    # Pivot situation-wide
    pivot_metrics = ["g60", "a1_60", "shots60", "xg60", "points60",
                     "onIce_xGoalsPercentage", "onIce_corsiPercentage"]
    pivot_metrics = [m for m in pivot_metrics if m in long.columns]
    wide = long.pivot_table(
        index=["playerId", "season"],
        columns="situation",
        values=pivot_metrics,
        aggfunc="first",
    )
    wide.columns = [f"{m}_{s}" for m, s in wide.columns]
    wide = wide.reset_index()
    return wide


# --- Main -------------------------------------------------------------------


def main() -> None:
    logging_setup()
    config.ensure_dirs()

    canonical = read_parquet(config.PROCESSED_DIR / "players.parquet")
    forwards = canonical[
        (canonical["position_normalized"] == "F")
        & (canonical["czech_eligible_flag"] != "no")
    ].copy()
    LOG.info("forward pool: %d canonical players (eligible_flag != 'no')", len(forwards))

    seasons = config.leagues()["leagues"]["nhl"]["season_window"]
    raw_stats = aggregate_player_seasons(seasons)
    LOG.info("aggregated %d (source, season) stat rows across NHL/Liiga/Extraliga", len(raw_stats))

    joined = attach_canonical_ids(raw_stats, canonical)
    joined = joined[joined["canonical_id"].isin(set(forwards["canonical_id"]))]
    LOG.info("joined to forward canonical: %d rows", len(joined))

    rates = compute_per_game_rates(joined)
    shrunk = bayesian_shrink(rates)
    full = add_quality_adjusted(shrunk)

    # Z-score per projection
    style_cols = [f"{m}_shrunk" for m in PER_GAME_METRICS]
    quality_cols = [f"{m}_quality" for m in PER_GAME_METRICS]
    full = z_score_within_position(full, style_cols + quality_cols)

    # Attach a few canonical metadata columns for downstream convenience
    meta_cols = ["canonical_id", "first_name", "last_name", "position_normalized",
                 "birth_year", "czech_eligible_flag", "iihf_appearances", "sources"]
    meta = canonical[meta_cols].copy()
    full = full.merge(meta, on="canonical_id", how="left")

    write_parquet(full, config.PROCESSED_DIR / "features_forwards.parquet")

    # NHL-only enrichment via MoneyPuck
    nhl_extras = build_nhl_extras(canonical, seasons)
    if not nhl_extras.empty:
        write_parquet(nhl_extras, config.PROCESSED_DIR / "features_forwards_nhl_extras.parquet")

    # Summary
    LOG.info("=== forwards features summary ===")
    LOG.info("forward seasons in features: %d (unique players: %d)",
             len(full), full["canonical_id"].nunique())
    LOG.info("by league: %s", full["league"].value_counts().to_dict())
    LOG.info("by season: %s", full["season"].value_counts().to_dict())
    LOG.info("by eligibility: %s", full["czech_eligible_flag"].value_counts().to_dict())
    LOG.info("NHL extras rows: %d (unique players: %d)",
             len(nhl_extras), nhl_extras["playerId"].nunique() if not nhl_extras.empty else 0)


if __name__ == "__main__":
    main()
