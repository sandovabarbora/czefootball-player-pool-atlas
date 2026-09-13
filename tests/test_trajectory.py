"""Tests for src.trajectory: min-minutes gate and direction thresholds."""

from __future__ import annotations

import pandas as pd

from src.trajectory import compute_trajectory


def _row(player_key, season, min_, npg_q, ast_q, **kw):
    row = {
        "player_key": player_key,
        "player": player_key,
        "season": season,
        "league": "Fortuna Liga",
        "nation": "CZE",
        "czech_eligible": True,
        "nt_flag": False,
        "min": min_,
        "npg_p90_quality": npg_q,
        "ast_p90_quality": ast_q,
    }
    row.update(kw)
    return row


def test_compute_trajectory_requires_900_min_in_both_seasons():
    rows = [
        # Qualifies: >=900 min both seasons.
        _row("a", "2023-2024", 1000, 0.30, 0.10),
        _row("a", "2024-2025", 1000, 0.30, 0.10),
        # Fails: under 900 min in the previous season.
        _row("b", "2023-2024", 800, 0.30, 0.10),
        _row("b", "2024-2025", 1000, 0.30, 0.10),
        # Fails: under 900 min in the metrics season.
        _row("c", "2023-2024", 1000, 0.30, 0.10),
        _row("c", "2024-2025", 700, 0.30, 0.10),
    ]
    features = pd.DataFrame(rows)
    out = compute_trajectory(features, "FW")
    assert set(out["player_key"]) == {"a"}


def test_compute_trajectory_direction_thresholds():
    rows = [
        # delta = +0.10 -> improving (> 0.05)
        _row("improver", "2023-2024", 1000, 0.20, 0.00),
        _row("improver", "2024-2025", 1000, 0.30, 0.00),
        # delta = -0.10 -> declining (< -0.05)
        _row("decliner", "2023-2024", 1000, 0.30, 0.00),
        _row("decliner", "2024-2025", 1000, 0.20, 0.00),
        # delta = +0.02 -> stable (within +-0.05)
        _row("stable_player", "2023-2024", 1000, 0.20, 0.00),
        _row("stable_player", "2024-2025", 1000, 0.22, 0.00),
    ]
    features = pd.DataFrame(rows)
    out = compute_trajectory(features, "FW").set_index("player_key")
    assert out.loc["improver", "direction"] == "improving"
    assert out.loc["decliner", "direction"] == "declining"
    assert out.loc["stable_player", "direction"] == "stable"


def test_compute_trajectory_output_columns():
    rows = [
        _row("a", "2023-2024", 1000, 0.30, 0.10),
        _row("a", "2024-2025", 1000, 0.30, 0.10),
    ]
    features = pd.DataFrame(rows)
    out = compute_trajectory(features, "FW")
    expected = {
        "player_key", "player", "league", "nation", "czech_eligible", "nt_flag",
        "min_prev", "min_curr", "npg_ast_quality_prev", "npg_ast_quality_curr",
        "delta", "direction",
    }
    assert expected <= set(out.columns)


def test_compute_trajectory_empty_when_no_overlap():
    rows = [_row("a", "2023-2024", 1000, 0.30, 0.10)]
    features = pd.DataFrame(rows)
    out = compute_trajectory(features, "FW")
    assert out.empty
