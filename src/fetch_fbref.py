"""Player season tables from FBref via soccerdata, normalised to a flat frame.

Output: data/processed/fbref_players.parquet (one row per player-team-season).
Raw HTML is cached by soccerdata itself under ~/soccerdata/data/FBref.
"""
from __future__ import annotations

import logging

import pandas as pd
import soccerdata as sd

from src import config, leagues_setup
from src.utils import player_key, write_parquet

LOG = logging.getLogger(__name__)
COLS = ["league", "season", "team", "player", "player_key", "nation", "pos", "born", "age",
        "mp", "min", "gls", "ast", "pk", "crdy", "crdr"]


def _col(df: pd.DataFrame, *names: tuple) -> pd.Series:
    for n in names:
        if n in df.columns:
            return df[n]
    raise KeyError(names)


def normalize_player_table(df: pd.DataFrame, league: str, season: str) -> pd.DataFrame:
    idx = df.index.to_frame(index=False)
    out = pd.DataFrame({
        "league": league,
        "season": season,
        "team": idx["team"].values,
        "player": idx["player"].values,
        "nation": _col(df, ("nation", "")).fillna("").astype(str).str.split().str[-1].fillna("").values,
        "pos": _col(df, ("pos", "")).fillna("").astype(str).str.split(",").str[0].fillna("").values,
        "born": pd.to_numeric(_col(df, ("born", "")), errors="coerce").astype("Int64").values,
        "age": pd.to_numeric(_col(df, ("age", "")).astype(str).str.split("-").str[0], errors="coerce").astype("Int64").values,
        "mp": pd.to_numeric(_col(df, ("Playing Time", "MP")), errors="coerce").fillna(0).astype(int).values,
        "min": pd.to_numeric(_col(df, ("Playing Time", "Min")), errors="coerce").fillna(0).astype(int).values,
        "gls": pd.to_numeric(_col(df, ("Performance", "Gls")), errors="coerce").fillna(0).astype(int).values,
        "ast": pd.to_numeric(_col(df, ("Performance", "Ast")), errors="coerce").fillna(0).astype(int).values,
        "pk": pd.to_numeric(_col(df, ("Performance", "PK")), errors="coerce").fillna(0).astype(int).values,
        "crdy": pd.to_numeric(_col(df, ("Performance", "CrdY")), errors="coerce").fillna(0).astype(int).values,
        "crdr": pd.to_numeric(_col(df, ("Performance", "CrdR")), errors="coerce").fillna(0).astype(int).values,
    })
    out["player_key"] = [player_key(n, b) for n, b in zip(out["player"], out["born"], strict=True)]
    return out[COLS]


def fetch_league(league: str, season: str) -> pd.DataFrame:
    fb = sd.FBref(leagues=[league], seasons=[season])
    raw = fb.read_player_season_stats(stat_type="standard")
    return normalize_player_table(raw, league, season)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    leagues_setup.install()
    cfg, seasons = config.leagues(), config.seasons()
    leagues = list(dict.fromkeys(cfg["headline"] + [cfg["domestic"]] + list(cfg["custom"]) + list(cfg.get("peer_domestic", {}))))
    frames = []
    for league in leagues:
        for season in (seasons["previous"], seasons["metrics"], seasons["current"]):
            try:
                frames.append(fetch_league(league, season))
                LOG.info("%s %s: %d rows", league, season, len(frames[-1]))
            except Exception as exc:  # one league failing must not kill the run
                LOG.warning("%s %s failed: %s", league, season, exc)
    # Analog corpus depth: extra seasons for the nine headline leagues only
    # (keeps the extra fetch volume to headline_leagues * history_seasons calls).
    for league in cfg["headline"]:
        for season in seasons.get("history", []):
            try:
                frames.append(fetch_league(league, season))
                LOG.info("%s %s: %d rows", league, season, len(frames[-1]))
            except Exception as exc:  # one league failing must not kill the run
                LOG.warning("%s %s failed: %s", league, season, exc)
    write_parquet(pd.concat(frames, ignore_index=True), config.PROCESSED_DIR / "fbref_players.parquet")


if __name__ == "__main__":
    main()
