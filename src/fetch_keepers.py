"""Keeper season tables from FBref, normalised to a flat frame.

Output: data/processed/<NATION>/fbref_keepers.parquet (one row per
goalkeeper-team-season). Raw HTML is cached by soccerdata itself under
~/soccerdata/data/FBref -- the same cache `src.fetch_fbref` uses, keyed by
`(league, season, "keeper")`, so a keeper page already fetched for one
nation is reused for the other (`src.config.PROCESSED_DIR` is nation-scoped,
the FBref page cache is not).

`src.fetch_fbref.parse_player_page` is stat-type-generic (it looks for the
comment containing `div_stats_{stat_type}` and the table `stats_{stat_type}`)
so the keeper page ("keepers" URL segment, `stats_keeper` table) parses with
the exact same function used for the standard tables; only the column
mapping below is keeper-specific.

Column tuples on the live page (checked against a cached
`players_CZE-First League_2526_keeper.html`, see `tests/fixtures/
fbref_keepers_pol_2526.html` for a trimmed copy): the "Performance" block
carries GA, GA90, SoTA, Saves, Save%, W, D, L, CS, CS% -- this module keeps
GA, SoTA, Saves, Save%, CS (the brief's column list); GA90/W/D/L/CS% and the
"Penalty Kicks" block (which repeats a second "Save%") are dropped. Not
joined against `fbref_players.parquet` here -- `src.goalkeepers` does that
join (GK rows in the standard table already carry minutes/born/nation).
"""
from __future__ import annotations

import logging

import pandas as pd

from src import config, leagues_setup
from src.fetch_fbref import _col, fetch_player_page
from src.utils import player_key, write_parquet

LOG = logging.getLogger(__name__)
COLS = ["league", "season", "team", "player", "player_key", "nation", "born", "age",
        "mp", "min", "ga", "saves", "sota", "save_pct", "cs"]


def normalize_keeper_table(df: pd.DataFrame, league: str, season: str) -> pd.DataFrame:
    idx = df.index.to_frame(index=False)
    out = pd.DataFrame({
        "league": league,
        "season": season,
        "team": idx["team"].values,
        "player": idx["player"].values,
        "nation": _col(df, ("nation", "")).fillna("").astype(str).str.split().str[-1].fillna("").values,
        "born": pd.to_numeric(_col(df, ("born", "")), errors="coerce").astype("Int64").values,
        "age": pd.to_numeric(_col(df, ("age", "")).astype(str).str.split("-").str[0], errors="coerce").astype("Int64").values,
        "mp": pd.to_numeric(_col(df, ("Playing Time", "MP")), errors="coerce").fillna(0).astype(int).values,
        "min": pd.to_numeric(_col(df, ("Playing Time", "Min")), errors="coerce").fillna(0).astype(int).values,
        "ga": pd.to_numeric(_col(df, ("Performance", "GA")), errors="coerce").fillna(0).astype(int).values,
        "saves": pd.to_numeric(_col(df, ("Performance", "Saves")), errors="coerce").fillna(0).astype(int).values,
        "sota": pd.to_numeric(_col(df, ("Performance", "SoTA")), errors="coerce").fillna(0).astype(int).values,
        "save_pct": pd.to_numeric(_col(df, ("Performance", "Save%")), errors="coerce").astype(float).values,
        "cs": pd.to_numeric(_col(df, ("Performance", "CS")), errors="coerce").fillna(0).astype(int).values,
    })
    out["player_key"] = [player_key(n, b) for n, b in zip(out["player"], out["born"], strict=True)]
    return out[COLS]


def fetch_league_keepers(league: str, season: str) -> pd.DataFrame:
    return normalize_keeper_table(fetch_player_page(league, season, "keeper"), league, season)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    leagues_setup.install()
    cfg, seasons = config.leagues(), config.seasons()
    # Same league list as src.fetch_fbref.main, minus the extra history
    # seasons: the keeper corpus only needs previous/metrics/current.
    leagues = list(dict.fromkeys(cfg["headline"] + [cfg["domestic"]] + list(cfg["custom"]) + list(cfg.get("peer_domestic", {}))))
    frames = []
    for league in leagues:
        for season in (seasons["previous"], seasons["metrics"], seasons["current"]):
            try:
                frames.append(fetch_league_keepers(league, season))
                LOG.info("%s %s: %d keeper rows", league, season, len(frames[-1]))
            except Exception as exc:  # one league failing must not kill the run
                LOG.warning("%s %s failed: %s", league, season, exc)
    write_parquet(pd.concat(frames, ignore_index=True), config.PROCESSED_DIR / "fbref_keepers.parquet")


if __name__ == "__main__":
    main()
