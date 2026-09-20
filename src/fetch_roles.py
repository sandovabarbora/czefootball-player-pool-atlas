"""Fetch FBref's *playing time* and *miscellaneous* player tables.

Why these two pages and not the advanced ones: FBref's 2025/26 season pages
carry no Expected (xG/xAG) block for **any** competition in this pipeline --
not the Czech First League and not the Premier League (verified 2026-09-21
against the cached shooting pages: no `data-stat="xg"` on either). Shot
volume, playing time and the miscellaneous table are, by contrast, present
and identically shaped for every league in `config/leagues.yaml`, which is
what this atlas needs: one instrument, measured the same way everywhere.

What they add to `fbref_players.parquet`'s goals/assists/minutes/cards:

* **playing time** -- `starts`, `mn_per_start`, `compl` (matches finished),
  `subs`, `unsub` (unused substitute) and FBref's own `min_pct`. The report's
  youth mechanism has so far counted *minutes*; these columns separate a
  young player who starts from one who comes on at 3-0, which is a different
  football claim. `ppm`, `plus_minus_90` and `on_off` come with the page and
  are kept as a crude team-success signal, to be used only with their
  well-known caveats (team quality, selection).
* **miscellaneous** -- `fls`, `fld`, `off`, `crs`, `int`, `tklw`: enough
  crossing/defensive volume to describe a *role*, which goals and assists
  alone cannot.

Output: `data/processed/<nation>/fbref_roles.parquet`, one row per
(league, season, team, player_key), the two blocks merged outer -- the
playing-time page lists squad members with no minutes, the misc page does
not. Scope is the three configured seasons (previous/metrics/current) for
every league; the history seasons are deliberately out of scope, the analog
corpus does not use these columns.
"""

from __future__ import annotations

import logging

import pandas as pd

from src import config, leagues_setup
from src.fetch_fbref import fetch_player_page
from src.utils import player_key, write_parquet

LOG = logging.getLogger(__name__)

# (output name, FBref column) per page. Kept explicit rather than derived so a
# silent FBref column rename fails loudly in `_block` instead of producing NaN.
PLAYING_TIME = {
    "min_pct": ("Playing Time", "Min%"),
    "starts": ("Starts", "Starts"),
    "mn_per_start": ("Starts", "Mn/Start"),
    "compl": ("Starts", "Compl"),
    "subs": ("Subs", "Subs"),
    "mn_per_sub": ("Subs", "Mn/Sub"),
    "unsub": ("Subs", "unSub"),
    "ppm": ("Team Success", "PPM"),
    "plus_minus_90": ("Team Success", "+/-90"),
    "on_off": ("Team Success", "On-Off"),
}
MISC = {
    "fls": ("Performance", "Fls"),
    "fld": ("Performance", "Fld"),
    "off": ("Performance", "Off"),
    "crs": ("Performance", "Crs"),
    "interceptions": ("Performance", "Int"),
    "tklw": ("Performance", "TklW"),
}
KEYS = ["league", "season", "team", "player", "player_key"]


def _block(df: pd.DataFrame, cols: dict[str, tuple[str, str]], league: str, season: str) -> pd.DataFrame:
    """One page's table, reduced to `cols` plus the join keys.

    `parse_player_page` returns a (league, season, team, player)-indexed frame
    with FBref's two-level columns; a missing column is an error, not a NaN
    column, so an FBref rename surfaces at fetch time.
    """
    idx = df.index.to_frame(index=False)
    born = pd.to_numeric(df[("born", "")], errors="coerce")
    out = pd.DataFrame({"league": league, "season": season,
                        "team": idx["team"].values, "player": idx["player"].values})
    out["player_key"] = [player_key(n, b) for n, b in zip(out["player"], born, strict=True)]
    for name, col in cols.items():
        if col not in df.columns:
            raise KeyError(f"{league} {season}: no {col} column on the page")
        out[name] = pd.to_numeric(df[col], errors="coerce").values
    return out.drop_duplicates(subset=KEYS)


def fetch_roles(league: str, season: str) -> pd.DataFrame:
    """Both pages for one league-season, merged on the player keys."""
    pt = _block(fetch_player_page(league, season, "playing_time"), PLAYING_TIME, league, season)
    ms = _block(fetch_player_page(league, season, "misc"), MISC, league, season)
    return pt.merge(ms, on=KEYS, how="outer")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    leagues_setup.install()
    cfg, seasons = config.leagues(), config.seasons()
    leagues = list(dict.fromkeys(
        cfg["headline"] + [cfg["domestic"]] + list(cfg["custom"]) + list(cfg.get("peer_domestic", {}))))
    frames = []
    for league in leagues:
        for season in (seasons["previous"], seasons["metrics"], seasons["current"]):
            try:
                frames.append(fetch_roles(league, season))
                LOG.info("%s %s: %d rows", league, season, len(frames[-1]))
            except Exception as exc:   # one league failing must not kill the run
                LOG.warning("%s %s failed: %s", league, season, exc)
    write_parquet(pd.concat(frames, ignore_index=True), config.PROCESSED_DIR / "fbref_roles.parquet")


if __name__ == "__main__":
    main()
