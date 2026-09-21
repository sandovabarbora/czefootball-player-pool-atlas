"""Official league portraits for the pool: one source, one style.

The Wikimedia Commons portraits (src/fetch_photos.py) are licensed but
inconsistent: press-box crops, different lighting, half the pool missing.
The domestic league's own site publishes one studio portrait per player,
300 x 400 on a white ground, at a stable URL, the way the NHL publishes
its mugs. This module walks every club's squad page for the metrics and the
current season, matches players to the pool on normalised name and birth
year, downloads the portrait to docs/img/players/<fbref_id>-league.jpg,
and updates site/players.<nation>.json so the site layer prefers it, with
the credit "<league site> (official portrait)". Players the league does
not carry (exports) keep whatever portrait they had.

Configured per nation in config/nations/<nation>.yaml::league_photos:
    site:  https://www.chanceliga.cz
    clubs: /                      (page listing /klub/<id>-<slug> links)
    table: /tabulka/{season}/aktualni?id_stage=1   (that season's clubs, relegated ones included)
    squad: /klub/{season}/kadr/{club}   (season = end year, e.g. 2026 for 2025/26)
    photo: /photo/player/player_{id}.jpg
A nation without the block is skipped.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import pandas as pd

from src import config
from src.utils import http_get, normalize_name, read_parquet

LOG = logging.getLogger(__name__)
DOCS = config.ROOT_DIR / "docs" if hasattr(config, "ROOT_DIR") else Path(__file__).resolve().parents[1] / "docs"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh) player-pool-atlas/1.0 (portfolio; contact via repository)"}

CLUB_RE = re.compile(r'href="/klub/(\d+-[^"/]+)"')
ROW_RE = re.compile(r'<a href="/hrac/(\d+)-[^"]*"[^>]*>([^<]+)</a>.*?<td class="">(\d{2})\.(\d{2})\.(\d{4})</td>', re.S)


def parse_clubs(html: str) -> list[str]:
    return sorted(set(CLUB_RE.findall(html)))


def parse_squad(html: str) -> list[dict]:
    """(league player id, name, birth year) per row of a squad table."""
    out = []
    for pid, name, _d, _m, year in ROW_RE.findall(html):
        out.append({"league_id": int(pid), "name": re.sub(r"\s+", " ", name).strip(), "born": int(year)})
    return out


def match_pool(rows: list[dict], pool: pd.DataFrame) -> dict[str, dict]:
    """{fbref_id: row} for league rows that match a pool player on
    normalised name and birth year; a name that matches two pool players
    is skipped rather than guessed."""
    key = {}
    for r in pool.itertuples():
        if pd.isna(r.born):
            continue
        key.setdefault((normalize_name(r.player), int(r.born)), []).append(r.fbref_id)
    out = {}
    for row in rows:
        ids = key.get((normalize_name(row["name"]), row["born"]), [])
        if len(ids) == 1:
            out[ids[0]] = row
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    cfg = config.nation().get("league_photos")
    if not cfg:
        LOG.info("no league_photos block for %s; nothing to do", config.NATION)
        return
    site, seasons = cfg["site"], cfg.get("seasons", [])
    pool = read_parquet(config.PROCESSED_DIR / "pool.parquet")
    rows: dict[int, dict] = {}
    for season in seasons:
        # the front page lists this season's clubs only; a season's standings
        # page (config `table`) also carries the ones relegated since, whose
        # squad pages stay up -- the metrics season's exports would otherwise
        # be the players most often missing
        clubs = set(parse_clubs(http_get(site + cfg["clubs"], headers=UA).text))
        if cfg.get("table"):
            try:
                clubs |= set(parse_clubs(http_get(site + cfg["table"].format(season=season), headers=UA).text))
            except Exception as exc:
                LOG.warning("standings %s: %s", season, exc)
        # one entry per club id: the standings page links a short slug
        # (/klub/10-dukla), the front page the full one; the squad page
        # renders fully only under the full slug, so keep the longest
        by_id: dict[str, str] = {}
        for c in clubs:
            cid = c.split("-", 1)[0]
            if len(c) > len(by_id.get(cid, "")):
                by_id[cid] = c
        clubs = set(by_id.values())
        LOG.info("season %s: %d clubs", season, len(clubs))
        for club in sorted(clubs):
            url = site + cfg["squad"].format(season=season, club=club)
            try:
                for r in parse_squad(http_get(url, headers=UA).text):
                    rows.setdefault(r["league_id"], r)
            except Exception as exc:   # one club page failing must not kill the run
                LOG.warning("%s: %s", url, exc)
    matched = match_pool(list(rows.values()), pool)
    LOG.info("%d league players, %d matched to the pool of %d", len(rows), len(matched), len(pool))

    players_path = Path(__file__).resolve().parents[1] / "site" / f"players.{config.NATION}.json"
    players = json.loads(players_path.read_text(encoding="utf-8")) if players_path.exists() else {}
    out_dir = DOCS / "img" / "players"
    out_dir.mkdir(parents=True, exist_ok=True)
    by_id = {r.fbref_id: r for r in pool.itertuples()}
    n_new = 0
    for fid, row in matched.items():
        dest = out_dir / f"{fid}-league.jpg"
        if not dest.exists():
            try:
                resp = http_get(site + cfg["photo"].format(id=row["league_id"]), headers=UA)
            except Exception as exc:   # a player without a portrait (404) keeps his old one
                LOG.warning("no portrait for %s (%s): %s", row["name"], row["league_id"], exc)
                continue
            if not resp.headers.get("content-type", "").startswith("image/"):
                LOG.warning("no portrait for %s (%s)", row["name"], row["league_id"])
                continue
            dest.write_bytes(resp.content)
            n_new += 1
        p = by_id[fid]
        players[fid] = {
            "name": p.player, "player_key": p.player_key,
            "image": f"img/players/{fid}-league.jpg",
            "credit": cfg.get("credit", site), "license": cfg.get("license", "official league portrait"),
            "source_url": site + f"/hrac/{row['league_id']}",
        }
    players_path.write_text(json.dumps(players, ensure_ascii=False, indent=1), encoding="utf-8")
    LOG.info("%d portraits downloaded, players.%s.json now has %d entries", n_new, config.NATION, len(players))


if __name__ == "__main__":
    main()
