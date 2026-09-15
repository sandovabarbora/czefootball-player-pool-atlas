# Task 13a: The 26-season Big-5 series (module + figure), data already fetched

**Spec:** `docs/superpowers/specs/2026-09-14-why-the-train-leaves-design.md` §2 M4 (exhibit only — the break model comes later).

**Data:** `data/processed/big5_history.parquet` — 70 544 rows, columns as
`fbref_players.parquet` (`league, season, team, player, player_key, nation, pos, born,
age, mp, min, gls, ast, pk, crdy, crdr`), leagues ENG/ITA/ESP/GER/FRA, seasons
2000-2001 … 2025-2026 (26). Fetcher: `src/fetch_big5_history.py` (exists; Makefile
target `fetch-big5` to add: `$(ACT) python -m src.fetch_big5_history`).

**Files:** create `src/big5_series.py`, `tests/test_big5_series.py`; modify `Makefile`
(`fetch-big5`, `series: $(ACT) python -m src.big5_series`, add `series` to `all` before
`render`); `src/render.py` `load_data` reads `big5_series.json` (empty dict tolerated).

## Interface
`build_series(history: pd.DataFrame, peers: dict[str, dict], min_minutes: int = 450) -> dict`
returns
```python
{"seasons": ["2000-2001", …],
 "countries": {"CZE": {"n": [21, 23, …], "per_million": [1.93, …], "minutes_share": [0.0123, …]}, "DEN": {…}, …},
 "cze_peak": {"season": "2002-2003", "n": 32},
 "cze_low":  {"season": "2014-2015", "n": 12},
 "golden": [{"season": "2002-2003", "players": ["Pavel Nedvěd", "Karel Poborský", "Tomáš Rosický"]}, …]}
```
- `n` = distinct `player_key` with `min >= min_minutes` in that season across the five
  leagues, per peer nation (peers = `config.countries()["peers"]`, populations for
  `per_million`); `minutes_share` = the nation's minutes ÷ all minutes that season.
- `golden`: for each of the three seasons with the highest Czech `n`, the three Czech
  players with the most minutes — **computed, never typed**; the report may name them
  because the data does.
- `cze_peak` / `cze_low` = argmax / argmin of the Czech `n` (ties → earliest).

`render_series(series: dict, out_path: Path) -> None` — one matplotlib SVG
(`outputs/big5_series.svg`): Czech `n` as a thick navy line with the peak, the low and
the last season annotated (season label + count), the eight peers as thin grey lines
(DEN and CRO in a mid tone, labelled at the right edge), x = season start year, y =
players. Palette/typography from `src/international_benchmark.py` constants
(`NAVY`, `OXBLOOD`, `CREAM`, `INK`, serif title). A second panel below (shared x):
`per_million` for CZE vs DEN vs CRO. Title "Czech players in the Big-5 leagues,
{first} → {last}" (computed labels). `main()` writes `data/processed/big5_series.json`
and the SVG; log the peak/low/last.

## Tests (write first)
```python
import pandas as pd
from src.big5_series import build_series

PEERS = {"CZE": {"name": "Czechia", "population_m": 10.0}, "DEN": {"name": "Denmark", "population_m": 5.0}}

def _hist():
    rows = []
    for season, cz, dk in [("2000-2001", 3, 1), ("2001-2002", 2, 2), ("2002-2003", 1, 2)]:
        for i in range(cz):
            rows.append({"season": season, "nation": "CZE", "player_key": f"c{i}", "player": f"Czech {i}", "min": 900 + i, "league": "ENG-Premier League"})
        for i in range(dk):
            rows.append({"season": season, "nation": "DEN", "player_key": f"d{i}", "player": f"Dane {i}", "min": 900, "league": "ENG-Premier League"})
        rows.append({"season": season, "nation": "CZE", "player_key": "cx", "player": "Sub", "min": 100, "league": "ENG-Premier League"})  # below the floor
    return pd.DataFrame(rows)

def test_series_counts_players_above_the_floor_and_finds_peak_and_low():
    s = build_series(_hist(), PEERS)
    assert s["seasons"] == ["2000-2001", "2001-2002", "2002-2003"]
    assert s["countries"]["CZE"]["n"] == [3, 2, 1] and s["countries"]["DEN"]["n"] == [1, 2, 2]
    assert s["countries"]["CZE"]["per_million"][0] == 0.3
    assert s["cze_peak"] == {"season": "2000-2001", "n": 3} and s["cze_low"] == {"season": "2002-2003", "n": 1}
    assert s["golden"][0]["season"] == "2000-2001" and s["golden"][0]["players"][0] == "Czech 2"
```
Plus a smoke test that `render_series` writes an SVG for the fixture (tmp_path).

## Verify
`uv run pytest -q`; `uv run python -m src.big5_series` on the real parquet → log shows
peak 2002-2003 (32), low 2014-2015 (12), last 2025-2026 (14) (from the fetched data —
report what you get); `outputs/big5_series.svg` exists. Commit plain message, no AI
trailer; add src/tests/Makefile only.
