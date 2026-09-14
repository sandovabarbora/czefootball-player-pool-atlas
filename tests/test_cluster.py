"""Tests for src.cluster: silhouette-driven K selection and clustering."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src import config
from sklearn.datasets import make_blobs

from src.cluster import K_RANGE, cluster_group, select_k
from src.reduce import reduce_group


def test_select_k_finds_the_true_number_of_blobs():
    x, _ = make_blobs(
        n_samples=300, centers=4, n_features=5, cluster_std=0.5, random_state=42
    )
    best_k, scores = select_k(x, k_range=K_RANGE)
    assert best_k == 4
    assert set(scores.keys()) == set(K_RANGE)


def test_select_k_handles_too_few_rows():
    x = np.random.default_rng(0).normal(size=(3, 2))
    best_k, scores = select_k(x, k_range=K_RANGE)
    assert best_k >= 2


def _toy_features(n: int = 60, season: str = config.seasons()["metrics"]) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    df = pd.DataFrame({
        "player_key": [f"p{i}" for i in range(n)],
        "player": "x",
        "season": season,
        "league": np.where(np.arange(n) % 2 == 0, "Fortuna Liga", "1. Liga"),
        "team": "T",
        "born": 1998,
        "pos_group": "FW",
        "home_eligible": False,
        "nt_flag": False,
        "min": 1500,
    })
    for f in ["npg_p90", "ast_p90", "min_share", "age", "cards_p90"]:
        df[f"{f}_shrunk"] = rng.normal(size=n)
        df[f"{f}_quality"] = rng.normal(size=n)
        df[f"{f}_shrunk_z"] = df[f"{f}_shrunk"]
        df[f"{f}_quality_z"] = df[f"{f}_quality"]
    return df


def test_cluster_group_writes_cluster_labels():
    df = _toy_features()
    coords, _ = reduce_group(df, "FW")
    out, summary = cluster_group(df, coords, "FW")
    assert "cluster_style" in out.columns
    assert "cluster_quality" in out.columns
    style_labels = set(out["cluster_style"].dropna().unique())
    assert style_labels
    assert all(label.startswith("C") for label in style_labels)
    assert summary
    assert {"position", "projection", "cluster", "k", "silhouette", "n", "top_leagues"} <= set(summary[0].keys())
