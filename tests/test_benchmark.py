"""Tests for src/international_benchmark.py — per-capita benchmark and
cohort gaps for the peer countries."""

from __future__ import annotations

import pandas as pd

from src import config
from src.international_benchmark import assign_cohort, build_narrative, cohort_table, per_capita


def test_per_capita_counts_distinct_players_in_headline_leagues():
    tables = pd.DataFrame({
        "player_key": ["a", "a", "b", "c", "d"], "nation": ["CZE", "CZE", "CZE", "DEN", "CZE"],
        "league": ["ENG-Premier League", "GER-Bundesliga", "ITA-Serie A", "ENG-Premier League", "CZE-First League"],
        "season": ["2025-2026"] * 5})
    peers = {"CZE": {"name": "Czechia", "population_m": 10.0}, "DEN": {"name": "Denmark", "population_m": 5.0}}
    out = per_capita(tables, peers, ["ENG-Premier League", "GER-Bundesliga", "ITA-Serie A"], "2025-2026")
    cze = out[out.country == "CZE"].iloc[0]
    assert cze.n_players == 2 and abs(cze.per_million - 0.2) < 1e-9
    assert out.sort_values("rank").iloc[0].country == "DEN"


def test_assign_cohort():
    assert assign_cohort(2004, "2024-2025") == "U22"
    assert assign_cohort(1994, "2024-2025") == "30+"


def test_cohort_table_median_and_n(monkeypatch):
    import src.international_benchmark as ib

    monkeypatch.setattr(ib.config, "seasons", lambda: {"metrics": "2024-2025"})
    monkeypatch.setattr(ib.config, "HEADLINE_LEAGUES", ["ENG-Premier League"])
    monkeypatch.setattr(ib.config, "features", lambda: {"min_minutes": 450})

    fw = pd.DataFrame({
        "player_key": ["p1", "p2", "p3", "p4"],
        "nation": ["CZE", "CZE", "DEN", "DEN"],
        "league": ["ENG-Premier League"] * 4,
        "season": ["2024-2025"] * 4,
        "born": [2003, 2003, 1994, 1994],
        "min": [1000, 1000, 1000, 1000],
        "npg_p90_quality": [0.2, 0.4, 0.1, 0.3],
        "ast_p90_quality": [0.1, 0.1, 0.2, 0.2],
    })
    peers = {"CZE": {"name": "Czechia", "population_m": 10.0}, "DEN": {"name": "Denmark", "population_m": 5.0}}
    out = cohort_table({"FW": fw}, peers)

    cze_row = out[(out.country == "CZE") & (out.pos_group == "FW")].iloc[0]
    assert cze_row.cohort == "U22"
    assert cze_row.n == 2
    assert abs(cze_row.median_npg_ast_p90 - 0.4) < 1e-9

    den_row = out[(out.country == "DEN") & (out.pos_group == "FW")].iloc[0]
    assert den_row.cohort == "30+"
    assert den_row.n == 2


def test_cohort_table_excludes_below_min_minutes(monkeypatch):
    import src.international_benchmark as ib

    monkeypatch.setattr(ib.config, "seasons", lambda: {"metrics": "2024-2025"})
    monkeypatch.setattr(ib.config, "HEADLINE_LEAGUES", ["ENG-Premier League"])
    monkeypatch.setattr(ib.config, "features", lambda: {"min_minutes": 450})

    fw = pd.DataFrame({
        "player_key": ["p1"],
        "nation": ["CZE"],
        "league": ["ENG-Premier League"],
        "season": ["2024-2025"],
        "born": [2003],
        "min": [100],
        "npg_p90_quality": [0.2],
        "ast_p90_quality": [0.1],
    })
    peers = {"CZE": {"name": "Czechia", "population_m": 10.0}}
    out = cohort_table({"FW": fw}, peers)
    assert out.empty


def test_build_narrative_zero_fills_absent_peers_in_cohort_median():
    # Three peers: the home nation, DEN, POL. In the FW/U22 cohort, POL has
    # no qualifying players at all (no row in `coh`) — the median over the
    # non-home peers (DEN, POL) must treat POL as n=0, not exclude it.
    # `build_narrative` reads the home country off `config.HOME` (nation-
    # aware: "CZE" under NATION=cze, "ENG" under NATION=eng, ...), so the
    # fixture's "home" row is keyed on it too rather than hardcoded "CZE".
    home = config.HOME
    peer = "DEN" if home != "DEN" else "NOR"   # the fixture's first peer must not be the home nation (NATION=den runs this too)
    pc = pd.DataFrame({
        "country": [home, peer, "POL"],
        "name": ["Home", "Denmark", "Poland"],
        "n_players": [2, 4, 0],
        "population_m": [10.0, 5.0, 36.0],
        "per_million": [0.2, 0.8, 0.0],
        "rank": [2, 1, 3],
    })
    coh = pd.DataFrame({
        "country": [home, peer],
        "pos_group": ["FW", "FW"],
        "cohort": ["U22", "U22"],
        "n": [2, 4],
        "median_npg_ast_p90": [0.3, 0.5],
    })
    narrative = build_narrative(pc, coh)
    # median([DEN=4, POL=0]) == 2.0, not median([DEN=4]) == 4.0
    assert "| Forwards | U22 | 2 | 2.0 | 0.0 |" in narrative
