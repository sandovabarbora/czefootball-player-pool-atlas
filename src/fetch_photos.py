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

import argparse
import hashlib
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
UA = {"User-Agent": "czefootball-player-pool-atlas/1.0 (hello@bsandova.com)"}
IMG_DIR = config.ROOT_DIR / "docs" / "img" / "players"
WIKIDATA_CACHE_DIR = config.RAW_DIR / "wikidata" / config.NATION
LICENSE_NOTE = "Wikimedia Commons — see file page for the licence"
BATCH_SIZE = 40
SPARQL_URL = "https://query.wikidata.org/sparql"
# Above this pool size, the Wikipedia second pass (one to two HTTP requests
# per unmatched player, uncached on a first run) defaults to only the
# players who will actually appear on the site -- those with metrics
# (`pool.in_fbref_tables`; cards/the player index need a features row, which
# only exists for players FBref's league tables actually tracked). A small
# home nation (e.g. Czechia, ~440 pool entries) can afford the full pass;
# England's ~3,500-entry country page cannot -- most of those thousands are
# lower-league players with no metrics and, so, no page to render them on.
ONLY_WITH_METRICS_POOL_THRESHOLD = 1000


def _sparql_escape(text: str) -> str:
    """Escape a value for a double-quoted SPARQL string literal.

    Backslash first, then the quote, so a name like `O"Brien` or one with a
    stray backslash cannot break out of the literal (or the whole query).
    """
    return text.replace("\\", "\\\\").replace('"', '\\"')


def sparql_for(names: list[str]) -> str:
    """Build a SPARQL query matching any of `names` who carry the home nation's
    P27 citizenship value (`nation()["wikidata_citizenship"]`, wd:Q213 for
    Czechia) and are association football players (wd:Q937857)."""
    citizenship = config.nation()["wikidata_citizenship"]
    values = " ".join(f'"{_sparql_escape(n)}"@en' for n in names)
    return f"""SELECT ?p ?pLabel ?dob ?img WHERE {{
  VALUES ?name {{ {values} }}
  ?p rdfs:label ?name ; wdt:P27 wd:{citizenship} ; wdt:P106 wd:Q937857 .
  OPTIONAL {{ ?p wdt:P569 ?dob }} OPTIONAL {{ ?p wdt:P18 ?img }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }} }}"""


def _batch_cache_key(names: list[str]) -> str:
    """Content hash of a (sorted) batch of names, so the cache file changes when
    the pool changes -- a positional `batch_<i>.json` key would silently serve
    stale results after the pool is re-fetched/re-filtered."""
    digest = hashlib.sha1("\n".join(sorted(names)).encode("utf-8")).hexdigest()
    return digest[:12]


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
    # Commons rate-limits a run of a few hundred downloads (HTTP 429, seen on
    # the Denmark run 2026-09-21): pace every download and back off on 429
    # rather than losing the portrait
    for attempt in range(4):
        r = requests.get(url + f"?width={MAX_WIDTH}", headers=UA, timeout=60)
        if r.status_code == 429 and attempt < 3:
            time.sleep(20 * (attempt + 1))
            continue
        break
    r.raise_for_status()
    time.sleep(1.0)
    img = Image.open(io.BytesIO(r.content)).convert("RGB")
    if img.width > MAX_WIDTH:
        height = round(img.height * MAX_WIDTH / img.width)
        img = img.resize((MAX_WIDTH, height), Image.LANCZOS)
    img.save(dest, "JPEG", quality=85)


def _fetch_batches(names: list[str]) -> list[dict]:
    """Query Wikidata in batches of BATCH_SIZE names, caching each response to disk.

    Each batch's cache file is keyed by a content hash of its (sorted) names,
    not its position in the list, so a changed pool never silently serves a
    stale response left over from a different set of names at that index.
    """
    bindings: list[dict] = []
    for i in range(0, len(names), BATCH_SIZE):
        batch = names[i : i + BATCH_SIZE]
        cache_path = WIKIDATA_CACHE_DIR / f"batch_{_batch_cache_key(batch)}.json"
        was_cached = cache_path.exists()
        q = sparql_for(batch)
        url = f"{SPARQL_URL}?{urllib.parse.urlencode({'query': q, 'format': 'json'})}"
        text = cached_text(url, cache_path, headers=UA, timeout=120.0)
        bindings.extend(json.loads(text)["results"]["bindings"])
        if not was_cached:
            time.sleep(1)
    return bindings


# --- Wikipedia page-image fallback -------------------------------------------
# Wikidata's P18 is set on a minority of Czech footballers; many more have a
# Czech or English Wikipedia article whose infobox carries a Commons image.
# The article's Wikidata item is checked the same way as the SPARQL match
# (occupation = association football player, birth year when both known).
WIKIPEDIA_CACHE_DIR = config.RAW_DIR / "wikipedia"
WIKIPEDIA_LANGS = ("cs", "en")
FOOTBALLER = "Q937857"


def wikipedia_candidate(api_json: dict, entity_json: dict, born) -> tuple[str, str] | None:
    """(image_url, credit) from a `prop=pageimages|pageprops` response plus the
    page's Wikidata entity, or None when the page is missing, a disambiguation,
    has no image, is not a footballer, or the birth year disagrees."""
    page = next(iter(api_json.get("query", {}).get("pages", {}).values()), {})
    if "missing" in page or "disambiguation" in page.get("pageprops", {}):
        return None
    url = page.get("original", {}).get("source")
    qid = page.get("pageprops", {}).get("wikibase_item")
    if not url or not qid:
        return None
    claims = entity_json.get("entities", {}).get(qid, {}).get("claims", {})
    occupations = {c["mainsnak"]["datavalue"]["value"]["id"] for c in claims.get("P106", [])
                   if "datavalue" in c.get("mainsnak", {})}
    if FOOTBALLER not in occupations:
        return None
    years = [int(c["mainsnak"]["datavalue"]["value"]["time"][1:5]) for c in claims.get("P569", [])
             if "datavalue" in c.get("mainsnak", {})]
    if born is not None and not pd.isna(born) and years and int(born) not in years:
        return None
    return url.split("?")[0], urllib.parse.unquote(url.split("?")[0].rsplit("/", 1)[-1])


def wikipedia_lookup(name: str, born) -> tuple[str, str] | None:
    """Try cs then en Wikipedia for `name`; responses cached under data/raw/wikipedia."""
    WIKIPEDIA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    slug = normalize_name(name).replace(" ", "_")
    for lang in WIKIPEDIA_LANGS:
        params = {"action": "query", "prop": "pageimages|pageprops", "titles": name,
                  "piprop": "original", "redirects": 1, "format": "json"}
        url = f"https://{lang}.wikipedia.org/w/api.php?{urllib.parse.urlencode(params)}"
        cache = WIKIPEDIA_CACHE_DIR / f"{lang}_{slug}.json"
        was_cached = cache.exists()
        api = json.loads(cached_text(url, cache, headers=UA, timeout=30.0))
        page = next(iter(api.get("query", {}).get("pages", {}).values()), {})
        qid = page.get("pageprops", {}).get("wikibase_item")
        entity: dict = {}
        if qid and page.get("original"):
            ecache = WIKIPEDIA_CACHE_DIR / f"entity_{qid}.json"
            entity = json.loads(cached_text(f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json",
                                            ecache, headers=UA, timeout=30.0))
        if not was_cached:
            time.sleep(0.3)
        hit = wikipedia_candidate(api, entity, born)
        if hit:
            return hit
    return None


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--only-with-metrics",
        dest="only_with_metrics",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Restrict the Wikipedia second pass to pool players with metrics "
            "(pool.in_fbref_tables) -- those are the only ones that can appear "
            "on a card or in the player index. Default: on automatically once "
            f"the pool exceeds {ONLY_WITH_METRICS_POOL_THRESHOLD} players; off "
            "for a smaller pool. Pass explicitly to override either way."
        ),
    )
    return p.parse_args(argv)


def _resolve_only_with_metrics(explicit: bool | None, pool_size: int) -> bool:
    """`--only-with-metrics`/`--no-only-with-metrics` wins when given; otherwise
    on automatically once the pool exceeds `ONLY_WITH_METRICS_POOL_THRESHOLD`."""
    return explicit if explicit is not None else pool_size > ONLY_WITH_METRICS_POOL_THRESHOLD


def _gk_relevant_player_keys() -> set[str]:
    """`player_key`s of the home nation's goalkeepers that actually appear on
    the site: the two GK cards (slide 8b) plus everyone in the GK production
    table (`goalkeepers.json`'s `cards` and `production.home` -- both keyed
    off the same >= min_minutes `home_top9` roster `src.goalkeepers` builds
    off of, so this is the full roster, not just the two card picks). Empty
    when `goalkeepers.json` hasn't been built yet (`src.goalkeepers` not run)
    rather than failing the whole photo fetch.
    """
    path = config.PROCESSED_DIR / "goalkeepers.json"
    if not path.exists():
        LOG.warning("photos: %s missing, skipping goalkeeper portraits", path)
        return set()
    gk = json.loads(path.read_text(encoding="utf-8"))
    keys = {c["player_key"] for c in gk.get("cards", [])}
    keys |= {p["player_key"] for p in gk.get("production", {}).get("home", [])}
    return keys


def squad_relevant_player_keys(squads: pd.DataFrame, pool_all: pd.DataFrame, home: str) -> set[str]:
    """`player_key`s of `home`'s `nt_core_event` squad (the site's squad grid,
    Task 25b): `squads`' home-country rows, matched to `pool_all` by
    `normalize_name` (tie-broken by birth year when both are known — the same
    rule `src.squad_lens` uses to match a squad row to an FBref table row). A
    squad player not found in the pool at all (should not happen: the pool is
    built from FBref's own "Players from <nation>" country page, which any
    current international is on) is skipped rather than failing the whole
    photo fetch. Most squad players are already covered by `outfield` in
    `main()`; this closes the gap for a squad goalkeeper who is not on a GK
    card or in the GK production table (`_gk_relevant_player_keys`) and so
    would otherwise never be queried at all -- the same "add the missing
    roster to the lookup list" fix Task 24 made for GK cards.
    """
    home_rows = squads[squads.country == home]
    if home_rows.empty:
        return set()
    norm = pool_all.player.map(normalize_name)
    keys: set[str] = set()
    for r in home_rows.itertuples():
        cand = pool_all[norm == r.player_norm]
        if cand.empty:
            continue
        if pd.notna(r.born) and cand["born"].notna().any():
            born_match = cand[cand.born == r.born]
            if not born_match.empty:
                cand = born_match
        keys.add(str(cand.iloc[0]["player_key"]))
    return keys


def _squad_relevant_player_keys(pool_all: pd.DataFrame) -> set[str]:
    """`squad_relevant_player_keys`, loading `peer_squads.parquet` for `main()`."""
    path = config.PROCESSED_DIR / "peer_squads.parquet"
    if not path.exists():
        LOG.warning("photos: %s missing, skipping squad portraits", path)
        return set()
    return squad_relevant_player_keys(read_parquet(path), pool_all, config.HOME)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO)
    args = _parse_args(argv)
    pool_all = read_parquet(config.PROCESSED_DIR / "pool.parquet")
    # Outfield players (pos_group set) are shown on the site's cards/index;
    # goalkeepers (pos_group is null -- see src.pool.pos_group) are shown
    # too, but only the ones that actually appear on a GK card or in the GK
    # production table (site/goalkeepers.json's `cards` + `production.home`).
    outfield = pool_all[pool_all.pos_group.notna()]
    gk_keys = _gk_relevant_player_keys() | _squad_relevant_player_keys(pool_all)
    gk = pool_all[pool_all.pos_group.isna() & pool_all.player_key.isin(gk_keys)]
    pool = pd.concat([outfield, gk], ignore_index=True)

    only_with_metrics = _resolve_only_with_metrics(args.only_with_metrics, len(pool))

    bindings = _fetch_batches(pool.player.tolist())
    matched = match_images(bindings, pool).drop_duplicates("fbref_id")

    # second pass: Wikipedia infobox images for players Wikidata's P18 missed
    second_pass_pool = pool[~pool.fbref_id.isin(matched.fbref_id)]
    if only_with_metrics:
        excluded = len(second_pass_pool) - int(second_pass_pool.in_fbref_tables.sum())
        second_pass_pool = second_pass_pool[second_pass_pool.in_fbref_tables]
        LOG.info(
            "photos: --only-with-metrics active (pool=%d > %d), skipping Wikipedia "
            "lookup for %d players with no metrics",
            len(pool), ONLY_WITH_METRICS_POOL_THRESHOLD, excluded,
        )
    extra = []
    for r in second_pass_pool.itertuples():
        try:
            hit = wikipedia_lookup(r.player, r.born)
        except Exception as exc:  # one lookup failing must not kill the run
            LOG.warning("%s: wikipedia lookup failed: %s", r.player, exc)
            continue
        if hit:
            extra.append({"fbref_id": r.fbref_id, "player": r.player, "image_url": hit[0], "credit": hit[1]})
    LOG.info("photos: wikidata P18 matched %d, wikipedia page images add %d", len(matched), len(extra))
    matched = pd.concat([matched, pd.DataFrame(extra, columns=matched.columns)], ignore_index=True)

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
    (site_dir / f"players.{config.NATION}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    LOG.info(
        "photos: matched %d, downloaded %d, failed %d, of %d eligible pool players",
        len(matched), downloaded, failed, len(pool),
    )


if __name__ == "__main__":
    main()
