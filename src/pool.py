"""Czech-eligible pool: discovery (FBref country page) ∪ league tables.

The country page lists every Czech player FBref ever tracked as one <p> per
player: link (id + name), career span, position, clubs most-recent-first.

Two known data-quality caveats in the source page, both handled here:

- The page mixes women's players into the same unmarked list as men. We drop
  entries whose surname ends in "-ová" (the Czech feminine-surname suffix,
  see `is_feminine_surname`) as a heuristic filter. This is not exhaustive:
  a naturalised or foreign-married name that doesn't follow the convention
  can still slip through, and this is called out as a residual-contamination
  limitation rather than a guarantee.
- Two different players can share a normalised name (e.g. father/son both
  "Ladislav Krejčí"), which would otherwise collide onto the same
  `player_key`. `pick_born` disambiguates using the pool entry's own club
  list against each candidate's most recent club in `fbref_players.parquet`.
"""
from __future__ import annotations

import logging
import re

import pandas as pd
from bs4 import BeautifulSoup

from src import config
from src.utils import normalize_name, player_key, read_parquet, write_parquet

LOG = logging.getLogger(__name__)
COUNTRY_URL = config.nation()["fbref_country_page"]
ENTRY = re.compile(r"^(?P<span>\d{4}(?:-\d{4})?)\s*·\s*(?P<pos>[A-Z,]+)(?:\s*·\s*(?P<clubs>.*))?$")


def pos_group(pos: str | None) -> str | None:
    first = (pos or "").split(",")[0].strip()
    return first if first in ("FW", "MF", "DF") else None


def is_feminine_surname(name: str | None) -> bool:
    """Heuristic: Czech feminine surnames conventionally end in "-ová".

    Used to filter women's players out of FBref's country page, which mixes
    them into the same unmarked list as men (see module docstring). Not
    exhaustive -- see the caveat there.
    """
    tokens = (name or "").split()
    if not tokens:
        return False
    return tokens[-1].lower().endswith("ová")


def parse_country_page(html: str, current_start_year: int) -> pd.DataFrame:
    soup = BeautifulSoup(html, "lxml")
    rows = []
    dropped = 0
    for p in soup.find_all("p"):
        a = p.find("a", href=re.compile(r"^/en/players/[0-9a-f]{8}/"))
        if a is None:
            continue
        pid = a["href"].split("/")[3]
        name = a.get_text(strip=True)
        if is_feminine_surname(name):
            dropped += 1
            continue
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
    if dropped:
        LOG.info("dropped %d women's entries by -ová suffix", dropped)
    return pd.DataFrame(rows).drop_duplicates("fbref_id")


def fetch_country_page() -> str:
    import soccerdata as sd
    fb = sd.FBref(leagues=["ENG-Premier League"], seasons=[config.seasons()["current"]], headless=True)
    cache_name = config.nation()["fbref_country_cache"]
    return fb.get(COUNTRY_URL, fb.data_dir / cache_name).read().decode("utf-8")


def unmatched_clubs(pool: pd.DataFrame, tables: pd.DataFrame) -> pd.DataFrame:
    known = set(tables.team.map(normalize_name))
    act = pool[pool.active & ~pool.in_fbref_tables]
    counts = act.club_current.map(lambda c: c if c and normalize_name(c) not in known else None).dropna().value_counts()
    return counts.rename_axis("club").reset_index(name="n_players")


def pick_born(candidates: list[tuple[int, str]], clubs: list[str]) -> int | None:
    """Pick the birth year for a pool entry whose normalised name is shared by
    more than one player in `fbref_players.parquet` (e.g. father/son pairs).

    `candidates` is one `(born, most_recent_team)` pair per distinct born
    year sharing that normalised name (most recent = latest season row for
    that born year). `clubs` is the pool entry's own club list from the
    country page (most-recent-first). Returns the born year whose team
    (normalised) appears in `clubs`; if none match, falls back to the first
    candidate. Returns None when there are no candidates at all.
    """
    if not candidates:
        return None
    norm_clubs = {normalize_name(c) for c in clubs}
    for born, team in candidates:
        if normalize_name(team) in norm_clubs:
            return born
    return candidates[0][0]


def _born_candidates_by_norm(cze: pd.DataFrame) -> dict[str, list[tuple[int, str]]]:
    """Build `pick_born`'s per-normalised-name candidate lists from the
    CZE-nation rows of `fbref_players.parquet`: one `(born, most_recent_team)`
    pair per distinct born year, using that born year's latest season row.
    """
    known = cze.dropna(subset=["born"]).sort_values("season")
    out: dict[str, list[tuple[int, str]]] = {}
    for norm, g in known.groupby("player_norm"):
        latest = g.groupby("born", as_index=False).tail(1)
        out[norm] = list(zip(latest.born.astype(int), latest.team, strict=True))
    return out


def build_pool() -> pd.DataFrame:
    current_year = int(config.seasons()["current"][:4])
    disc = parse_country_page(fetch_country_page(), current_year)
    tables = read_parquet(config.PROCESSED_DIR / "fbref_players.parquet")
    cze = tables[tables.nation == config.HOME].copy()
    cze["player_norm"] = cze.player.map(normalize_name)
    cand_by_norm = _born_candidates_by_norm(cze)
    pool = disc.copy()
    pool["born"] = [
        pick_born(cand_by_norm.get(norm, []), clubs)
        for norm, clubs in zip(pool.player_norm, pool.clubs, strict=True)
    ]
    pool["born"] = pool["born"].astype("Int64")
    pool["player_key"] = [player_key(n, b) for n, b in zip(pool.player, pool.born, strict=True)]
    pool["pos_group"] = pool.pos.map(pos_group)
    home_name = config.nation()["name"]
    pool["club_current"] = pool.clubs.map(lambda c: next((x for x in c if x != home_name), ""))
    pool["in_fbref_tables"] = pool.player_norm.isin(set(cze.player_norm))
    for _, row in pool[pool.active].iterrows():
        cands = cand_by_norm.get(row.player_norm, [])
        if len(cands) <= 1:
            continue
        norm_clubs = {normalize_name(c) for c in row.clubs}
        if not any(normalize_name(team) in norm_clubs for _, team in cands):
            LOG.warning("ambiguous name %r (fbref_id=%s): no club match among %s; defaulted born=%s",
                        row.player, row.fbref_id, cands, cands[0][0])
    dup = pool[pool.active].player_norm.duplicated(keep=False)
    if dup.any():
        LOG.warning("active players sharing a normalised name: %s", sorted(pool[pool.active][dup].player.unique()))
    miss = unmatched_clubs(pool, tables)
    if len(miss):
        LOG.warning("active %s players at clubs outside fetched leagues (extend config/leagues.yaml):\n%s",
                    config.nation()["adjective"].lower(), miss.head(30).to_string(index=False))
    out = pool[pool.active][["player_key", "fbref_id", "player", "born", "pos_group", "club_current", "in_fbref_tables"]].reset_index(drop=True)
    write_parquet(out, config.PROCESSED_DIR / "pool.parquet")
    LOG.info("pool: %d active players, %d with metrics", len(out), int(out.in_fbref_tables.sum()))
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    build_pool()


if __name__ == "__main__":
    main()
