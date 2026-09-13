from pathlib import Path

from src.pool import parse_country_page, pos_group

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
