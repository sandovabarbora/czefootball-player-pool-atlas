"""Season tables for the history years of the non-headline leagues.

`src.fetch_fbref` fetches the history seasons (config/seasons.yaml::history)
for the nine headline leagues only, which is what the analog corpus needs.
The atlas's career view wants every pool player's seasons back to the same
year wherever he played, so this fetches the same history seasons for the
domestic league, the peer domestic leagues and the stepping-stone leagues
into a separate table, data/processed/<nation>/fbref_history.parquet.

Kept separate on purpose: `fbref_players.parquet` feeds the feature
tables, whose shrinkage priors are fitted on the corpus, so adding rows to
it would move every quality-adjusted number in the report. This table is
read by `src.careers_export` only.
"""

from __future__ import annotations

import logging

import pandas as pd

from src import config, leagues_setup
from src.fetch_fbref import fetch_league
from src.utils import write_parquet

LOG = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    leagues_setup.install()
    cfg, seasons = config.leagues(), config.seasons()
    headline = set(cfg["headline"])
    leagues = [lg for lg in dict.fromkeys([cfg["domestic"], *cfg["custom"], *cfg.get("peer_domestic", {})])
               if lg not in headline]
    out_path = config.PROCESSED_DIR / "fbref_history.parquet"
    done = pd.read_parquet(out_path) if out_path.exists() else pd.DataFrame()
    have = set(zip(done["league"], done["season"])) if len(done) else set()
    frames = [done] if len(done) else []
    for league in leagues:
        for season in seasons.get("history", []):
            if (league, season) in have:
                continue
            try:
                frames.append(fetch_league(league, season))
                LOG.info("%s %s: %d rows", league, season, len(frames[-1]))
            except Exception as exc:   # one league failing must not kill the run
                LOG.warning("%s %s failed: %s", league, season, exc)
            if frames:   # the first page can fail (Norway's 2020: FBref serves a mislabelled page) -- nothing to checkpoint yet
                write_parquet(pd.concat(frames, ignore_index=True), out_path)   # checkpoint after every page
    LOG.info("history table: %d rows", sum(len(f) for f in frames))


if __name__ == "__main__":
    main()
