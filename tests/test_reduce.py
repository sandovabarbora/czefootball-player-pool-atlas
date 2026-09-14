"""Tests for src.reduce: PCA projections per position group."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src import config

from src.reduce import reduce_group


def _toy_features(n: int = 60, season: str = config.seasons()["metrics"]) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    df = pd.DataFrame({
        "player_key": [f"p{i}" for i in range(n)],
        "player": "x",
        "season": season,
        "league": "L",
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


def test_reduce_group_returns_two_projections():
    df = _toy_features()
    coords, loadings = reduce_group(df, "FW")
    assert {"pc1_style", "pc2_style", "pc1_quality", "pc2_quality"} <= set(coords.columns)
    assert len(coords) == len(df)
    assert loadings["projection"].nunique() == 2


def test_reduce_group_meta_columns_use_player_key():
    df = _toy_features()
    coords, _ = reduce_group(df, "FW")
    assert "player_key" in coords.columns
    assert "fbref_id" not in coords.columns


def test_reduce_group_loadings_have_position_and_feature_columns():
    df = _toy_features()
    _, loadings = reduce_group(df, "FW")
    assert set(loadings["position"].unique()) == {"FW"}
    for feat in ["npg_p90", "ast_p90", "min_share", "age", "cards_p90"]:
        assert feat in loadings.columns
    assert set(loadings["pc"].unique()) == {"PC1", "PC2"}


def test_reduce_group_missing_features_give_nan_coords_no_crash():
    df = _toy_features()
    # Blank out one row's style feature vector -- it should get NaN coords
    # rather than crash the whole reduction.
    df.loc[0, "npg_p90_shrunk_z"] = np.nan
    coords, _ = reduce_group(df, "FW")
    assert pd.isna(coords.loc[0, "pc1_style"])
    assert pd.isna(coords.loc[0, "pc2_style"])
    # Quality projection for that row is untouched and still numeric.
    assert not pd.isna(coords.loc[0, "pc1_quality"])


def test_reduce_group_fits_on_metrics_season_only():
    """Rows from the previous/current seasons should still get coordinates,
    projected into the space fit on the metrics season."""
    metrics = _toy_features(n=60, season=config.seasons()["metrics"])
    other = _toy_features(n=10, season=config.seasons()["previous"])
    other["player_key"] = [f"q{i}" for i in range(10)]
    df = pd.concat([metrics, other], ignore_index=True)
    coords, _ = reduce_group(df, "FW")
    # All rows (including the non-metrics season) get real coordinates.
    assert coords["pc1_style"].notna().all()
    assert coords["pc1_quality"].notna().all()
