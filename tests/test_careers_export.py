"""src.careers_export: every pool player's seasons for the player atlas."""

from __future__ import annotations

import pandas as pd

from src.careers_export import careers, seasons_table

CFG = {"headline": ["ENG-Premier League", "GER-Bundesliga"], "stepping_stone": ["GER-2. Bundesliga"]}
MULT = {"ENG-Premier League": 1.0, "GER-Bundesliga": 0.9, "CZE-First League": 0.5, "GER-2. Bundesliga": 0.6}


def _row(season, league, team, key, min_, gls=0, ast=0, pk=0, pos="FW", born=2000):
    return {"league": league, "season": season, "team": team, "player": key.split("|")[0].title(), "player_key": key,
            "nation": "CZE", "pos": pos, "born": born, "age": int(season[:4]) - born, "mp": max(1, min_ // 90),
            "min": min_, "gls": gls, "ast": ast, "pk": pk, "crdy": 0, "crdr": 0}


def _fixture():
    players = pd.DataFrame([
        _row("2024-2025", "CZE-First League", "Slavia", "jan novak|2000", 1800, gls=10, ast=2, pk=2),
        _row("2025-2026", "GER-Bundesliga", "Leverkusen", "jan novak|2000", 900, gls=5, ast=0),
        _row("2025-2026", "GER-2. Bundesliga", "Hamburg", "jan novak|2000", 90, gls=1),   # a mid-season move
        _row("2025-2026", "CZE-First League", "Plzen", "petr gk|1998", 30, pos="GK", born=1998),
    ])
    history = pd.DataFrame([_row("2022-2023", "CZE-First League", "Slavia", "jan novak|2000", 400)])
    pool = pd.DataFrame([
        {"player_key": "jan novak|2000", "fbref_id": "aaaa", "player": "Jan Novák", "born": 2000, "pos_group": "FW", "club_current": "Leverkusen"},
        {"player_key": "petr gk|1998", "fbref_id": "bbbb", "player": "Petr Gk", "born": 1998, "pos_group": None, "club_current": "Plzen"},
        {"player_key": "nobody|1990", "fbref_id": "cccc", "player": "No Body", "born": 1990, "pos_group": "DF", "club_current": None},
    ])
    nt = pd.DataFrame([{"player_norm": "jan novak", "player": "Jan Novák", "born": 2000, "team": "A", "event": "UEFA Euro 2024", "year": 2024}])
    profiles = {"jan novak|2000": {"season": "2025-2026", "rank": 3, "n": 40, "axes": [], "q": 0.8, "min_share": 0.4}}
    return careers(seasons_table(players, history), pool, nt, MULT, {**CFG}, 450, profiles)


def test_seasons_are_unioned_ordered_and_tiered(monkeypatch):
    monkeypatch.setattr("src.careers_export.config.DOMESTIC_LEAGUE", "CZE-First League")
    out = {p["key"]: p for p in _fixture()}
    jan = out["jan novak|2000"]
    assert [s["season"] for s in jan["seasons"]] == ["2022-2023", "2024-2025", "2025-2026"]
    assert [s["tier"] for s in jan["seasons"]] == ["domestic", "domestic", "top9"]
    last = jan["seasons"][-1]
    assert last["min"] == 990 and last["team"] == "Leverkusen" and len(last["stints"]) == 2
    assert [st["tier"] for st in last["stints"]] == ["top9", "stepping_stone"]
    assert jan["seasons"][0]["under_floor"] and not jan["seasons"][1]["under_floor"]


def test_rates_are_non_penalty_per_90_times_the_league_multiplier(monkeypatch):
    monkeypatch.setattr("src.careers_export.config.DOMESTIC_LEAGUE", "CZE-First League")
    jan = {p["key"]: p for p in _fixture()}["jan novak|2000"]
    s2425 = jan["seasons"][1]["stints"][0]
    assert s2425["npg"] == 8 and s2425["ga90"] == round((8 + 2) / 20, 3) and s2425["ga90_adj"] == round(0.5 * 0.5, 3)


def test_call_ups_profile_and_missing_group(monkeypatch):
    monkeypatch.setattr("src.careers_export.config.DOMESTIC_LEAGUE", "CZE-First League")
    out = {p["key"]: p for p in _fixture()}
    assert out["jan novak|2000"]["calls"] == [{"event": "UEFA Euro 2024", "year": 2024, "team": "A"}]
    assert out["jan novak|2000"]["profile"]["rank"] == 3
    assert out["petr gk|1998"]["pos"] == "GK" and out["petr gk|1998"]["profile"] is None
    assert "nobody|1990" not in out, "a pool player with no season in a covered league has no entry"
