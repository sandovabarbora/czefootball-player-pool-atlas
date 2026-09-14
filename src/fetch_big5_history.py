"""Big-5 player standard tables 2000/01 → metrics season, for the 26-season series (M4).

Output: data/processed/big5_history.parquet (same columns as fbref_players.parquet).
Pages are cached by soccerdata under ~/soccerdata/data/FBref; headless; one
league-season failing is logged and skipped so the run never dies mid-way.
"""
from __future__ import annotations

import logging

import pandas as pd

from src import config, leagues_setup
from src.fetch_fbref import fetch_league
from src.utils import write_parquet

LOG = logging.getLogger(__name__)
BIG5 = ["ENG-Premier League", "ITA-Serie A", "ESP-La Liga", "GER-Bundesliga", "FRA-Ligue 1"]
FIRST_SEASON = 2000


def seasons_until(metrics: str) -> list[str]:
    end = int(metrics[:4])
    return [f"{y}-{y + 1}" for y in range(FIRST_SEASON, end + 1)]


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    leagues_setup.install()
    frames = []
    for league in BIG5:
        for season in seasons_until(config.seasons()["metrics"]):
            try:
                frames.append(fetch_league(league, season))
                LOG.info("%s %s: %d rows", league, season, len(frames[-1]))
            except Exception as exc:  # noqa: BLE001 — one page must not kill 130
                LOG.warning("%s %s failed: %s", league, season, exc)
    write_parquet(pd.concat(frames, ignore_index=True), config.PROCESSED_DIR / "big5_history.parquet")


if __name__ == "__main__":
    main()
