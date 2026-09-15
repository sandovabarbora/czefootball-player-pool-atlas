"""Tests for src/feature_eda.py (Task 17)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.feature_eda import (
    RAW_COLUMNS,
    feature_row_dict,
    pick_raw_and_feature_row,
    raw_row_dict,
)


def _fw_row(**over) -> dict:
    base = {
        "player_key": "cs|1998", "player": "Czech Star", "team": "X", "season": "2025-2026",
        "pos_group": "FW", "min": 1800, "npg_p90": 0.2, "ast_p90": 0.1, "min_share": 0.9,
        "age": 27, "cards_p90": 0.15,
        "npg_p90_shrunk": 0.18, "ast_p90_shrunk": 0.09, "min_share_shrunk": 0.9,
        "age_shrunk": 27, "cards_p90_shrunk": 0.15,
        "npg_p90_quality": 0.08, "ast_p90_quality": 0.04, "min_share_quality": 0.9,
        "age_quality": 27, "cards_p90_quality": 0.15,
        "npg_p90_quality_z": 0.5, "ast_p90_quality_z": 0.2, "min_share_quality_z": 0.1,
        "age_quality_z": 0.0, "cards_p90_quality_z": -0.1,
    }
    base.update(over)
    return base


def _empty_fw() -> pd.DataFrame:
    return pd.DataFrame(columns=list(_fw_row().keys()))


def test_pick_raw_and_feature_row_picks_most_minutes_home_player_with_a_feature_row():
    tables = pd.DataFrame([
        {"player": "Czech Star", "player_key": "cs|1998", "nation": "CZE", "season": "2025-2026",
         "team": "X", "league": "CZE-First League", "pos": "FW", "born": 1998, "age": 27, "mp": 20,
         "min": 1800, "gls": 5, "ast": 2, "pk": 1, "crdy": 3, "crdr": 0},
        {"player": "Czech Bench", "player_key": "cb|2000", "nation": "CZE", "season": "2025-2026",
         "team": "Y", "league": "CZE-First League", "pos": "MF", "born": 2000, "age": 25, "mp": 5,
         "min": 300, "gls": 0, "ast": 0, "pk": 0, "crdy": 0, "crdr": 0},  # no feature row (below floor)
        {"player": "Foreigner", "player_key": "f|1997", "nation": "FRA", "season": "2025-2026",
         "team": "X", "league": "CZE-First League", "pos": "FW", "born": 1997, "age": 28, "mp": 25,
         "min": 2200, "gls": 10, "ast": 5, "pk": 2, "crdy": 1, "crdr": 0},  # more minutes, wrong nation
    ])
    fw = pd.DataFrame([_fw_row()])
    features_by_group = {"FW": fw, "MF": _empty_fw(), "DF": _empty_fw()}

    raw, feat = pick_raw_and_feature_row(tables, features_by_group, "2025-2026")
    assert raw["player"] == "Czech Star"
    assert feat["player_key"] == "cs|1998"


def test_pick_raw_and_feature_row_raises_when_nobody_qualifies():
    tables = pd.DataFrame([
        {"player": "Czech Bench", "player_key": "cb|2000", "nation": "CZE", "season": "2025-2026",
         "team": "Y", "league": "CZE-First League", "pos": "MF", "born": 2000, "age": 25, "mp": 5,
         "min": 300, "gls": 0, "ast": 0, "pk": 0, "crdy": 0, "crdr": 0},
    ])
    with pytest.raises(ValueError, match="2025-2026"):
        pick_raw_and_feature_row(tables, {"FW": _empty_fw(), "MF": _empty_fw(), "DF": _empty_fw()}, "2025-2026")


def test_raw_row_dict_has_every_column_ints_where_fbref_types_are_integer_like():
    row = pd.Series({
        "league": "CZE-First League", "season": "2025-2026", "team": "X", "player": "Czech Star",
        "nation": "CZE", "pos": "FW", "born": 1998, "age": pd.NA, "mp": 20, "min": 1800,
        "gls": 5, "ast": 2, "pk": 1, "crdy": 3, "crdr": 0,
    })
    out = raw_row_dict(row)
    assert list(out) == RAW_COLUMNS
    assert out["born"] == 1998 and isinstance(out["born"], int)
    assert out["age"] is None  # NA stays None, not 0 or "NA"
    assert out["player"] == "Czech Star" and isinstance(out["player"], str)


def test_feature_row_dict_carries_the_four_pipeline_stages_per_feature():
    row = pd.Series(_fw_row())
    out = feature_row_dict(row)
    assert out["player"] == "Czech Star" and out["pos_group"] == "FW"
    assert out["npg_p90"] == {"raw": 0.2, "shrunk": 0.18, "quality": 0.08, "z": 0.5}
    assert set(out) == {"player", "pos_group", *["npg_p90", "ast_p90", "min_share", "age", "cards_p90"]}


def test_feature_row_dict_handles_missing_stage_values():
    row = pd.Series(_fw_row(cards_p90_quality_z=np.nan))
    out = feature_row_dict(row)
    assert out["cards_p90"]["z"] is None
