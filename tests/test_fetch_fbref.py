import pandas as pd

from src.fetch_fbref import normalize_player_table
from src.utils import normalize_name, player_key


def _soccerdata_like():
    cols = pd.MultiIndex.from_tuples([
        ("nation", ""), ("pos", ""), ("age", ""), ("born", ""),
        ("Playing Time", "MP"), ("Playing Time", "Min"),
        ("Performance", "Gls"), ("Performance", "Ast"), ("Performance", "PK"),
        ("Performance", "CrdY"), ("Performance", "CrdR"),
    ])
    idx = pd.MultiIndex.from_tuples(
        [("ENG-Premier League", "2425", "West Ham", "Tomáš Souček"),
         ("ENG-Premier League", "2425", "Arsenal", "Bukayo Saka")],
        names=["league", "season", "team", "player"])
    data = [["cz CZE", "MF", "29-200", 1995, 38, 3200, 5, 2, 0, 6, 0],
            ["eng ENG", "FW,MF", "23-100", 2001, 35, 2900, 12, 10, 1, 2, 0]]
    return pd.DataFrame(data, index=idx, columns=cols)


def test_normalize_flattens_and_types():
    out = normalize_player_table(_soccerdata_like(), "ENG-Premier League", "2024-2025")
    assert list(out.columns) == ["league", "season", "team", "player", "player_key", "nation",
                                 "pos", "born", "age", "mp", "min", "gls", "ast", "pk", "crdy", "crdr"]
    row = out[out.player == "Tomáš Souček"].iloc[0]
    assert row.nation == "CZE" and row.pos == "MF" and row.born == 1995 and row["min"] == 3200
    assert row.player_key == "tomas soucek|1995"
    assert out.season.unique().tolist() == ["2024-2025"]


def test_pos_takes_first_token():
    out = normalize_player_table(_soccerdata_like(), "ENG-Premier League", "2024-2025")
    assert out[out.player == "Bukayo Saka"].iloc[0].pos == "FW"


def _soccerdata_like_with_missing_nation_and_pos():
    cols = pd.MultiIndex.from_tuples([
        ("nation", ""), ("pos", ""), ("age", ""), ("born", ""),
        ("Playing Time", "MP"), ("Playing Time", "Min"),
        ("Performance", "Gls"), ("Performance", "Ast"), ("Performance", "PK"),
        ("Performance", "CrdY"), ("Performance", "CrdR"),
    ])
    idx = pd.MultiIndex.from_tuples(
        [("ENG-Premier League", "2425", "West Ham", "Unknown Player")],
        names=["league", "season", "team", "player"])
    data = [[float("nan"), float("nan"), "23-100", 2001, 10, 900, 0, 0, 0, 0, 0]]
    return pd.DataFrame(data, index=idx, columns=cols)


def test_missing_nation_and_pos_become_empty_string_not_the_literal_nan():
    out = normalize_player_table(
        _soccerdata_like_with_missing_nation_and_pos(), "ENG-Premier League", "2024-2025")
    row = out.iloc[0]
    assert row.nation == ""
    assert row.pos == ""
    assert row.player_key == "unknown player|2001"


def test_normalize_name_strips_diacritics_lowercases_and_collapses_whitespace():
    assert normalize_name("Tomáš   Souček") == "tomas soucek"
    assert normalize_name("Bukayo Saka") == "bukayo saka"


def test_player_key_uses_normalized_name_and_int_born():
    assert player_key("Tomáš Souček", 1995) == "tomas soucek|1995"
    assert player_key("Tomáš Souček", 1995.0) == "tomas soucek|1995"


def test_player_key_uses_x_when_born_missing():
    assert player_key("Bukayo Saka", None) == "bukayo saka|x"
    assert player_key("Bukayo Saka", float("nan")) == "bukayo saka|x"


# --- page-level reader: season guard + tolerance to a finished season's table ---
from pathlib import Path

import pytest

from src.fetch_fbref import SeasonMismatch, page_season, parse_player_page

FIX = Path(__file__).parent / "fixtures" / "fbref_players_pol_2526_standard.html"


def test_page_season_reads_the_h1():
    assert page_season(FIX.read_text(encoding="utf-8")) == "2025-2026"


def test_parse_player_page_without_matches_column():
    # a finished season's FBref table has no "Matches" link column; soccerdata's
    # reader raises KeyError on it, ours must not
    out = parse_player_page(FIX.read_text(encoding="utf-8"), "POL-Ekstraklasa", "2025-2026", "standard")
    assert len(out) == 3
    assert out.index.get_level_values("season").unique().tolist() == ["2025-2026"]
    assert "Abbati Abdullahi" in out.index.get_level_values("player")  # sorted by team
    flat = normalize_player_table(out, "POL-Ekstraklasa", "2025-2026")
    assert list(flat.columns) == ["league", "season", "team", "player", "player_key", "nation",
                                  "pos", "born", "age", "mp", "min", "gls", "ast", "pk", "crdy", "crdr"]
    assert flat["min"].gt(0).any() and flat.born.notna().all()


def test_parse_player_page_rejects_wrong_season():
    with pytest.raises(SeasonMismatch, match="2026-2027"):
        parse_player_page(FIX.read_text(encoding="utf-8"), "POL-Ekstraklasa", "2026-2027", "standard")


def test_season_page_url_uses_fbrefs_page_segment(monkeypatch):
    from src import fetch_fbref

    class _FB:
        def read_seasons(self):
            return pd.DataFrame({"url": ["/en/comps/9/Premier-League-Stats"]},
                                index=pd.MultiIndex.from_tuples([("ENG-Premier League", "2627")],
                                                                names=["league", "season"]))
    url = fetch_fbref._season_page_url(_FB(), "ENG-Premier League", "2026-2027", "standard")
    assert url.endswith("/en/comps/9/stats/Premier-League-Stats")
    assert fetch_fbref._season_page_url(_FB(), "ENG-Premier League", "2026-2027", "keeper").endswith(
        "/en/comps/9/keepers/Premier-League-Stats")


def test_parse_player_page_reports_squads_only_page():
    from src.fetch_fbref import MissingTable
    page = "<html><body><h1>2026-2027 NB I Stats</h1><table id='stats_squads_standard_for'></table></body></html>"
    with pytest.raises(MissingTable):
        parse_player_page(page, "HUN-NB I", "2026-2027", "standard")


def test_calendar_year_league_page_matches_the_start_year():
    from src.fetch_fbref import page_season
    page = "<html><body><h1>2025 Eliteserien Stats</h1><!-- <div id='div_stats_standard'></div> --></body></html>"
    assert page_season(page) == "2025"
    with pytest.raises(Exception, match="no player"):   # season accepted (start year), table missing
        parse_player_page(page, "NOR-Eliteserien", "2025-2026", "standard")
