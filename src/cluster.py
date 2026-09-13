"""KMeans clustering with silhouette-driven K selection.

K is chosen per (position group, projection) by silhouette score over
k = 3..6, not pre-chosen to match a fixed number of archetypes. As with
`reduce.py`, KMeans is fit on the metrics-season rows with a complete
feature vector (`config.seasons()["metrics"]`), then used to predict a
cluster for every season's rows with a complete feature vector -- so the
previous/current seasons are assigned into the same clusters the metrics
season defined. Rows with a missing feature get no cluster.

Descriptive (non-evaluative) labels for each cluster live in
`config/cluster_labels.yaml`, written by hand after inspecting the medians
of each cluster (see the module docstring's `main()` for the summary that
informs those labels).

Inputs:
  data/processed/features_{FW,MF,DF}.parquet
  data/processed/coords_{FW,MF,DF}.parquet  (written by reduce.py)

Outputs (overwrites coords parquets with added cluster columns):
  data/processed/coords_{FW,MF,DF}.parquet  + cluster_style, cluster_quality
      (labels "C0".."Ck", NA for rows with a missing feature)
  data/processed/cluster_summary.parquet  -- per-cluster aggregates
      (position, projection, cluster, k, silhouette, n, medians, top leagues)
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from src import config
from src.logging_setup import setup as logging_setup
from src.reduce import PROJECTIONS, feature_columns
from src.utils import read_parquet, write_parquet

LOG = logging.getLogger(__name__)

K_RANGE: tuple[int, ...] = (3, 4, 5, 6)

# Columns used to describe cluster medians for the labeling step (Step 4 of
# the task-7 brief) -- plain, readable feature values, not the z-scored
# inputs to KMeans.
MEDIAN_COLS: tuple[str, ...] = ("npg_p90_quality", "ast_p90_quality", "min_share", "age", "cards_p90")


def select_k(x: np.ndarray, k_range: tuple[int, ...] = K_RANGE) -> tuple[int, dict[int, float]]:
    """Pick K by silhouette score. Returns (best_k, scores_by_k)."""
    if len(x) < max(k_range) + 1:
        max_safe = max(2, len(x) - 1)
        k_range = tuple(k for k in k_range if k <= max_safe)
        if not k_range:
            return 2, {}
    scores: dict[int, float] = {}
    for k in k_range:
        km = KMeans(n_clusters=k, n_init=10, random_state=config.RANDOM_SEED)
        labels = km.fit_predict(x)
        if len(set(labels)) < 2:
            continue
        scores[k] = float(silhouette_score(x, labels))
    if not scores:
        return min(k_range), {}
    best_k = max(scores, key=scores.get)
    return best_k, scores


def _top_leagues(members: pd.DataFrame, n: int = 3) -> str:
    if "league" not in members.columns or members.empty:
        return ""
    counts = members["league"].value_counts().head(n)
    return "; ".join(f"{league} ({count})" for league, count in counts.items())


def cluster_group(
    features_df: pd.DataFrame,
    coords_df: pd.DataFrame,
    group: str,
) -> tuple[pd.DataFrame, list[dict]]:
    """Run KMeans for both style + quality projections; attach to coords.

    Returns (coords_with_clusters, summary_rows).
    """
    out = coords_df.copy()
    summary: list[dict] = []
    metrics_season = config.seasons()["metrics"]

    for label, suffix in PROJECTIONS:
        cols = feature_columns(suffix)
        kept_mask = features_df[cols].notna().all(axis=1)
        fit_mask = kept_mask & (features_df["season"] == metrics_season)

        col = f"cluster_{label}"
        out[col] = pd.NA

        if fit_mask.sum() < 4:
            LOG.warning("%s %s: too few metrics-season rows (%d) to cluster",
                        group, label, int(fit_mask.sum()))
            continue

        x_fit = features_df.loc[fit_mask, cols].astype(float).values
        best_k, scores = select_k(x_fit)
        LOG.info("%s %s: silhouette scores %s, best K=%d",
                 group, label, {k: round(v, 3) for k, v in scores.items()}, best_k)

        km = KMeans(n_clusters=best_k, n_init=10, random_state=config.RANDOM_SEED)
        km.fit(x_fit)

        if not kept_mask.any():
            continue
        x_all = features_df.loc[kept_mask, cols].astype(float).values
        cluster_ids = km.predict(x_all)
        out.loc[kept_mask, col] = [f"C{cid}" for cid in cluster_ids]

        for cid in sorted(set(cluster_ids)):
            members = out[out[col] == f"C{cid}"]
            feat_members = features_df.loc[members.index]
            present_cols = [c for c in MEDIAN_COLS if c in feat_members.columns]
            medians = feat_members[present_cols].median(numeric_only=True)
            summary.append({
                "position": group,
                "projection": label,
                "cluster": f"C{cid}",
                "k": int(best_k),
                "silhouette": float(scores.get(best_k, 0.0)),
                "n": int(len(members)),
                "top_leagues": _top_leagues(members),
                **{f"median_{c}": float(medians.get(c, np.nan)) for c in MEDIAN_COLS},
            })
    return out, summary


def main() -> None:
    logging_setup()
    config.ensure_dirs()

    all_summary: list[dict] = []
    for group in config.features()["groups"]:
        features_df = read_parquet(config.PROCESSED_DIR / f"features_{group}.parquet")
        coords_df = read_parquet(config.PROCESSED_DIR / f"coords_{group}.parquet")
        out, summary = cluster_group(features_df, coords_df, group)
        write_parquet(out, config.PROCESSED_DIR / f"coords_{group}.parquet")
        all_summary.extend(summary)

    summary_df = pd.DataFrame(all_summary)
    write_parquet(summary_df, config.PROCESSED_DIR / "cluster_summary.parquet")

    LOG.info("=== cluster sizes ===")
    LOG.info("\n%s", summary_df[["position", "projection", "cluster", "k", "silhouette", "n", "top_leagues"]]
              .to_string(index=False))


if __name__ == "__main__":
    main()
