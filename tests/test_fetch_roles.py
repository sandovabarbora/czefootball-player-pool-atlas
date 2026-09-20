from pathlib import Path

import pytest

from src.fetch_fbref import parse_player_page
from src.fetch_roles import KEYS, MISC, PLAYING_TIME, _block

FIX = Path(__file__).parent / "fixtures"


def _parsed(stat: str):
    return parse_player_page((FIX / f"fbref_{stat}_cze_2526.html").read_text(encoding="utf-8"),
                             "CZE-First League", "2025-2026", stat)


def test_parse_finds_the_playing_time_and_misc_tables():
    # stat-type-generic: the same reader used for "standard"/"keeper" finds
    # div_stats_playing_time and div_stats_misc on their own pages.
    pt, ms = _parsed("playing_time"), _parsed("misc")
    assert len(pt) == 3 and len(ms) == 3
    assert ("Starts", "Starts") in pt.columns and ("Subs", "unSub") in pt.columns
    assert ("Team Success", "On-Off") in pt.columns
    assert ("Performance", "Crs") in ms.columns and ("Performance", "Int") in ms.columns


def test_playing_time_block_keeps_the_start_and_substitute_split():
    out = _block(_parsed("playing_time"), PLAYING_TIME, "CZE-First League", "2025-2026")
    assert list(out.columns) == KEYS + list(PLAYING_TIME)
    zika = out[out.player_key == "jan zika|2006"].iloc[0]
    # the column the youth mechanism needs: a part-season player who both
    # starts and comes on, so `starts` is not a restatement of `min`
    assert zika.starts == 14 and zika.subs == 9
    assert zika.compl == 10 and zika.mn_per_start == 85
    cermak = out[out.player_key == "marcel cermak|1998"].iloc[0]
    assert cermak.starts == 34 and cermak.subs == 0


def test_misc_block_maps_the_performance_columns():
    out = _block(_parsed("misc"), MISC, "CZE-First League", "2025-2026")
    assert list(out.columns) == KEYS + list(MISC)
    row = out[out.player_key == "marcel cermak|1998"].iloc[0]
    # a wide midfielder's role signature: crosses far above the defensive volume
    assert row.crs == 153 and row.interceptions == 12 and row.tklw == 18


def test_a_renamed_fbref_column_fails_loudly():
    # a silent rename must not produce an all-NaN column that only surfaces
    # in a figure; `_block` raises at fetch time instead.
    with pytest.raises(KeyError, match="Starts.*Appearances|no .* column"):
        _block(_parsed("playing_time"), {"starts": ("Starts", "Appearances")},
               "CZE-First League", "2025-2026")


def test_blocks_join_on_the_player_keys():
    pt = _block(_parsed("playing_time"), PLAYING_TIME, "CZE-First League", "2025-2026")
    ms = _block(_parsed("misc"), MISC, "CZE-First League", "2025-2026")
    merged = pt.merge(ms, on=KEYS, how="outer")
    assert len(merged) == 3
    assert merged[["starts", "crs"]].notna().all().all()
