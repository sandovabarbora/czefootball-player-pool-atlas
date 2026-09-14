"""Player season tables from FBref via soccerdata, normalised to a flat frame.

Output: data/processed/fbref_players.parquet (one row per player-team-season).
Raw HTML is cached by soccerdata itself under ~/soccerdata/data/FBref.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd
import soccerdata as sd
from lxml import etree, html
from soccerdata.fbref import FBREF_API, _fix_nation_col, _parse_table

from src import config, leagues_setup
from src.utils import player_key, write_parquet

LOG = logging.getLogger(__name__)
COLS = ["league", "season", "team", "player", "player_key", "nation", "pos", "born", "age",
        "mp", "min", "gls", "ast", "pk", "crdy", "crdr"]
SEASON_RE = re.compile(r"(\d{4}-\d{4})")
# FBref's URL segment per soccerdata stat_type (same mapping as soccerdata's reader)
PAGE_FOR_STAT = {"standard": "stats", "keeper": "keepers", "shooting": "shooting",
                 "playing_time": "playingtime", "misc": "misc"}


class SeasonMismatch(RuntimeError):
    """The page FBref served is not the season that was asked for."""


class MissingTable(RuntimeError):
    """The page has no player table (FBref intermittently serves a squads-only page)."""


def page_season(page_html: str) -> str | None:
    """Season named in the page's <h1> ("2025-2026 Ekstraklasa Stats"), or None."""
    tree = html.fromstring(page_html)
    h1 = tree.xpath("//h1")
    m = SEASON_RE.search(h1[0].text_content()) if h1 else None
    return m.group(1) if m else None


def parse_player_page(page_html: str, league: str, season: str, stat_type: str) -> pd.DataFrame:
    """Parse one FBref league-season player page into soccerdata's frame shape.

    Two reasons not to use `FBref.read_player_season_stats` for the parse:
    (1) a completed season's table has no "Matches" link column and
    soccerdata's fixed `.drop("Matches")` raises KeyError on it; (2) the
    season index page can be stale — FBref then serves the *current* season
    at the season-less URL — so the page's own <h1> is checked against
    `season` and a mismatch raises `SeasonMismatch` instead of mislabelling
    a whole league-season.
    """
    found = page_season(page_html)
    if found != season:
        raise SeasonMismatch(f"{league}: asked for {season}, page says {found}")
    tree = html.fromstring(page_html)
    for elem in tree.xpath("//td[@data-stat='comp_level']//span"):
        elem.getparent().remove(elem)
    comments = tree.xpath(f"//comment()[contains(.,'div_stats_{stat_type}')]")
    if not comments:
        raise MissingTable(f"{league} {season}: no player {stat_type} table on the page")
    el = comments[0]
    parser = etree.HTMLParser(recover=True)
    (table,) = etree.fromstring(el.text, parser).xpath(f"//table[contains(@id, 'stats_{stat_type}')]")
    df = _parse_table(table)
    df[("Unnamed: league", "league")] = league
    df[("Unnamed: season", "season")] = season
    df = _fix_nation_col(df)
    # header rows repeated inside the table body, and the columns soccerdata drops
    df = df[df[("Unnamed: 1_level_0", "Player")] != "Player"]
    df = df.drop(columns=[c for c in df.columns if c[1] in ("Rk", "Matches")])
    rename = {"Squad": "team", "Player": "player", "Nation": "nation", "Pos": "pos",
              "Age": "age", "Born": "born", "league": "league", "season": "season"}
    # single-level columns arrive as ("Unnamed: N", name): flatten them to (name, "")
    df.columns = pd.MultiIndex.from_tuples(
        [(rename.get(b, b), "") if str(a).startswith("Unnamed") else (a, b) for a, b in df.columns])
    return df.set_index(["league", "season", "team", "player"]).sort_index()


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


def _season_page_url(fb: sd.FBref, league: str, season: str, stat_type: str) -> str:
    """URL of the league-season player page, from the league's season index page."""
    seasons = fb.read_seasons()
    (row,) = [r for (lk, sk), r in seasons.iterrows() if lk == league]
    parts = row.url.split("/")
    return FBREF_API + "/".join(parts[:-1]) + f"/{PAGE_FOR_STAT[stat_type]}/" + parts[-1]


def fetch_player_page(league: str, season: str, stat_type: str = "standard") -> pd.DataFrame:
    """Cached page for (league, season). On a season mismatch the stale index
    and page are discarded; on a squads-only page (FBref serves one now and
    then) just the page is; either way one refetch, then give up."""
    # headless: FBref's Cloudflare gate lets the undetected driver through without
    # a visible window (verified 2026-09-14), and a window per page steals focus
    fb = sd.FBref(leagues=[league], seasons=[season], headless=True)
    skey = fb.seasons[0]
    page_path: Path = fb.data_dir / f"players_{league}_{skey}_{stat_type}.html"
    index_path: Path = fb.data_dir / f"seasons_{league}.html"
    for attempt in (1, 2):
        url = _season_page_url(fb, league, season, stat_type)
        page_html = fb.get(url, page_path).read().decode("utf-8", errors="ignore")
        try:
            return parse_player_page(page_html, league, season, stat_type)
        except (SeasonMismatch, MissingTable) as exc:
            if attempt == 2:
                raise
            stale = (page_path, index_path) if isinstance(exc, SeasonMismatch) else (page_path,)
            LOG.warning("%s; discarding %s and refetching", exc, ", ".join(p.name for p in stale))
            for p in stale:
                p.unlink(missing_ok=True)
    raise AssertionError("unreachable")


def fetch_league(league: str, season: str) -> pd.DataFrame:
    return normalize_player_table(fetch_player_page(league, season, "standard"), league, season)


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
