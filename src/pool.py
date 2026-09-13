"""Czech-eligible pool: discovery (FBref country page) ∪ league tables.

The country page lists every Czech player FBref ever tracked as one <p> per
player: link (id + name), career span, position, clubs most-recent-first.
"""
from __future__ import annotations

import logging
import re

import pandas as pd
from bs4 import BeautifulSoup

from src import config
from src.utils import normalize_name, player_key, read_parquet, write_parquet

LOG = logging.getLogger(__name__)
COUNTRY_URL = "https://fbref.com/en/country/players/CZE/Czechia-Football-Players"
ENTRY = re.compile(r"^(?P<span>\d{4}(?:-\d{4})?)\s*·\s*(?P<pos>[A-Z,]+)(?:\s*·\s*(?P<clubs>.*))?$")


def pos_group(pos: str | None) -> str | None:
    first = (pos or "").split(",")[0].strip()
    return first if first in ("FW", "MF", "DF") else None


def parse_country_page(html: str, current_start_year: int) -> pd.DataFrame:
    soup = BeautifulSoup(html, "lxml")
    rows = []
    for p in soup.find_all("p"):
        a = p.find("a", href=re.compile(r"^/en/players/[0-9a-f]{8}/"))
        if a is None:
            continue
        pid = a["href"].split("/")[3]
        name = a.get_text(strip=True)
        rest = p.get_text(" ", strip=True)[len(name):].strip()
        m = ENTRY.match(rest)
        if not m:
            continue
        span = m.group("span")
        start, end = int(span[:4]), int(span[-4:])
        clubs = [c.strip() for c in (m.group("clubs") or "").split(",") if c.strip()]
        rows.append({"fbref_id": pid, "player": name, "player_norm": normalize_name(name),
                     "span_start": start, "span_end": end,
                     "active": bool(a.find("strong")) or end >= current_start_year,
                     "pos": m.group("pos"), "clubs": clubs})
    return pd.DataFrame(rows).drop_duplicates("fbref_id")


def fetch_country_page() -> str:
    import soccerdata as sd
    fb = sd.FBref(leagues=["ENG-Premier League"], seasons=[config.seasons()["current"]])
    return fb.get(COUNTRY_URL, fb.data_dir / "country_cze.html").read().decode("utf-8")


def unmatched_clubs(pool: pd.DataFrame, tables: pd.DataFrame) -> pd.DataFrame:
    known = set(tables.team.map(normalize_name))
    act = pool[pool.active & ~pool.in_fbref_tables]
    counts = act.club_current.map(lambda c: c if c and normalize_name(c) not in known else None).dropna().value_counts()
    return counts.rename_axis("club").reset_index(name="n_players")


def build_pool() -> pd.DataFrame:
    current_year = int(config.seasons()["current"][:4])
    disc = parse_country_page(fetch_country_page(), current_year)
    tables = read_parquet(config.PROCESSED_DIR / "fbref_players.parquet")
    cze = tables[tables.nation == "CZE"].copy()
    cze["player_norm"] = cze.player.map(normalize_name)
    born_by_norm = cze.groupby("player_norm")["born"].first()
    pool = disc.copy()
    pool["born"] = pool.player_norm.map(born_by_norm).astype("Int64")
    pool["player_key"] = [player_key(n, b) for n, b in zip(pool.player, pool.born, strict=True)]
    pool["pos_group"] = pool.pos.map(pos_group)
    pool["club_current"] = pool.clubs.map(lambda c: next((x for x in c if x != "Czechia"), ""))
    pool["in_fbref_tables"] = pool.player_norm.isin(set(cze.player_norm))
    dup = pool[pool.active].player_norm.duplicated(keep=False)
    if dup.any():
        LOG.warning("active players sharing a normalised name: %s", sorted(pool[pool.active][dup].player.unique()))
    miss = unmatched_clubs(pool, tables)
    if len(miss):
        LOG.warning("active Czech players at clubs outside fetched leagues (extend config/leagues.yaml):\n%s",
                    miss.head(30).to_string(index=False))
    out = pool[pool.active][["player_key", "fbref_id", "player", "born", "pos_group", "club_current", "in_fbref_tables"]].reset_index(drop=True)
    write_parquet(out, config.PROCESSED_DIR / "pool.parquet")
    LOG.info("pool: %d active players, %d with metrics", len(out), int(out.in_fbref_tables.sum()))
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    build_pool()


if __name__ == "__main__":
    main()
