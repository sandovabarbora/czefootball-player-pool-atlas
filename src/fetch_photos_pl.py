"""Official Premier League headshots for the pool, from the league's own API.

The Premier League publishes one studio headshot per player (250 x 250,
transparent background) at a stable URL keyed by the player's Opta id,
and its site's API lists every player of a season with name, birth date
and nationality. Like src.fetch_photos_league for the Czech league, this
matches the pool on normalised name and birth year and prefers the
official portrait to whatever Commons had -- for any home nation: a Czech
or Danish player in the Premier League gets his league portrait too.

Output: docs/img/players/<fbref_id>-league.png (kept as PNG: the
transparent background is the cut-out the cards want) and an entry in
site/players.<nation>.json with the credit "Premier League, official
headshot". Players not in the league keep whatever portrait they had.
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
API = "https://footballapi.pulselive.com/football"
PHOTO = "https://resources.premierleague.com/premierleague/photos/players/250x250/{opta}.png"
PAGE = "https://www.premierleague.com/players/{id}/"
HEADERS = {"Origin": "https://www.premierleague.com", "Referer": "https://www.premierleague.com/",
           "User-Agent": "Mozilla/5.0 (Macintosh) player-pool-atlas/1.0 (portfolio; contact via repository)"}
N_SEASONS = 2          # the metrics season and the one in progress


def seasons(n: int = N_SEASONS) -> list[dict]:
    r = requests.get(f"{API}/competitions/1/compseasons?page=0&pageSize={n}", headers=HEADERS, timeout=30)
    r.raise_for_status()
    return [{"id": int(s["id"]), "label": s["label"]} for s in r.json()["content"]]


def players(season_id: int) -> list[dict]:
    """(pl id, opta id, name, birth year) for every player of the season."""
    out, page = [], 0
    while True:
        r = requests.get(f"{API}/players?pageSize=100&compSeasons={season_id}&altIds=true&page={page}&type=player&id=-1",
                         headers=HEADERS, timeout=30)
        r.raise_for_status()
        body = r.json()
        for p in body["content"]:
            born = p.get("birth", {}).get("date", {}).get("label", "")
            year = int(born[-4:]) if born[-4:].isdigit() else None
            opta = (p.get("altIds") or {}).get("opta")
            if year and opta:
                out.append({"league_id": int(p["id"]), "opta": opta, "name": p["name"]["display"], "born": year})
        page += 1
        if page >= body["pageInfo"]["numPages"]:
            break
        time.sleep(0.4)
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    pool = read_parquet(config.PROCESSED_DIR / "pool.parquet")
    rows: dict[int, dict] = {}
    for s in seasons():
        for r in players(s["id"]):
            rows.setdefault(r["league_id"], r)
        LOG.info("%s: %d players so far", s["label"], len(rows))
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
            resp = requests.get(PHOTO.format(opta=row["opta"]), headers=HEADERS, timeout=60)
            if resp.status_code != 200 or not resp.headers.get("content-type", "").startswith("image/"):
                LOG.warning("no headshot for %s (%s): %s", row["name"], row["opta"], resp.status_code)
                continue
            dest.write_bytes(resp.content)
            n_new += 1
            time.sleep(0.5)
        p = by_id[fid]
        manifest[fid] = {
            "name": p.player, "player_key": p.player_key,
            "image": f"img/players/{fid}-league.png",
            "credit": "Premier League, official headshot",
            "license": "league portrait, used with credit; not part of the MIT-licensed repository",
            "source_url": PAGE.format(id=row["league_id"]),
        }
    players_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    LOG.info("%d headshots downloaded, players.%s.json now has %d entries", n_new, config.NATION, len(manifest))


if __name__ == "__main__":
    main()
