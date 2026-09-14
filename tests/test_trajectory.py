"""Tests for src.trajectory: min-minutes gate, direction thresholds and the
mid-season-transfer collapse."""

from __future__ import annotations

import pandas as pd

from src import config
from src.trajectory import compute_trajectory

PREV, METRICS = config.seasons()["previous"], config.seasons()["metrics"]


def _row(player_key, season, min_, npg_q, ast_q, **kw):
    row = {
        "player_key": player_key,
        "player": player_key,
        "season": season,
        "league": "Fortuna Liga",
        "nation": "CZE",
        "czech_eligible": True,
        "nt_flag": False,
        "pos_group": "FW",
        "min": min_,
        "npg_p90_quality": npg_q,
        "ast_p90_quality": ast_q,
    }
    row.update(kw)
    return row


def test_compute_trajectory_requires_900_min_in_both_seasons():
    rows = [
        # Qualifies: >=900 min both seasons.
        _row("a", PREV, 1000, 0.30, 0.10),
        _row("a", METRICS, 1000, 0.30, 0.10),
        # Fails: under 900 min in the previous season.
        _row("b", PREV, 800, 0.30, 0.10),
        _row("b", METRICS, 1000, 0.30, 0.10),
        # Fails: under 900 min in the metrics season.
        _row("c", PREV, 1000, 0.30, 0.10),
        _row("c", METRICS, 700, 0.30, 0.10),
    ]
    features = pd.DataFrame(rows)
    out = compute_trajectory(features, "FW")
    assert set(out["player_key"]) == {"a"}


def test_compute_trajectory_direction_thresholds():
    rows = [
        # delta = +0.10 -> improving (> 0.05)
        _row("improver", PREV, 1000, 0.20, 0.00),
        _row("improver", METRICS, 1000, 0.30, 0.00),
        # delta = -0.10 -> declining (< -0.05)
        _row("decliner", PREV, 1000, 0.30, 0.00),
        _row("decliner", METRICS, 1000, 0.20, 0.00),
        # delta = +0.02 -> stable (within +-0.05)
        _row("stable_player", PREV, 1000, 0.20, 0.00),
        _row("stable_player", METRICS, 1000, 0.22, 0.00),
    ]
    features = pd.DataFrame(rows)
    out = compute_trajectory(features, "FW").set_index("player_key")
    assert out.loc["improver", "direction"] == "improving"
    assert out.loc["decliner", "direction"] == "declining"
    assert out.loc["stable_player", "direction"] == "stable"


def test_compute_trajectory_output_columns():
    rows = [
        _row("a", PREV, 1000, 0.30, 0.10),
        _row("a", METRICS, 1000, 0.30, 0.10),
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
    rows = [_row("a", PREV, 1000, 0.30, 0.10)]
    features = pd.DataFrame(rows)
    out = compute_trajectory(features, "FW")
    assert out.empty


def test_compute_trajectory_collapses_mid_season_transfers():
    rows = [
        # Split season: 500 + 500 minutes across two clubs passes the 900 gate
        # only once the two rows are collapsed into the season total.
        _row("split", PREV, 500, 0.20, 0.00, team="A"),
        _row("split", PREV, 500, 0.40, 0.00, team="B"),
        _row("split", METRICS, 1000, 0.30, 0.00, team="B"),
        # Duplicated in the metrics season too: must appear exactly once, and
        # the join must not fan out into two trajectory rows.
        _row("dup", PREV, 1000, 0.30, 0.00, team="A"),
        _row("dup", METRICS, 900, 0.30, 0.00, team="A"),
        _row("dup", METRICS, 300, 0.30, 0.00, team="B"),
    ]
    out = compute_trajectory(pd.DataFrame(rows), "FW").set_index("player_key")

    assert set(out.index) == {"split", "dup"}
    assert out.loc["split", "min_prev"] == 1000
    # minutes-weighted rate over the two stints: (0.20 * 500 + 0.40 * 500) / 1000
    assert out.loc["split", "npg_ast_quality_prev"] == 0.30
    assert out.loc["split", "direction"] == "stable"
    assert out.loc["dup", "min_curr"] == 1200
    assert len(out) == 2
