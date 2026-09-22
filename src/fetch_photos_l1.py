"""Official Ligue 1 portraits for the pool, from the league's open API.

ligue1.com's front end reads an unauthenticated API (ma-api.ligue1.fr):
the season's standings list the clubs, and each club's summary carries the
squad with birth dates and the official portraits (transparent PNG
busts, 800 x 600) on the league's image host. Matching on normalised name
and birth year; output as src.fetch_photos_pl: docs/img/players/
<fbref_id>-league.png and a site/players.<nation>.json entry credited
"Ligue 1 (LFP), official portrait".
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import requests

from src import config
from src.fetch_photos_league import DOCS, match_pool
from src.utils import read_parquet

LOG = logging.getLogger(__name__)
API = "https://ma-api.ligue1.fr"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh) player-pool-atlas/1.0 (portfolio; contact via repository)"}
SEASONS = (2026, 2025)     # start years: the season in progress and the metrics season


def clubs(season: int) -> list[str]:
    r = requests.get(f"{API}/championship-standings/1/general?season={season}", headers=UA, timeout=30)
    r.raise_for_status()
    return [row["clubId"] for row in r.json()["standings"].values()]


def squad(club_id: str, season: int) -> list[dict]:
    r = requests.get(f"{API}/championship-club-summary/{club_id}?season={season}", headers=UA, timeout=30)
    if r.status_code != 200:
        LOG.warning("%s %s: %s", club_id, season, r.status_code)
        return []
    out = []
    for p in (r.json().get("squad") or {}).get("players", {}).values():
        dob = (p.get("birthDate") or "")[:4]
        img = ((p.get("assets") or {}).get("bustPictures") or {}).get("large")
        name = f"{p.get('firstName', '')} {p.get('lastName', '')}".strip()
        if name and dob.isdigit() and img:
            out.append({"league_id": p["id"], "name": name, "born": int(dob), "image": img})
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    pool = read_parquet(config.PROCESSED_DIR / "pool.parquet")
    rows: dict[str, dict] = {}
    for season in SEASONS:
        for club_id in clubs(season):
            for r in squad(club_id, season):
                rows.setdefault(r["league_id"], r)
            time.sleep(0.3)
        LOG.info("season %d: %d players so far", season, len(rows))
    matched = match_pool(list(rows.values()), pool)
    LOG.info("%d league players, %d matched to the pool of %d", len(rows), len(matched), len(pool))

    players_path = Path(__file__).resolve().parents[1] / "site" / f"players.{config.NATION}.json"
    manifest = json.loads(players_path.read_text(encoding="utf-8")) if players_path.exists() else {}
    out_dir = DOCS / "img" / "players"
    out_dir.mkdir(parents=True, exist_ok=True)
    by_id = {r.fbref_id: r for r in pool.itertuples()}
    n_new = 0
    for fid, row in matched.items():
        dest = out_dir / f"{fid}-league.png"
        if not dest.exists():
            resp = requests.get(row["image"], headers=UA, timeout=60)
            if resp.status_code != 200 or not resp.headers.get("content-type", "").startswith("image/"):
                LOG.warning("no portrait for %s: %s", row["name"], resp.status_code)
                continue
            dest.write_bytes(resp.content)
            n_new += 1
            time.sleep(0.5)
        p = by_id[fid]
        manifest[fid] = {
            "name": p.player, "player_key": p.player_key,
            "image": f"img/players/{fid}-league.png",
            "credit": "Ligue 1 (LFP), official portrait",
            "license": "league portrait, used with credit; not part of the MIT-licensed repository",
            "source_url": "https://ligue1.com/",
        }
    players_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    LOG.info("%d portraits downloaded, players.%s.json now has %d entries", n_new, config.NATION, len(manifest))


if __name__ == "__main__":
    main()
