"""Dimensionality reduction: PCA for forwards, midfielders and defenders.

Two projection variants per position group (locked critique decision):
  - STYLE   -- z-scored features without league multipliers (`*_shrunk_z`)
  - QUALITY -- z-scored features with league multipliers applied (`*_quality_z`)

Each projection is reduced to 2 components with PCA. PCA is fit on the rows
of the metrics season only (`config.seasons()["metrics"]`) that have a
complete feature vector, then used to transform every season's rows with a
complete feature vector -- so the previous/current seasons land in the same
component space as the metrics season they are compared against. Rows with
a missing feature get NaN coordinates.

All stochastic operations use `src.config.RANDOM_SEED` (=42).

Feature vector (see `src.features.FEATURES`):
  - npg_p90    (non-penalty goals per 90)
  - ast_p90    (assists per 90)
  - min_share  (minutes / (club matches * 90))
  - age        (at season start)
  - cards_p90  ((yellow + 2*red) per 90)

Inputs:
  data/processed/features_{FW,MF,DF}.parquet

Outputs:
  data/processed/coords_{FW,MF,DF}.parquet
      player_key, player, season, league, team, born, pos_group,
      czech_eligible, nt_flag, min,
      pc1_style, pc2_style, pc1_quality, pc2_quality
  data/processed/pca_loadings.parquet
      One row per (position, projection, pc) with explained_variance and
      one column per feature holding its loading, for the methodology
      section. `projection` in {style, quality}.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

from src import config
from src.features import FEATURES
from src.logging_setup import setup as logging_setup
from src.utils import read_parquet, write_parquet

LOG = logging.getLogger(__name__)

# (projection label, feature-column suffix)
PROJECTIONS: tuple[tuple[str, str], ...] = (("style", "shrunk"), ("quality", "quality"))

META_COLS: list[str] = [
    "player_key", "player", "season", "league", "team", "born",
    "pos_group", "czech_eligible", "nt_flag", "min",
]

MIN_FIT_ROWS = 4


def feature_columns(suffix: str) -> list[str]:
    """Z-scored feature columns for one projection variant."""
    return [f"{f}_{suffix}_z" for f in FEATURES]


def _reduce_one(df: pd.DataFrame, suffix: str, label: str, group: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fit PCA on the metrics-season rows, transform all complete rows.

    Returns:
        (coords_df, loadings_df). coords_df has one row per input row
        (NaN for rows with a missing feature). loadings_df has one row per
        principal component.
    """
    cols = feature_columns(suffix)
    kept_mask = df[cols].notna().all(axis=1)
    metrics_season = config.seasons()["metrics"]
    fit_mask = kept_mask & (df["season"] == metrics_season)
    n_fit = int(fit_mask.sum())

    out = pd.DataFrame(index=df.index, dtype=float)
    out[f"pc1_{label}"] = np.nan
    out[f"pc2_{label}"] = np.nan

    if n_fit < MIN_FIT_ROWS:
        LOG.warning("%s %s: too few metrics-season rows (%d) to fit PCA; skipping", group, label, n_fit)
        return out, pd.DataFrame()

    x_fit = df.loc[fit_mask, cols].astype(float).values
    pca = PCA(n_components=2, random_state=config.RANDOM_SEED)
    pca.fit(x_fit)

    if kept_mask.any():
        x_all = df.loc[kept_mask, cols].astype(float).values
        transformed = pca.transform(x_all)
        out.loc[kept_mask, f"pc1_{label}"] = transformed[:, 0]
        out.loc[kept_mask, f"pc2_{label}"] = transformed[:, 1]

    loadings_rows: list[dict] = []
    for pc_idx in range(2):
        row = {
            "position": group,
            "projection": label,
            "pc": f"PC{pc_idx + 1}",
            "explained_variance": float(pca.explained_variance_ratio_[pc_idx]),
        }
        for f_idx, feat in enumerate(FEATURES):
            row[feat] = float(pca.components_[pc_idx, f_idx])
        loadings_rows.append(row)
    return out, pd.DataFrame(loadings_rows)


def reduce_group(df: pd.DataFrame, group: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run both style + quality PCA projections for one position group."""
    LOG.info("reducing %s features: %d rows", group, len(df))
    coords_parts: list[pd.DataFrame] = []
    loadings_parts: list[pd.DataFrame] = []
    for label, suffix in PROJECTIONS:
        coords, loadings = _reduce_one(df, suffix, label, group)
        coords_parts.append(coords)
        loadings_parts.append(loadings)

    coords = pd.concat(coords_parts, axis=1)
    meta_cols = [c for c in META_COLS if c in df.columns]
    out = pd.concat([df[meta_cols].reset_index(drop=True), coords.reset_index(drop=True)], axis=1)
    loadings = pd.concat(loadings_parts, ignore_index=True)
    return out, loadings


def main() -> None:
    logging_setup()
    config.ensure_dirs()
    np.random.seed(config.RANDOM_SEED)

    all_loadings: list[pd.DataFrame] = []
    for group in config.features()["groups"]:
        df = read_parquet(config.PROCESSED_DIR / f"features_{group}.parquet")
        coords, loadings = reduce_group(df, group)
        write_parquet(coords, config.PROCESSED_DIR / f"coords_{group}.parquet")
        all_loadings.append(loadings)

    combined = pd.concat(all_loadings, ignore_index=True)
    write_parquet(combined, config.PROCESSED_DIR / "pca_loadings.parquet")

    LOG.info("=== PCA explained variance (PC1 + PC2) ===")
    ev = combined.groupby(["position", "projection"])["explained_variance"].sum()
    LOG.info("\n%s", ev.to_string())


if __name__ == "__main__":
    main()
