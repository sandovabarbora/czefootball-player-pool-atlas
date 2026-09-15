"""Tests for src/feature_eda.py (Task 17)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.feature_eda import (
    RAW_COLUMNS,
    age_production_curve_stat,
    assemble_output,
    build_rejected,
    feature_row_dict,
    missingness_stat,
    penalty_share_stat,
    pick_raw_and_feature_row,
    raw_row_dict,
    red_card_zero_share_stat,
    render_distributions_figure,
    render_shrinkage_figure,
    starts_proxy_stat,
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


# =============================================================================
# Rejected-candidates statistics, toy corpus
# =============================================================================


def _toy_corpus() -> pd.DataFrame:
    return pd.DataFrame([
        # A: half of goals from penalties (5 of 10) -- the top penalty share
        {"player": "A", "league": "L1", "season": "2025-2026", "min": 1800, "mp": 20, "gls": 10, "pk": 5,
         "ast": 2, "crdr": 0, "npg_p90": 0.25, "ast_p90": 0.1, "age": 20},
        {"player": "B", "league": "L1", "season": "2025-2026", "min": 900, "mp": 10, "gls": 4, "pk": 0,
         "ast": 1, "crdr": 1, "npg_p90": 0.4, "ast_p90": 0.1, "age": 27},
        {"player": "C", "league": "L2", "season": "2025-2026", "min": 2700, "mp": 30, "gls": 9, "pk": 1,
         "ast": 3, "crdr": 0, "npg_p90": 0.267, "ast_p90": 0.1, "age": 31},
        {"player": "D", "league": "L2", "season": "2025-2026", "min": 450, "mp": 5, "gls": 0, "pk": 0,
         "ast": 0, "crdr": 0, "npg_p90": 0.0, "ast_p90": 0.0, "age": 24},
    ])


def test_penalty_share_stat_top_rows_and_correlation():
    out = penalty_share_stat(_toy_corpus(), n=2)
    assert out["corr"] is not None
    assert out["top"][0] == {"player": "A", "league": "L1", "season": "2025-2026", "share": 0.5}
    assert len(out["top"]) == 2


def test_starts_proxy_stat_correlates_mp_and_min():
    out = starts_proxy_stat(_toy_corpus())
    assert out["corr"] is not None and out["corr"] > 0.9  # mp and min move together in the toy data


def test_red_card_zero_share():
    out = red_card_zero_share_stat(_toy_corpus())
    assert out["zero_share"] == pytest.approx(0.75)  # 3 of 4 rows have crdr == 0


def test_age_production_curve_bands_ordered_and_populated():
    bands = age_production_curve_stat(_toy_corpus())
    labels = [b["band"] for b in bands]
    assert labels == sorted(labels, key=lambda b: ["U22", "23-25", "26-29", "30+"].index(b))
    assert all(b["n"] >= 1 for b in bands)


def test_missingness_stat_counts_missing_per_raw_column():
    tables = pd.DataFrame({c: [1, None] for c in RAW_COLUMNS})
    out = missingness_stat(tables)
    by_col = {r["column"]: r for r in out}
    assert by_col["born"]["missing"] == 1
    assert by_col["born"]["share"] == pytest.approx(0.5)


def test_build_rejected_has_five_rows_with_expected_decision_codes():
    penalty = {"corr": 0.9, "top": []}
    starts = {"corr": 0.95}
    redcard = {"zero_share": 0.9}
    age_bands = [{"band": "U22", "median": 0.1, "n": 5}, {"band": "30+", "median": 0.3, "n": 5}]
    missingness = [{"column": "born", "missing": 2, "share": 0.02}]
    rows = build_rejected(penalty, starts, redcard, age_bands, missingness)
    assert len(rows) == 5
    decisions = {r["candidate"]: r["decision"] for r in rows}
    assert decisions == {
        "gls_p90": "replaced_npg", "mp": "replaced_min_share", "crdr_p90": "folded_cards",
        "age": "kept", "born": "kept_key",
    }
    for r in rows:
        assert set(r) == {"candidate", "statistic", "value", "decision"}
    age_row = next(r for r in rows if r["candidate"] == "age")
    assert age_row["value"] == pytest.approx(0.2)  # 0.3 - 0.1


# =============================================================================
# Figures (smoke tests, tmp_path)
# =============================================================================


def _toy_features_all() -> pd.DataFrame:
    from src import config
    rng = np.random.default_rng(0)
    rows = []
    for i in range(40):
        league = config.DOMESTIC_LEAGUE if i % 2 == 0 else "ENG-Premier League"
        minutes = int(rng.uniform(450, 2700))
        raw = float(rng.uniform(0.0, 0.5))
        rows.append({
            "league": league, "player": f"Player {i}", "min": minutes,
            "npg_p90": raw, "npg_p90_shrunk": raw * 0.7 + 0.05,
            "ast_p90": float(rng.uniform(0.0, 0.3)), "min_share": float(rng.uniform(0.2, 1.0)),
            "age": int(rng.uniform(18, 34)), "cards_p90": float(rng.uniform(0.0, 0.3)),
            "home_eligible": i % 2 == 0,
        })
    return pd.DataFrame(rows)


def test_render_distributions_figure_writes_svg(tmp_path):
    out_path = tmp_path / "eda_distributions.svg"
    meta = render_distributions_figure(_toy_features_all(), out_path)
    assert out_path.exists()
    text = out_path.read_text(encoding="utf-8")
    assert "<svg" in text
    assert meta["leagues"]


def test_render_shrinkage_figure_writes_svg_and_returns_most_shrunk(tmp_path):
    out_path = tmp_path / "eda_shrinkage.svg"
    most_shrunk = render_shrinkage_figure(_toy_features_all(), phantom_minutes=900, out_path=out_path)
    assert out_path.exists()
    assert "<svg" in out_path.read_text(encoding="utf-8")
    assert most_shrunk is not None
    assert set(most_shrunk) == {"player", "league", "min", "raw", "shrunk", "delta"}


def test_render_shrinkage_figure_returns_none_on_empty_input(tmp_path):
    empty = pd.DataFrame(columns=["league", "player", "min", "npg_p90", "npg_p90_shrunk", "home_eligible"])
    out_path = tmp_path / "eda_shrinkage_empty.svg"
    assert render_shrinkage_figure(empty, phantom_minutes=900, out_path=out_path) is None


# =============================================================================
# JSON assembly shape (pure)
# =============================================================================


def test_assemble_output_shape_round_trips_through_json():
    import json

    from src.feature_eda import _INT_RAW_COLUMNS
    raw_row = raw_row_dict(pd.Series({c: (1 if c in _INT_RAW_COLUMNS else "x") for c in RAW_COLUMNS}))
    feature_row = feature_row_dict(pd.Series(_fw_row()))
    penalty = penalty_share_stat(_toy_corpus())
    age_bands = age_production_curve_stat(_toy_corpus())
    missingness = missingness_stat(pd.DataFrame({c: [1] for c in RAW_COLUMNS}))
    rejected = build_rejected(penalty, starts_proxy_stat(_toy_corpus()), red_card_zero_share_stat(_toy_corpus()),
                              age_bands, missingness)
    out = assemble_output("2025-2026", raw_row, feature_row, rejected, penalty, age_bands, missingness,
                          most_shrunk=None, distributions={"leagues": ["L1"], "log_scaled": []})
    assert set(out) == {"metrics_season", "raw_row", "feature_row", "rejected", "penalty_top",
                        "age_bands", "missingness", "most_shrunk", "distributions"}
    assert len(out["rejected"]) == 5
    json.dumps(out)  # round-trips through plain JSON types
