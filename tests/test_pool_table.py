"""Tests for src/pool_table.py -- every pool player as one row (Task 30)."""

from __future__ import annotations

import pandas as pd
import pytest

from src.pool_table import build_keeper_rows, build_rows

HEADLINE = ["ENG-Premier League", "GER-Bundesliga"]
STEPPING = ["NED-Eredivisie"]
DOMESTIC = "CZE-First League"


def _feats():
    base = {"season": "2025-2026", "home_eligible": True, "nt_flag": False, "min_share": 0.5,
            "npg_p90_quality": 0.1, "ast_p90_quality": 0.05, "npg_p90": 0.3, "ast_p90": 0.1}
    return pd.DataFrame([
        # a regular in the home league
        base | {"league": DOMESTIC, "team": "Sparta", "player": "Jan Novák", "player_key": "jan novak|2000",
                "pos_group": "FW", "born": 2000, "age": 25, "min": 1800},
        # a mid-season mover: two rows, one player, minutes to be summed
        base | {"league": DOMESTIC, "team": "Teplice", "player": "Petr Mover", "player_key": "petr mover|1999",
                "pos_group": "MF", "born": 1999, "age": 26, "min": 600, "npg_p90_quality": 0.0},
        base | {"league": "ENG-Premier League", "team": "Wolves", "player": "Petr Mover",
                "player_key": "petr mover|1999", "pos_group": "MF", "born": 1999, "age": 26, "min": 1200,
                "npg_p90_quality": 0.3},
        # a second midfielder, weaker, to give Mover a rank to beat
        base | {"league": DOMESTIC, "team": "Slavia", "player": "Karel Druhý", "player_key": "karel druhy|1995",
                "pos_group": "MF", "born": 1995, "age": 30, "min": 900, "npg_p90_quality": 0.02},
        # not eligible: must not appear
        base | {"league": DOMESTIC, "team": "Slavia", "player": "Foreign Guy", "player_key": "foreign guy|1998",
                "pos_group": "MF", "born": 1998, "age": 27, "min": 2000, "home_eligible": False},
        # wrong season: must not appear
        base | {"league": DOMESTIC, "team": "Sparta", "player": "Old Season", "player_key": "old season|1990",
                "pos_group": "DF", "born": 1990, "age": 34, "min": 2000, "season": "2024-2025"},
    ])


def _roles():
    return pd.DataFrame([
        {"league": DOMESTIC, "season": "2025-2026", "team": "Sparta", "player_key": "jan novak|2000",
         "starts": 20, "subs": 3, "compl": 12, "mn_per_start": 82.0, "crs": 40, "interceptions": 10,
         "tklw": 15, "fld": 20, "fls": 18},
        {"league": DOMESTIC, "season": "2025-2026", "team": "Teplice", "player_key": "petr mover|1999",
         "starts": 6, "subs": 2, "compl": 3, "mn_per_start": 70.0, "crs": 5, "interceptions": 4,
         "tklw": 6, "fld": 5, "fls": 4},
        {"league": "ENG-Premier League", "season": "2025-2026", "team": "Wolves", "player_key": "petr mover|1999",
         "starts": 13, "subs": 1, "compl": 9, "mn_per_start": 85.0, "crs": 10, "interceptions": 12,
         "tklw": 14, "fld": 7, "fls": 9},
    ])


def test_build_rows_keeps_only_eligible_players_of_the_season():
    rows = build_rows(_feats(), _roles(), "2025-2026", HEADLINE, STEPPING, DOMESTIC)
    assert {r["player"] for r in rows} == {"Jan Novák", "Petr Mover", "Karel Druhý"}


def test_a_mid_season_mover_is_one_row_with_both_stints():
    rows = {r["player_key"]: r for r in build_rows(_feats(), _roles(), "2025-2026", HEADLINE, STEPPING, DOMESTIC)}
    m = rows["petr mover|1999"]
    assert m["moved"] and m["min"] == 1800
    assert m["starts"] == 19 and m["subs"] == 3 and m["compl"] == 12
    # the lead club is the one with more minutes, and its tier is the row's tier
    assert m["club"] == "Wolves" and m["tier"] == "top9"
    assert [s["team"] for s in m["stints"]] == ["Wolves", "Teplice"]
    assert [s["tier"] for s in m["stints"]] == ["top9", "domestic"]
    # minutes-weighted, not a plain mean: (0.0*600 + 0.3*1200)/1800 + ast 0.05
    assert m["q"] == pytest.approx(0.2 + 0.05)
    # per-90 role totals are pooled over both stints: 15 crosses in 1800 minutes
    assert m["crs_p90"] == pytest.approx(15 / 1800 * 90)


def test_rank_is_within_the_position_group():
    rows = {r["player_key"]: r for r in build_rows(_feats(), _roles(), "2025-2026", HEADLINE, STEPPING, DOMESTIC)}
    assert rows["jan novak|2000"]["rank_q"] == 1 and rows["jan novak|2000"]["n_group"] == 1
    assert rows["petr mover|1999"]["rank_q"] == 1 and rows["petr mover|1999"]["n_group"] == 2
    assert rows["karel druhy|1995"]["rank_q"] == 2


def test_build_rows_without_roles_still_emits_every_player():
    rows = {r["player_key"]: r for r in build_rows(_feats(), None, "2025-2026", HEADLINE, STEPPING, DOMESTIC)}
    n = rows["jan novak|2000"]
    assert n["starts"] is None and n["subs"] is None and n["crs_p90"] is None
    assert n["min"] == 1800 and n["rank_q"] == 1


def test_keeper_rows_use_pool_eligibility_and_carry_a_tier():
    keepers = pd.DataFrame([
        {"league": DOMESTIC, "season": "2025-2026", "team": "Teplice", "player": "Matouš Trmal",
         "player_key": "matous trmal|1998", "born": 1998, "age": 26, "min": 1800, "ga": 24, "saves": 60,
         "sota": 84, "save_pct": 71.4, "cs": 6},
        {"league": "NED-Eredivisie", "season": "2025-2026", "team": "PSV", "player": "Foreign Keeper",
         "player_key": "foreign keeper|1997", "born": 1997, "age": 28, "min": 1800, "ga": 20, "saves": 50,
         "sota": 70, "save_pct": 71.4, "cs": 8},
    ])
    pool = pd.DataFrame({"player_key": ["matous trmal|1998"]})
    rows = build_keeper_rows(keepers, pool, "2025-2026", HEADLINE, STEPPING, DOMESTIC)
    assert len(rows) == 1
    r = rows[0]
    assert r["pos_group"] == "GK" and r["tier"] == "domestic"
    assert r["ga_p90"] == pytest.approx(24 / 1800 * 90) and r["cs"] == 6


def test_profile_percentiles_rank_within_the_position_group():
    """SkillCorner-style benchmark: each axis is a percentile among every
    player-season of the position group above the inclusion floor, home or
    not, so a Czech midfielder is ranked against every midfielder covered."""
    from src.pool_table import _profile_frame, percentiles
    base = {"season": "2025-2026", "home_eligible": False, "nt_flag": False,
            "npg_p90_quality": 0.1, "ast_p90_quality": 0.0, "npg_p90": 0.1, "ast_p90": 0.0}
    rows = []
    for i in range(12):   # twelve midfielders, output rising with i; the last one is home-eligible
        rows.append(base | {"league": "X", "team": f"T{i}", "player": f"P{i}", "player_key": f"p{i}|2000",
                            "pos_group": "MF", "born": 2000, "age": 25, "min": 900, "min_share": 0.5,
                            "npg_p90_quality": 0.05 * i, "home_eligible": i == 11})
    rows.append(base | {"league": "X", "team": "T", "player": "Cameo", "player_key": "cameo|2005", "pos_group": "MF",
                        "born": 2005, "age": 20, "min": 30, "min_share": 0.02, "npg_p90_quality": 9.0})   # under the floor
    feats = pd.DataFrame(rows)
    pcts = percentiles(_profile_frame(feats, None, "2025-2026"))
    assert pcts[("p11|2000", "MF")]["q"] == 100          # best of the twelve
    assert pcts[("p0|2000", "MF")]["q"] == 8               # 1/12 -> 8th percentile
    assert ("cameo|2005", "MF") not in pcts                # 30 minutes do not rank
    # starts-based axes are absent without the roles table
    assert "starts_share" not in pcts[("p11|2000", "MF")]
