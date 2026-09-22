"""Official LaLiga portraits for the pool, from the league's public API.

laliga.com's own front end reads a public API (apim.laliga.com, with the
read-only subscription key it ships in every page) that lists each club's
squad with names, birth dates and the official studio portraits on the
league's asset host (transparent PNGs). The 20 club slugs of the season
come from the site's clubs page (kept in CLUBS below and refreshed by
hand when the league changes). Matching on normalised name and birth
year, as for the Czech and Premier League sources; output as
src.fetch_photos_pl: docs/img/players/<fbref_id>-league.png and a
site/players.<nation>.json entry credited "LaLiga, official portrait".
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
API = "https://apim.laliga.com/public-service/api/v1"
KEY = "c13c3a8e2f6b46da9c5c425cf61fab3e"   # the read-only key laliga.com's pages carry
UA = {"User-Agent": "Mozilla/5.0 (Macintosh) player-pool-atlas/1.0 (portfolio; contact via repository)"}
SEASON_YEARS = (2026, 2025)               # the season in progress and the metrics season (start years)
CLUBS = ["athletic-club", "atletico-de-madrid", "c-a-osasuna", "rc-celta", "d-alaves", "elche-c-f", "fc-barcelona", "getafe-cf",
         "levante-ud", "malaga-cf", "r-racing-club", "rayo-vallecano", "rc-deportivo", "rcd-espanyol", "real-betis", "real-madrid",
         "real-sociedad", "sevilla-fc", "valencia-cf", "villarreal-cf",
         # 2025/26 clubs since relegated
         "girona-fc", "real-oviedo", "rcd-mallorca"]
PAGE = "https://www.laliga.com/en-GB/player/{slug}"


def squad(club: str, year: int) -> list[dict]:
    url = f"{API}/teams/{club}/squad-manager?limit=60&offset=0&orderField=id&orderType=DESC&seasonYear={year}&contentLanguage=en&subscription-key={KEY}"
    r = requests.get(url, headers=UA, timeout=30)
    if r.status_code != 200:
        LOG.warning("%s %s: %s", club, year, r.status_code)
        return []
    out = []
    for s in r.json().get("squads", []):
        p = s.get("person") or {}
        dob = (p.get("date_of_birth") or "")[:4]
        photos = s.get("photos") or {}
        square = photos.get("004") or {}
        img = square.get("512x512") or square.get("1024x1024") or next(iter(square.values()), None)
        if p.get("name") and dob.isdigit() and img:
            out.append({"league_id": str(p.get("id")), "name": p["name"], "born": int(dob), "image": img, "slug": p.get("slug")})
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    pool = read_parquet(config.PROCESSED_DIR / "pool.parquet")
    rows: dict[str, dict] = {}
    for year in SEASON_YEARS:
        for club in CLUBS:
            for r in squad(club, year):
                rows.setdefault(r["league_id"], r)
            time.sleep(0.3)
        LOG.info("season %d: %d players so far", year, len(rows))
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
            "credit": "LaLiga, official portrait",
            "license": "league portrait, used with credit; not part of the MIT-licensed repository",
            "source_url": PAGE.format(slug=row["slug"]) if row.get("slug") else "https://www.laliga.com/",
        }
    players_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    LOG.info("%d portraits downloaded, players.%s.json now has %d entries", n_new, config.NATION, len(manifest))


if __name__ == "__main__":
    main()
