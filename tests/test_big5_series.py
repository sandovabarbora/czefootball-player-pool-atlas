"""Tests for src/big5_series.py — the 26-season Big-5 series (M4 exhibit)."""

from __future__ import annotations

import pandas as pd

from src import config
from src.big5_series import build_series, render_series

# `build_series` reads the home country off `config.HOME` (nation-aware:
# "CZE" under NATION=cze, "ENG" under NATION=eng, ...); the fixture's "home"
# nation code (and its rows in `_hist()`) is keyed on it too, rather than
# hardcoded "CZE", so this test passes regardless of NATION. The returned
# dict's own "cze_peak"/"cze_low" keys are literal in `build_series` itself
# (not nation-parameterized) and stay that way here.
HOME = config.HOME
PEERS = {HOME: {"name": "Home", "population_m": 10.0}, "DEN": {"name": "Denmark", "population_m": 5.0}}


def _hist():
    rows = []
    for season, cz, dk in [("2000-2001", 3, 1), ("2001-2002", 2, 2), ("2002-2003", 1, 2)]:
        for i in range(cz):
            rows.append({"season": season, "nation": HOME, "player_key": f"c{i}", "player": f"Home {i}", "min": 900 + i, "league": "ENG-Premier League"})
        for i in range(dk):
            rows.append({"season": season, "nation": "DEN", "player_key": f"d{i}", "player": f"Dane {i}", "min": 900, "league": "ENG-Premier League"})
        rows.append({"season": season, "nation": HOME, "player_key": "cx", "player": "Sub", "min": 100, "league": "ENG-Premier League"})  # below the floor
    return pd.DataFrame(rows)


def test_series_counts_players_above_the_floor_and_finds_peak_and_low():
    s = build_series(_hist(), PEERS)
    assert s["seasons"] == ["2000-2001", "2001-2002", "2002-2003"]
    assert s["countries"][HOME]["n"] == [3, 2, 1] and s["countries"]["DEN"]["n"] == [1, 2, 2]
    assert s["countries"][HOME]["per_million"][0] == 0.3
    assert s["cze_peak"] == {"season": "2000-2001", "n": 3} and s["cze_low"] == {"season": "2002-2003", "n": 1}
    assert s["golden"][0]["season"] == "2000-2001" and s["golden"][0]["players"][0] == "Home 2"


def test_render_series_writes_svg(tmp_path):
    s = build_series(_hist(), PEERS)
    out_path = tmp_path / "big5_series.svg"
    render_series(s, out_path)
    assert out_path.exists()
    assert out_path.read_text(encoding="utf-8").startswith("<?xml") or "<svg" in out_path.read_text(encoding="utf-8")
