from pathlib import Path

from src.fetch_squads import normalize_name, parse_squad_section

FIX = Path(__file__).parent / "fixtures" / "wiki_squad_euro2024.html"


def test_normalize_name():
    assert normalize_name("Tomáš  Souček") == "tomas soucek"


def test_parse_czech_euro2024_squad():
    df = parse_squad_section(FIX.read_text(encoding="utf-8"), section="Czech Republic")
    assert 23 <= len(df) <= 26
    assert (df.player_norm == "patrik schick").any()
    assert df.born.between(1985, 2006).all()
