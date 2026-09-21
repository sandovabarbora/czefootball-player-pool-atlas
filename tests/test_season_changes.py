"""Tests for src/season_changes.py -- where the pool moved in a year (Task 31)."""

from __future__ import annotations

import pandas as pd

from src.season_changes import classify, summarise

HEADLINE = ["ENG-Premier League", "GER-Bundesliga"]
STEPPING = ["NED-Eredivisie"]
DOMESTIC = "CZE-First League"
PREV, CURR = "2024-2025", "2025-2026"


def _row(key, season, league, minutes, team="X", eligible=True):
    return {"player_key": key, "player": key.split("|")[0].title(), "season": season, "league": league,
            "team": team, "min": minutes, "home_eligible": eligible}


def _feats():
    return pd.DataFrame([
        _row("up|2000", PREV, DOMESTIC, 2000), _row("up|2000", CURR, "GER-Bundesliga", 1500),
        _row("down|1995", PREV, "NED-Eredivisie", 1800), _row("down|1995", CURR, DOMESTIC, 1700),
        _row("lateral|1998", PREV, "ENG-Premier League", 1200), _row("lateral|1998", CURR, "GER-Bundesliga", 1100),
        _row("stay|1997", PREV, DOMESTIC, 900, team="Sparta"), _row("stay|1997", CURR, DOMESTIC, 950, team="Slavia"),
        _row("new|2006", CURR, DOMESTIC, 600),
        _row("gone|1990", PREV, DOMESTIC, 2500),
        # below the floor this season: counts as left, not as stayed
        _row("fringe|2003", PREV, DOMESTIC, 800), _row("fringe|2003", CURR, DOMESTIC, 120),
        # a mid-season mover whose lead league decides the tier: 1000 abroad beats 400 at home
        _row("split|1999", PREV, DOMESTIC, 1500),
        _row("split|1999", CURR, DOMESTIC, 400, team="Teplice"), _row("split|1999", CURR, "ENG-Premier League", 1000, team="Wolves"),
        _row("foreign|1996", PREV, DOMESTIC, 2000, eligible=False), _row("foreign|1996", CURR, DOMESTIC, 2000, eligible=False),
    ])


def test_classify_names_every_kind_of_move():
    m = classify(_feats(), PREV, CURR, 450, HEADLINE, STEPPING, DOMESTIC).set_index("player_key")
    assert m.loc["up|2000", "move"] == "up"
    assert m.loc["down|1995", "move"] == "down"
    assert m.loc["lateral|1998", "move"] == "lateral"
    assert m.loc["stay|1997", "move"] == "stayed"        # a change of club inside the league
    assert m.loc["new|2006", "move"] == "entered"
    assert m.loc["gone|1990", "move"] == "left"
    assert m.loc["fringe|2003", "move"] == "left"        # 120 minutes is under the floor
    assert "foreign|1996" not in m.index


def test_lead_league_decides_the_tier_for_a_mid_season_mover():
    m = classify(_feats(), PREV, CURR, 450, HEADLINE, STEPPING, DOMESTIC).set_index("player_key")
    s = m.loc["split|1999"]
    assert s.league_curr == "ENG-Premier League" and s.tier_curr == "top9" and s.move == "up"
    assert s.min_curr == 1000   # the lead stint's minutes, not the season's total


def test_summarise_counts_and_minutes_by_tier():
    m = classify(_feats(), PREV, CURR, 450, HEADLINE, STEPPING, DOMESTIC)
    out = summarise(m, names_per_move=2)
    assert {k: v["n"] for k, v in out["moves"].items()} == {
        "up": 2, "down": 1, "lateral": 1, "stayed": 1, "entered": 1, "left": 2}
    # names are the top few by this season's minutes (last season's for `left`)
    assert [n["player"] for n in out["moves"]["left"]["names"]] == ["Gone", "Fringe"]
    assert len(out["moves"]["up"]["names"]) == 2
    dom = out["minutes_by_tier"]["domestic"]
    # last season at home: up, stay, gone, fringe, split; this season: stay, new, down
    assert dom["players_prev"] == 5 and dom["players_curr"] == 3
    assert dom["prev"] == 2000 + 900 + 2500 + 800 + 1500 and dom["curr"] == 950 + 600 + 1700
    assert out["n_prev"] == 7 and out["n_curr"] == 6
