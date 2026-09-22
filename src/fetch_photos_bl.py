"""Official Bundesliga portraits for the pool, from the league's own site.

bundesliga.com is a client-rendered app whose club pages carry the squad in
an embedded state object: each player with his DFL id, names, nationality
and the URL of his official portrait (a transparent render on the league's
asset host). The pages need a browser to render, so each club page is
loaded once in headless Chrome and the state parsed; the API behind the
site needs a key and is not used.

Matching is by normalised full name (the state carries no birth date),
guarded by the pool: only pool players whose latest fetched season is in
the Bundesliga are candidates, and a name that fits two of them is
skipped. Output as src.fetch_photos_pl: docs/img/players/<fbref_id>-league.png
and a site/players.<nation>.json entry credited "Bundesliga (DFL), official
portrait".
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import time
from pathlib import Path

import requests

from src import config
from src.fetch_photos_league import DOCS
from src.utils import normalize_name, read_parquet

LOG = logging.getLogger(__name__)
SITE = "https://www.bundesliga.com"
CLUBS_PAGE = f"{SITE}/en/bundesliga/clubs"
UA = "Mozilla/5.0 (Macintosh) player-pool-atlas/1.0 (portfolio; contact via repository)"
CHROME = shutil.which("google-chrome") or shutil.which("chromium") or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CACHE = config.RAW_DIR / "bundesliga"


def dump(url: str, name: str) -> str:
    """The rendered DOM of a page, cached under data/raw/bundesliga/."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{name}.html"
    if path.exists():
        return path.read_text(encoding="utf-8", errors="ignore")
    out = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--virtual-time-budget=15000", "--dump-dom", url],
                         capture_output=True, text=True, timeout=120).stdout
    path.write_text(out, encoding="utf-8")
    time.sleep(1.0)
    return out


def club_slugs(html: str) -> list[str]:
    return sorted(set(re.findall(r"/en/bundesliga/clubs/([a-z0-9-]+)", html)))


PLAYER_RE = re.compile(r'"id":"(DFL-OBJ-[0-9A-Z]+)","lastUpdate":[^,]*,"name":\{(.*?)\},"nationality":\{(.*?)\},"playerImages":\{"FACE_CIRCLE":"([^"]+)"\}')


def parse_players(html: str) -> list[dict]:
    """(dfl id, names, nationality code, portrait url) per player in a club page's state."""
    out = []
    html = html.replace("\\u002F", "/")
    for pid, names, nat, img in PLAYER_RE.findall(html):
        get = lambda blob, key: (re.search(rf'"{key}":"([^"]*)"', blob) or [None, None])[1]   # noqa: E731
        full, alias = get(names, "full"), get(names, "alias")
        slug = get(names, "slugifiedFull")
        code = get(nat, "firstNationalityCode")
        out.append({"league_id": pid, "names": [n for n in (full, alias) if n], "slug": slug, "nation": code,
                    "image": img.replace("-circle.png", ".png")})
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    pool = read_parquet(config.PROCESSED_DIR / "pool.parquet")
    players = read_parquet(config.PROCESSED_DIR / "fbref_players.parquet")
    latest = players.sort_values("season").groupby("player_key").tail(1)
    in_bl = set(latest[latest.league == "GER-Bundesliga"].player_key)
    cands = pool[pool.player_key.isin(in_bl)]
    LOG.info("%d pool players whose latest season is in the Bundesliga", len(cands))
    if cands.empty:
        return
    by_name: dict[str, list] = {}
    for r in cands.itertuples():
        by_name.setdefault(normalize_name(r.player), []).append(r)

    rows: dict[str, dict] = {}
    for slug in club_slugs(dump(CLUBS_PAGE, "clubs")):
        for p in parse_players(dump(f"{SITE}/en/bundesliga/clubs/{slug}", f"club_{slug}")):
            rows.setdefault(p["league_id"], p)
    LOG.info("%d league players across the club pages", len(rows))
    matched: dict[str, dict] = {}
    for p in rows.values():
        hits = {r.fbref_id: r for n in p["names"] for r in by_name.get(normalize_name(n), [])}
        if len(hits) == 1:
            fid = next(iter(hits))
            matched[fid] = p
    LOG.info("%d matched to the pool", len(matched))

    players_path = Path(__file__).resolve().parents[1] / "site" / f"players.{config.NATION}.json"
    manifest = json.loads(players_path.read_text(encoding="utf-8")) if players_path.exists() else {}
    out_dir = DOCS / "img" / "players"
    out_dir.mkdir(parents=True, exist_ok=True)
    by_id = {r.fbref_id: r for r in cands.itertuples()}
    n_new = 0
    for fid, p in matched.items():
        dest = out_dir / f"{fid}-league.png"
        if not dest.exists():
            resp = requests.get(p["image"], headers={"User-Agent": UA}, timeout=60)
            if resp.status_code != 200 or not resp.headers.get("content-type", "").startswith("image/"):
                LOG.warning("no portrait for %s: %s", p["names"][0], resp.status_code)
                continue
            dest.write_bytes(resp.content)
            n_new += 1
            time.sleep(0.5)
        r = by_id[fid]
        manifest[fid] = {
            "name": r.player, "player_key": r.player_key,
            "image": f"img/players/{fid}-league.png",
            "credit": "Bundesliga (DFL), official portrait",
            "license": "league portrait, used with credit; not part of the MIT-licensed repository",
            "source_url": f"{SITE}/en/player/{p['slug']}" if p.get("slug") else SITE,
        }
    players_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    LOG.info("%d portraits downloaded, players.%s.json now has %d entries", n_new, config.NATION, len(manifest))


if __name__ == "__main__":
    main()
