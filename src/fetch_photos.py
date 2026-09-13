"""Player photos: Wikidata P18 -> Wikimedia Commons file, downsized into docs/img/players/.

Match rule: Wikidata label equals the FBref name (accent-insensitive, via
normalize_name) AND birth year equals when both are known. When our own
`born` is unknown (<NA>), a *unique* label match is accepted instead (logged,
since it isn't confirmed by birth year) -- an ambiguous label (more than one
Wikidata person sharing that name) is skipped rather than guessed.

Credit = Commons file name (attribution required by CC-BY-SA); the page
footer / players.json lists every credit and links to the file page for the
exact licence.
"""
from __future__ import annotations

import io
import json
import logging
import time
import urllib.parse

import pandas as pd
import requests
from PIL import Image

from src import config
from src.utils import cached_text, normalize_name, read_parquet

LOG = logging.getLogger(__name__)
UA = {"User-Agent": "czefootball-player-pool-atlas/1.0 (barbora@datasimply.eu)"}
IMG_DIR = config.ROOT_DIR / "docs" / "img" / "players"
WIKIDATA_CACHE_DIR = config.RAW_DIR / "wikidata"
LICENSE_NOTE = "Wikimedia Commons — see file page for the licence"
BATCH_SIZE = 40
SPARQL_URL = "https://query.wikidata.org/sparql"


def sparql_for(names: list[str]) -> str:
    """Build a SPARQL query matching any of `names` who are Czech citizens (wd:Q213)."""
    values = " ".join(f'"{n}"@en' for n in names)
    return f"""SELECT ?p ?pLabel ?dob ?img WHERE {{
  VALUES ?name {{ {values} }}
  ?p rdfs:label ?name ; wdt:P27 wd:Q213 .
  OPTIONAL {{ ?p wdt:P569 ?dob }} OPTIONAL {{ ?p wdt:P18 ?img }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }} }}"""


def match_images(bindings: list[dict], pool: pd.DataFrame) -> pd.DataFrame:
    """Match Wikidata bindings (with an image) to pool players by name (+ birth year).

    Returns a DataFrame with columns fbref_id, player, image_url, credit.
    """
    by_norm: dict[str, list[tuple[int | None, str]]] = {}
    for b in bindings:
        if "img" not in b:
            continue
        name = b["pLabel"]["value"]
        year = int(b["dob"]["value"][:4]) if "dob" in b else None
        by_norm.setdefault(normalize_name(name), []).append((year, b["img"]["value"]))

    rows = []
    for r in pool.itertuples():
        candidates = by_norm.get(normalize_name(r.player))
        if not candidates:
            continue

        born_known = r.born is not None and not pd.isna(r.born)
        if born_known:
            dobbed = [c for c in candidates if c[0] is not None]
            match = next((c for c in dobbed if c[0] == int(r.born)), None)
            if match is None and not dobbed and len(candidates) == 1:
                LOG.info("%s: unique label match, wikidata dob missing", r.player)
                match = candidates[0]
        elif len(candidates) == 1:
            LOG.info("%s: unique label match, our birth year unknown", r.player)
            match = candidates[0]
        else:
            LOG.info("%s: ambiguous label (%d candidates) and no birth year to disambiguate, skipped", r.player, len(candidates))
            match = None

        if match is None:
            continue
        _year, url = match
        rows.append(
            {
                "fbref_id": r.fbref_id,
                "player": r.player,
                "image_url": url,
                "credit": urllib.parse.unquote(url.rsplit("/", 1)[-1]),
            }
        )
    return pd.DataFrame(rows, columns=["fbref_id", "player", "image_url", "credit"])


MAX_WIDTH = 480


def _download(url: str, dest) -> None:
    """Fetch a Commons image and save it as a JPEG no wider than MAX_WIDTH.

    Commons' Special:FilePath `?width=` hint rounds to its own thumbnail
    buckets (observed serving 500px for a 480px request), so width is
    re-enforced locally with PIL rather than trusted from the server.
    """
    r = requests.get(url + f"?width={MAX_WIDTH}", headers=UA, timeout=60)
    r.raise_for_status()
    img = Image.open(io.BytesIO(r.content)).convert("RGB")
    if img.width > MAX_WIDTH:
        height = round(img.height * MAX_WIDTH / img.width)
        img = img.resize((MAX_WIDTH, height), Image.LANCZOS)
    img.save(dest, "JPEG", quality=85)


def _fetch_batches(names: list[str]) -> list[dict]:
    """Query Wikidata in batches of BATCH_SIZE names, caching each response to disk."""
    bindings: list[dict] = []
    for i in range(0, len(names), BATCH_SIZE):
        batch = names[i : i + BATCH_SIZE]
        cache_path = WIKIDATA_CACHE_DIR / f"batch_{i // BATCH_SIZE}.json"
        was_cached = cache_path.exists()
        q = sparql_for(batch)
        url = f"{SPARQL_URL}?{urllib.parse.urlencode({'query': q, 'format': 'json'})}"
        text = cached_text(url, cache_path, headers=UA, timeout=120.0)
        bindings.extend(json.loads(text)["results"]["bindings"])
        if not was_cached:
            time.sleep(1)
    return bindings


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    pool = read_parquet(config.PROCESSED_DIR / "pool.parquet")
    # Players with no pos_group (goalkeepers/unknown) are not shown on the site.
    pool = pool[pool.pos_group.notna()].reset_index(drop=True)

    bindings = _fetch_batches(pool.player.tolist())
    matched = match_images(bindings, pool).drop_duplicates("fbref_id")

    IMG_DIR.mkdir(parents=True, exist_ok=True)
    out: dict[str, dict] = {}
    downloaded = 0
    failed = 0
    for r in matched.itertuples():
        dest = IMG_DIR / f"{r.fbref_id}.jpg"
        if not dest.exists():
            try:
                _download(r.image_url, dest)
                downloaded += 1
            except Exception as exc:
                LOG.warning("%s: download failed: %s", r.player, exc)
                failed += 1
                continue
        player_key = pool.loc[pool.fbref_id == r.fbref_id, "player_key"].iloc[0]
        out[r.fbref_id] = {
            "name": r.player,
            "player_key": player_key,
            "image": f"img/players/{r.fbref_id}.jpg",
            "credit": r.credit,
            "license": LICENSE_NOTE,
        }

    site_dir = config.ROOT_DIR / "site"
    site_dir.mkdir(parents=True, exist_ok=True)
    (site_dir / "players.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    LOG.info(
        "photos: matched %d, downloaded %d, failed %d, of %d eligible pool players",
        len(matched), downloaded, failed, len(pool),
    )


if __name__ == "__main__":
    main()
