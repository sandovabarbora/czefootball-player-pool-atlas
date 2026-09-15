from pathlib import Path

from src.fetch_fbref import parse_player_page
from src.fetch_keepers import COLS, normalize_keeper_table

FIX = Path(__file__).parent / "fixtures" / "fbref_keepers_pol_2526.html"


def _parsed():
    return parse_player_page(FIX.read_text(encoding="utf-8"), "POL-Ekstraklasa", "2025-2026", "keeper")


def test_parse_player_page_finds_the_keeper_table():
    # stat-type-generic: the same reader used for "standard" finds
    # div_stats_keeper / stats_keeper on a keeper page.
    out = _parsed()
    assert len(out) == 3
    assert out.index.get_level_values("season").unique().tolist() == ["2025-2026"]
    assert ("Performance", "GA") in out.columns
    assert ("Performance", "SoTA") in out.columns
    assert ("Performance", "Saves") in out.columns
    assert ("Performance", "Save%") in out.columns
    assert ("Performance", "CS") in out.columns


def test_normalize_keeper_table_shape_and_types():
    out = normalize_keeper_table(_parsed(), "POL-Ekstraklasa", "2025-2026")
    assert list(out.columns) == COLS
    assert len(out) == 3
    assert out["league"].unique().tolist() == ["POL-Ekstraklasa"]
    assert out["season"].unique().tolist() == ["2025-2026"]
    assert out["min"].gt(0).all()


def test_normalize_keeper_table_maps_performance_block_correctly():
    out = normalize_keeper_table(_parsed(), "POL-Ekstraklasa", "2025-2026")
    row = out[out.player == "Jiří Borek"].iloc[0]
    assert row.nation == "CZE"
    assert row.team == "Slovácko"
    assert row.ga >= 0 and row.saves >= 0 and row.sota >= row.saves
    assert 0 <= row.save_pct <= 100
    assert row.cs >= 0
    assert row.player_key == "jiri borek|2002"


def test_normalize_keeper_table_handles_missing_nation():
    # the fixture's second row (Stepan Bachurek) has no nation cell on the
    # live page; nation must come through as "" not the literal "nan".
    out = normalize_keeper_table(_parsed(), "POL-Ekstraklasa", "2025-2026")
    row = out[out.player == "Stepan Bachurek"].iloc[0]
    assert row.nation == ""
    assert row.player_key == "stepan bachurek|2002"
