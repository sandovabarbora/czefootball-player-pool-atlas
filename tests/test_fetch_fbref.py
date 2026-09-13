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


def test_normalize_name_strips_diacritics_lowercases_and_collapses_whitespace():
    assert normalize_name("Tomáš   Souček") == "tomas soucek"
    assert normalize_name("Bukayo Saka") == "bukayo saka"


def test_player_key_uses_normalized_name_and_int_born():
    assert player_key("Tomáš Souček", 1995) == "tomas soucek|1995"
    assert player_key("Tomáš Souček", 1995.0) == "tomas soucek|1995"


def test_player_key_uses_x_when_born_missing():
    assert player_key("Bukayo Saka", None) == "bukayo saka|x"
    assert player_key("Bukayo Saka", float("nan")) == "bukayo saka|x"
