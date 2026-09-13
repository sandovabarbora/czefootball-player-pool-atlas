from pathlib import Path

from src.pool import is_feminine_surname, parse_country_page, pick_born, pos_group

FIX = Path(__file__).parent / "fixtures" / "fbref_country_cze.html"


def test_country_page_yields_players_with_ids_and_activity():
    df = parse_country_page(FIX.read_text(encoding="utf-8"), current_start_year=2025)
    assert len(df) > 1500                      # all-time list
    assert df.fbref_id.str.len().eq(8).all()
    schick = df[df.player == "Patrik Schick"].iloc[0]
    assert schick.active and schick.pos == "FW" and schick.clubs[0] == "Leverkusen"
    assert not df[df.player == "Martin Abraham"].iloc[0].active
    assert df.active.sum() > 150


def test_pos_group_mapping():
    assert pos_group("FW,MF") == "FW"
    assert pos_group("DF") == "DF"
    assert pos_group("GK") is None


def test_country_page_drops_womens_entries_by_ova_suffix():
    df = parse_country_page(FIX.read_text(encoding="utf-8"), current_start_year=2025)
    assert not df.player.str.split().str[-1].str.lower().str.endswith("ová").any()


def test_is_feminine_surname():
    assert is_feminine_surname("Kateřina Svitková") is True
    assert is_feminine_surname("Patrik Schick") is False
    assert is_feminine_surname("Adam Hložek") is False


def test_pick_born_matches_by_current_club():
    candidates = [(1992, "Teplice"), (1999, "Girona")]
    assert pick_born(candidates, ["Teplice", "Sparta Prague"]) == 1992
    assert pick_born(candidates, ["Wolverhampton Wanderers", "Girona"]) == 1999


def test_pick_born_falls_back_to_first_when_no_club_matches():
    candidates = [(1992, "Teplice"), (1999, "Girona")]
    assert pick_born(candidates, ["Unknown Club"]) == 1992


def test_pick_born_no_candidates_returns_none():
    assert pick_born([], ["Teplice"]) is None
