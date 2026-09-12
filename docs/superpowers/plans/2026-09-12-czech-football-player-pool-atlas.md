# Czech Football Player Pool Atlas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the hockey atlas fork into a football report: Czech professional
pool vs nine peer countries, PCA atlases per position group, national-team
flags, photo cards, historical analogs — published bilingual at
`football.datasimply.eu`.

**Architecture:** Same pipeline as hockey (`fetch → pool → features → reduce →
cluster → trajectory → benchmark → analogs → render`), each stage a module
with a `main()` reading/writing parquet under `data/`. The site is generated
from the English render by `site/build.sh` (enrich → Czech via exact-match
pairs → SVG labels → atlas metadata). Fetchers cache raw responses and are
idempotent; the render never touches the network.

**Tech Stack:** Python 3.12, uv, pandas + pyarrow, soccerdata 1.9 (FBref
reader with Cloudflare handling), requests + BeautifulSoup, scikit-learn
(PCA, KMeans), matplotlib (SVG atlases), Jinja2, pytest + ruff. Site: static
HTML/CSS/JS on GitHub Pages.

**Spec:** `docs/superpowers/specs/2026-09-12-czech-football-player-pool-atlas-design.md`

## Global Constraints

- Public data only; no predictions, no selection recommendations — in copy,
  log messages and variable names alike.
- Headline leagues = UEFA ranks 1–9 (2025): ENG, ITA, ESP, GER, FRA, NED,
  POR, BEL, TUR. Peer countries: CZE, SVK, AUT, HUN, POL, HRV, DNK, CHE, NOR.
- Seasons: metrics/atlas/cohorts `2024-2025`; trajectory `2023-2024 → 2024-2025`;
  headline counts and current club `2025-2026`. Season strings are always the
  unambiguous `YYYY-YYYY` form (soccerdata parses `2425` wrongly).
- Feature vector per position group: identical across leagues or the feature
  is dropped (free-tier safe: npG/90, A/90, minutes share, age, cards/90).
- Shrinkage K = 10 in 90-minute units (900 minutes); seed 42 everywhere.
- Every strong claim in the report ends with `*` and has a mono footnote.
- `data/snapshot/` (processed parquet the render needs) is committed.
- Commit after every task; never commit `data/raw/` or secrets.

---

### Task 0: Spike — can we get the data today? (throwaway)

**Files:**
- Create: `scripts/spike_sources.py` (deleted at the end of the task)

**Interfaces:**
- Produces: a written finding in the task's commit message and, if it passes,
  the raw pages saved as test fixtures: `tests/fixtures/fbref_country_cze.html`,
  `tests/fixtures/wikidata_sample.json`.

- [ ] **Step 1: Write the spike script**

```python
"""Throwaway: verify the three data-access assumptions of the spec §8."""
import json, sys, time
import requests
import soccerdata as sd

UA = {"User-Agent": "Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/128 Safari/537.36"}

# 1. soccerdata FBref player table (one league, one season)
fb = sd.FBref(leagues=["ENG-Premier League"], seasons=["2024-2025"])
df = fb.read_player_season_stats(stat_type="standard")
print("FBref rows:", len(df), "cols sample:", list(df.columns)[:8])
cze = df[df[("nation", "")].astype(str).str.contains("CZE", na=False)]
print("CZE in PL 24/25:", cze.index.get_level_values("player").tolist())

# 2. FBref country page (raw HTML via soccerdata's session — Cloudflare-safe)
url = "https://fbref.com/en/country/players/CZE/Czechia-Football-Players"
html = fb.get(url, fb.data_dir / "country_cze.html").read().decode("utf-8")
print("country page bytes:", len(html), "has data-stat=player:", 'data-stat="player"' in html)
open("tests/fixtures/fbref_country_cze.html", "w", encoding="utf-8").write(html)

# 3. Wikidata P18 coverage on 10 Czech internationals
names = ["Patrik Schick", "Tomáš Souček", "Vladimír Coufal", "Adam Hložek", "Ladislav Krejčí",
         "Lukáš Provod", "Václav Černý", "Jindřich Staněk", "Tomáš Chorý", "Matěj Vydra"]
q = """SELECT ?p ?pLabel ?dob ?img WHERE {
  VALUES ?name { %s }
  ?p rdfs:label ?name ; wdt:P27 wd:Q213 ; wdt:P106 wd:Q937857 .
  OPTIONAL { ?p wdt:P569 ?dob } OPTIONAL { ?p wdt:P18 ?img }
  FILTER(LANG(?name) = "en")
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } }""" % " ".join(f'"{n}"@en' for n in names)
r = requests.get("https://query.wikidata.org/sparql", params={"query": q, "format": "json"}, headers=UA, timeout=60)
rows = r.json()["results"]["bindings"]
with_img = {b["pLabel"]["value"] for b in rows if "img" in b}
print("Wikidata hits:", len({b["pLabel"]["value"] for b in rows}), "with image:", len(with_img), sorted(with_img))
json.dump(r.json(), open("tests/fixtures/wikidata_sample.json", "w"), indent=1)
```

- [ ] **Step 2: Run it**

Run: `uv run python scripts/spike_sources.py`
Expected: FBref rows > 500 and at least one CZE player; country page has
`data-stat="player"`; Wikidata image count ≥ 7 of 10.

- [ ] **Step 3: Decide**

If FBref fails: retry with `sd.FBref(..., no_cache=True)`; if Cloudflare still
blocks, copy `auth.py` from `sparta-european-context` and inject the Stathead
cookie (see that repo's STATUS.md). If it still fails, stop and revise the
spec (§8 fallback). If Wikidata < 5/10: photos only for the six showcase
players, sourced by hand with attribution (spec §8).

- [ ] **Step 4: Commit fixtures, delete the script**

```bash
rm scripts/spike_sources.py
git add tests/fixtures/fbref_country_cze.html tests/fixtures/wikidata_sample.json
git commit -m "spike: FBref + country page + Wikidata access verified (fixtures kept)"
```

---

### Task 1: Prune the hockey fork and lay down football config

**Files:**
- Delete: `src/fetch_nhl.py`, `src/fetch_moneypuck.py`, `src/fetch_liiga.py`,
  `src/fetch_shl.py`, `src/fetch_nl.py`, `src/fetch_extraliga.py`,
  `src/fetch_iihf.py`, `src/features_goalies.py`, `src/features_defense.py`,
  `src/playwright_helper.py`, `src/vision_cards.py`, `src/llm_scout.py`,
  `src/crosswalk.py`, `tests/test_crosswalk.py`, `tests/test_extraliga_parser.py`,
  `tests/test_iihf_parser.py`, `tests/test_liiga_parser.py`, `tests/test_fetch_outputs.py`,
  `tests/test_features_forwards.py`, `COVER_LETTER.md`, `FIRST_CALL_PREP.md`,
  `README.cs.md`, `docs/briefs/`, `docs/cards/`, `docs/video_poc_*`,
  `docs/report.pdf`, `docs/*.svg`, `docs/cs/`, `docs/index.html`,
  `docs/atlas_meta.json`, `site/source/index.cs.html`, `site/players.json`,
  `config/nt_veterans.yaml`, `data/seed/*`, `notebooks/*`
- Modify: `pyproject.toml`, `Makefile`, `README.md`, `docs/CNAME`, `.gitignore`
- Create: `config/leagues.yaml`, `config/countries.yaml`, `config/seasons.yaml`,
  `config/feature_definitions.yaml`, `config/cluster_labels.yaml`
- Modify: `src/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `config.leagues() -> dict`, `config.countries() -> dict`,
  `config.seasons() -> dict`, `config.SNAPSHOT_DIR: Path`, constants
  `config.HEADLINE_LEAGUES: list[str]`, `config.PEER_COUNTRIES: list[str]`.

- [ ] **Step 1: Delete hockey-only files**

```bash
git rm -q src/fetch_nhl.py src/fetch_moneypuck.py src/fetch_liiga.py src/fetch_shl.py src/fetch_nl.py \
  src/fetch_extraliga.py src/fetch_iihf.py src/features_goalies.py src/features_defense.py \
  src/playwright_helper.py src/vision_cards.py src/llm_scout.py src/crosswalk.py \
  tests/test_crosswalk.py tests/test_extraliga_parser.py tests/test_iihf_parser.py tests/test_liiga_parser.py \
  tests/test_fetch_outputs.py tests/test_features_forwards.py COVER_LETTER.md FIRST_CALL_PREP.md README.cs.md \
  config/nt_veterans.yaml docs/CNAME
git rm -rq docs/briefs docs/cards docs/cs notebooks data/seed
git rm -q docs/video_poc_* docs/report.pdf docs/*.svg docs/index.html docs/atlas_meta.json site/source/index.cs.html site/players.json
git mv src/features_forwards.py src/features.py
echo "football.datasimply.eu" > docs/CNAME
```

- [ ] **Step 2: Write the configs**

`config/leagues.yaml`:
```yaml
# FBref competitions. `fbref_key` is the soccerdata league key; non-Big-5
# keys are registered into ~/soccerdata/config/league_dict.json by
# src/leagues_setup.py using `comp_id` + `slug` (both readable from the
# competition URL: /en/comps/<comp_id>/<slug>-Stats).
headline:            # UEFA coefficient ranks 1-9, 2025 — none is a peer country
  - ENG-Premier League
  - ITA-Serie A
  - ESP-La Liga
  - GER-Bundesliga
  - FRA-Ligue 1
  - NED-Eredivisie
  - POR-Primeira Liga
  - BEL-Pro League
  - TUR-Süper Lig
domestic: CZE-First League
custom:              # not built into soccerdata; comp_id verified via the country page links
  NED-Eredivisie:     {comp_id: 23, slug: Eredivisie,        country: NED, tier: 1}
  POR-Primeira Liga:  {comp_id: 32, slug: Primeira-Liga,     country: POR, tier: 1}
  BEL-Pro League:     {comp_id: 37, slug: Belgian-Pro-League, country: BEL, tier: 1}
  TUR-Süper Lig:      {comp_id: 26, slug: Super-Lig,         country: TUR, tier: 1}
  CZE-First League:   {comp_id: 66, slug: Czech-First-League, country: CZE, tier: 1}
  GER-2. Bundesliga:  {comp_id: 33, slug: 2-Bundesliga,      country: GER, tier: 2}
peer_domestic:       # tier-1 leagues of the peer countries (exhibit A, route origins)
  SVK-Super Liga:     {comp_id: 39, slug: Slovak-Super-Liga,  country: SVK, tier: 1}
  AUT-Bundesliga:     {comp_id: 56, slug: Austrian-Bundesliga, country: AUT, tier: 1}
  HUN-NB I:           {comp_id: 46, slug: NB-I,               country: HUN, tier: 1}
  POL-Ekstraklasa:    {comp_id: 36, slug: Ekstraklasa,        country: POL, tier: 1}
  CRO-HNL:            {comp_id: 63, slug: Hrvatska-NL,        country: CRO, tier: 1}
  DEN-Superliga:      {comp_id: 50, slug: Danish-Superliga,   country: DEN, tier: 1}
  SUI-Super League:   {comp_id: 57, slug: Swiss-Super-League, country: SUI, tier: 1}
  NOR-Eliteserien:    {comp_id: 28, slug: Eliteserien,        country: NOR, tier: 1}
stepping_stone: [NED-Eredivisie, BEL-Pro League, POR-Primeira Liga, TUR-Süper Lig, GER-2. Bundesliga]
# comp_ids above are best knowledge; Task 2's live smoke verifies each one against
# the page title FBref returns and corrects the yaml before fetching.
# Any further league is added to `custom` when pool discovery (Task 3) finds
# >= 3 Czech players in it; comp_id comes from the discovery output.
min_players_to_fetch: 3
```

`config/countries.yaml`:
```yaml
# Peer set for the per-capita benchmark. Population in millions, Eurostat
# 2024-01-01 estimates (demo_pjan). FBref nation codes are 3-letter.
peers:
  CZE: {name: Czechia,     population_m: 10.90}
  SVK: {name: Slovakia,    population_m: 5.42}
  AUT: {name: Austria,     population_m: 9.16}
  HUN: {name: Hungary,     population_m: 9.58}
  POL: {name: Poland,      population_m: 36.62}
  CRO: {name: Croatia,     population_m: 3.86}
  DEN: {name: Denmark,     population_m: 5.96}
  SUI: {name: Switzerland, population_m: 8.96}
  NOR: {name: Norway,      population_m: 5.55}
# NB: FBref uses CRO/DEN/SUI, not ISO HRV/DNK/CHE. Keep FBref codes here.
```

`config/seasons.yaml`:
```yaml
metrics: "2024-2025"       # atlas, cohorts, sensitivity
previous: "2023-2024"      # trajectory start
current: "2025-2026"       # headline rosters, current club
```

`config/feature_definitions.yaml`:
```yaml
# One vector per position group, identical across leagues (spec §5).
groups: [FW, MF, DF]       # FBref `pos` first token; GK excluded
features:
  - npg_p90        # non-penalty goals per 90
  - ast_p90        # assists per 90
  - min_share      # minutes / (club matches * 90)
  - age            # at season start (Jul 1)
  - cards_p90      # (yellow + 2*red) per 90
min_minutes: 450   # inclusion floor (5 full matches)
phantom_minutes: 900
```

`config/cluster_labels.yaml`: `{}` (filled in Task 7 after clustering; keys
`FW.style.C0` etc.)

- [ ] **Step 3: Write the failing config test**

`tests/test_config.py` (replace file):
```python
from src import config


def test_headline_leagues_are_nine_and_exclude_peers():
    assert len(config.HEADLINE_LEAGUES) == 9
    peer_codes = set(config.countries()["peers"])
    assert not any(l.split("-")[0] in peer_codes for l in config.HEADLINE_LEAGUES)


def test_peer_countries_have_population():
    peers = config.countries()["peers"]
    assert set(peers) == {"CZE", "SVK", "AUT", "HUN", "POL", "CRO", "DEN", "SUI", "NOR"}
    assert all(v["population_m"] > 1 for v in peers.values())


def test_seasons_are_unambiguous():
    for s in config.seasons().values():
        assert len(s) == 9 and s[4] == "-"


def test_snapshot_dir_is_inside_data():
    assert config.SNAPSHOT_DIR.parent == config.DATA_DIR
```

- [ ] **Step 4: Run to verify it fails**

Run: `uv run pytest tests/test_config.py -q`
Expected: FAIL — `AttributeError: module 'src.config' has no attribute 'HEADLINE_LEAGUES'`

- [ ] **Step 5: Update `src/config.py`**

Append after `leagues()`:
```python
SNAPSHOT_DIR: Path = DATA_DIR / "snapshot"


def countries() -> dict[str, Any]:
    return load_yaml("countries.yaml")


def seasons() -> dict[str, str]:
    return load_yaml("seasons.yaml")


def features() -> dict[str, Any]:
    return load_yaml("feature_definitions.yaml")


HEADLINE_LEAGUES: list[str] = list(leagues()["headline"])
DOMESTIC_LEAGUE: str = leagues()["domestic"]
PEER_COUNTRIES: list[str] = list(countries()["peers"])
```
and remove the hockey-only helpers (`league_quality()` stays — Task 5 writes
that file).

- [ ] **Step 6: Update `pyproject.toml` dependencies**

```toml
dependencies = [
  "pandas>=2.2", "pyarrow>=16", "numpy>=1.26", "scikit-learn>=1.5",
  "matplotlib>=3.9", "jinja2>=3.1", "pyyaml>=6", "requests>=2.32",
  "beautifulsoup4>=4.12", "lxml>=5", "soccerdata>=1.9,<2", "unidecode>=1.3",
]
[project.optional-dependencies]
dev = ["pytest>=8", "ruff>=0.5"]
```
Set `name = "czefootball-player-pool-atlas"`, description accordingly.

- [ ] **Step 7: Run tests and lint**

Run: `uv sync && uv run pytest tests/test_config.py -q && uv run ruff check src tests`
Expected: 4 passed; ruff may flag imports of deleted modules in remaining
files (`reduce.py`, `render.py`) — leave those for the tasks that rewrite them,
but delete dead `import` lines now so ruff passes.

- [ ] **Step 8: Update Makefile targets**

Replace the `fetch`/`features` blocks:
```make
fetch:
	$(ACT) python -m src.leagues_setup
	$(ACT) python -m src.fetch_fbref
	$(ACT) python -m src.fetch_elo
	$(ACT) python -m src.fetch_squads
	$(ACT) python -m src.fetch_photos

pool:
	$(ACT) python -m src.pool

features:
	$(ACT) python -m src.features
	$(ACT) python -m src.trajectory

all: fetch pool features reduce render

snapshot:
	mkdir -p data/snapshot && cp data/processed/*.parquet data/snapshot/
```
and in `pages` copy `outputs/index.html` to `site/source/index.en.html`.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "Prune hockey fork; football config (leagues, peers, seasons, features)"
```

---

### Task 2: FBref league player tables (`fetch_fbref.py`)

**Files:**
- Create: `src/leagues_setup.py`, `src/fetch_fbref.py`
- Test: `tests/test_fetch_fbref.py`

**Interfaces:**
- Produces: `data/processed/fbref_players.parquet` with columns
  `league, season, team, player, fbref_id, nation, pos, born, age, mp, min, gls, ast, pk, crdy, crdr`
  (one row per player-team-season), and function
  `normalize_player_table(df: pd.DataFrame, league: str, season: str) -> pd.DataFrame`.
- Consumes: `config.leagues()`, `config.seasons()`.

- [ ] **Step 1: Failing test for the normaliser**

`tests/test_fetch_fbref.py`:
```python
import pandas as pd
from src.fetch_fbref import normalize_player_table


def _soccerdata_like():
    cols = pd.MultiIndex.from_tuples([
        ("nation", ""), ("pos", ""), ("age", ""), ("born", ""),
        ("Playing Time", "MP"), ("Playing Time", "Min"),
        ("Performance", "Gls"), ("Performance", "Ast"), ("Performance", "PK"),
        ("Performance", "CrdY"), ("Performance", "CrdR"),
    ])
    idx = pd.MultiIndex.from_tuples(
        [("ENG-Premier League", "2425", "West Ham", "Tomáš Souček"),
         ("ENG-Premier League", "2425", "Arsenal", "Bukayo Saka")],
        names=["league", "season", "team", "player"])
    data = [["cz CZE", "MF", "29-200", 1995, 38, 3200, 5, 2, 0, 6, 0],
            ["eng ENG", "FW,MF", "23-100", 2001, 35, 2900, 12, 10, 1, 2, 0]]
    return pd.DataFrame(data, index=idx, columns=cols)


def test_normalize_flattens_and_types():
    out = normalize_player_table(_soccerdata_like(), "ENG-Premier League", "2024-2025")
    assert list(out.columns) == ["league", "season", "team", "player", "fbref_id", "nation",
                                 "pos", "born", "age", "mp", "min", "gls", "ast", "pk", "crdy", "crdr"]
    row = out[out.player == "Tomáš Souček"].iloc[0]
    assert row.nation == "CZE" and row.pos == "MF" and row.born == 1995 and row["min"] == 3200
    assert out.season.unique().tolist() == ["2024-2025"]


def test_pos_takes_first_token():
    out = normalize_player_table(_soccerdata_like(), "ENG-Premier League", "2024-2025")
    assert out[out.player == "Bukayo Saka"].iloc[0].pos == "FW"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_fetch_fbref.py -q`
Expected: FAIL — `ModuleNotFoundError: src.fetch_fbref`

- [ ] **Step 3: `src/leagues_setup.py`**

```python
"""Register custom FBref competitions with soccerdata (merge, never overwrite).

soccerdata knows the Big-5 out of the box; everything else must be declared in
~/soccerdata/config/league_dict.json. Entries come from config/leagues.yaml.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from src import config

LOG = logging.getLogger(__name__)
LEAGUE_DICT = Path.home() / "soccerdata" / "config" / "league_dict.json"


def entries() -> dict[str, dict]:
    out = {}
    for key, meta in {**config.leagues()["custom"], **config.leagues().get("peer_domestic", {})}.items():
        out[key] = {"FBref": f"{meta['slug']}", "season_start": "Jul", "season_end": "Jun"}
        out[key]["FBref"] = meta["slug"].replace("-", " ")
        out[key]["FBref_id"] = meta["comp_id"]  # soccerdata >=1.9 accepts an explicit id
    return out


def install() -> None:
    LEAGUE_DICT.parent.mkdir(parents=True, exist_ok=True)
    current = json.loads(LEAGUE_DICT.read_text()) if LEAGUE_DICT.exists() else {}
    current.update(entries())
    LEAGUE_DICT.write_text(json.dumps(current, indent=2, ensure_ascii=False))
    LOG.info("registered %d custom leagues in %s", len(entries()), LEAGUE_DICT)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    install()
```
(The exact `league_dict.json` schema is the one `sparta-european-context/src/leagues_setup.py`
used successfully in May — copy that file's `entries()` body verbatim if it
differs from the above; that repo is the authority.)

- [ ] **Step 4: `src/fetch_fbref.py`**

```python
"""Player season tables from FBref via soccerdata, normalised to a flat frame.

Output: data/processed/fbref_players.parquet (one row per player-team-season).
Raw HTML is cached by soccerdata itself under ~/soccerdata/data/FBref.
"""
from __future__ import annotations

import logging

import pandas as pd
import soccerdata as sd

from src import config
from src.utils import write_parquet

LOG = logging.getLogger(__name__)
COLS = ["league", "season", "team", "player", "fbref_id", "nation", "pos", "born", "age",
        "mp", "min", "gls", "ast", "pk", "crdy", "crdr"]


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
        "fbref_id": df.index.get_level_values("player").map(str),  # replaced below if ids present
        "nation": _col(df, ("nation", "")).astype(str).str.split().str[-1].values,
        "pos": _col(df, ("pos", "")).astype(str).str.split(",").str[0].values,
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
    if "id" in idx.columns:            # soccerdata >= 1.8 exposes FBref player ids in the index
        out["fbref_id"] = idx["id"].values
    return out[COLS]


def fetch_league(league: str, season: str) -> pd.DataFrame:
    fb = sd.FBref(leagues=[league], seasons=[season])
    raw = fb.read_player_season_stats(stat_type="standard")
    return normalize_player_table(raw, league, season)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
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
    write_parquet(pd.concat(frames, ignore_index=True), config.PROCESSED_DIR / "fbref_players.parquet")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_fetch_fbref.py -q`
Expected: 2 passed.

- [ ] **Step 6: Live smoke (one league) and commit**

Run: `uv run python -c "from src.fetch_fbref import fetch_league; print(fetch_league('ENG-Premier League','2024-2025').head())"`
Expected: a frame with ≈ 550 rows; `fbref_id` populated (if it equals the
name, note it — Task 3 then maps ids from the country page).

```bash
git add src/leagues_setup.py src/fetch_fbref.py tests/test_fetch_fbref.py
git commit -m "FBref player tables via soccerdata, normalised"
```

---

### Task 3: Pool discovery from the FBref country page (`pool.py`)

**Files:**
- Create: `src/pool.py`
- Test: `tests/test_pool.py` (uses `tests/fixtures/fbref_country_cze.html` from Task 0)

**Interfaces:**
- Produces: `parse_country_page(html: str) -> pd.DataFrame` with columns
  `fbref_id, player, born, pos, club, comp_id, comp_name`;
  `build_pool() -> pd.DataFrame` writing `data/processed/pool.parquet` with
  columns `fbref_id, player, born, pos_group, club_current, comp_id, comp_name,
  in_fbref_tables (bool)`; `discover_missing_leagues() -> list[dict]`.

- [ ] **Step 1: Failing parser test**

```python
from pathlib import Path
from src.pool import parse_country_page, pos_group

FIX = Path(__file__).parent / "fixtures" / "fbref_country_cze.html"


def test_country_page_yields_players_with_ids():
    df = parse_country_page(FIX.read_text(encoding="utf-8"))
    assert len(df) > 100
    assert df.fbref_id.str.len().eq(8).all()
    assert {"player", "born", "pos", "club", "comp_id", "comp_name"} <= set(df.columns)
    assert (df.player == "Patrik Schick").any()


def test_pos_group_mapping():
    assert pos_group("FW,MF") == "FW"
    assert pos_group("DF") == "DF"
    assert pos_group("GK") is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_pool.py -q` → FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/pool.py`**

```python
"""Czech-eligible pool: discovery (FBref country page) ∪ league tables.

FBref rows carry `data-stat` attributes, which is the only stable hook — column
order and headers change, `data-stat` does not. Tables sit inside HTML comments
on some pages; we un-comment before parsing.
"""
from __future__ import annotations

import logging
import re

import pandas as pd
from bs4 import BeautifulSoup

from src import config
from src.utils import read_parquet, write_parquet

LOG = logging.getLogger(__name__)
COUNTRY_URL = "https://fbref.com/en/country/players/CZE/Czechia-Football-Players"


def pos_group(pos: str | None) -> str | None:
    first = (pos or "").split(",")[0].strip()
    return first if first in ("FW", "MF", "DF") else None


def _uncomment(html: str) -> str:
    return re.sub(r"<!--|-->", "", html)


def parse_country_page(html: str) -> pd.DataFrame:
    soup = BeautifulSoup(_uncomment(html), "lxml")
    rows = []
    for tr in soup.select("table tbody tr"):
        cell = tr.find(attrs={"data-stat": "player"})
        if cell is None or not cell.find("a"):
            continue
        href = cell.find("a")["href"]                      # /en/players/<id>/<Name>
        pid = href.split("/")[3]
        club_cell = tr.find(attrs={"data-stat": "team"}) or tr.find(attrs={"data-stat": "club"})
        comp_cell = tr.find(attrs={"data-stat": "comp_level"}) or tr.find(attrs={"data-stat": "league"})
        comp_id, comp_name = None, None
        if comp_cell is not None and comp_cell.find("a"):
            m = re.search(r"/comps/(\d+)/", comp_cell.find("a")["href"])
            comp_id = int(m.group(1)) if m else None
            comp_name = comp_cell.get_text(strip=True)
        born_cell = tr.find(attrs={"data-stat": "birth_year"}) or tr.find(attrs={"data-stat": "born"})
        pos_cell = tr.find(attrs={"data-stat": "position"}) or tr.find(attrs={"data-stat": "pos"})
        rows.append({
            "fbref_id": pid,
            "player": cell.get_text(strip=True),
            "born": pd.to_numeric(born_cell.get_text(strip=True) if born_cell else None, errors="coerce"),
            "pos": pos_cell.get_text(strip=True) if pos_cell else "",
            "club": club_cell.get_text(strip=True) if club_cell else "",
            "comp_id": comp_id,
            "comp_name": comp_name,
        })
    df = pd.DataFrame(rows).drop_duplicates("fbref_id")
    df["born"] = df["born"].astype("Int64")
    return df


def fetch_country_page() -> str:
    import soccerdata as sd
    fb = sd.FBref(leagues=["ENG-Premier League"], seasons=[config.seasons()["current"]])
    return fb.get(COUNTRY_URL, fb.data_dir / "country_cze.html").read().decode("utf-8")


def discover_missing_leagues(discovery: pd.DataFrame) -> list[dict]:
    """Competitions with >= min_players_to_fetch Czech players not yet in config."""
    cfg = config.leagues()
    known = {v["comp_id"] for v in cfg["custom"].values()} | {9, 11, 12, 20, 13}  # Big-5 ids
    counts = discovery.dropna(subset=["comp_id"]).groupby(["comp_id", "comp_name"]).size()
    return [{"comp_id": int(cid), "comp_name": name, "players": int(n)}
            for (cid, name), n in counts.items() if n >= cfg["min_players_to_fetch"] and cid not in known]


def build_pool() -> pd.DataFrame:
    discovery = parse_country_page(fetch_country_page())
    tables = read_parquet(config.PROCESSED_DIR / "fbref_players.parquet")
    cze_tables = tables[tables.nation == "CZE"]
    ids_in_tables = set(cze_tables.fbref_id)
    pool = discovery.copy()
    pool["pos_group"] = pool["pos"].map(pos_group)
    pool["in_fbref_tables"] = pool.fbref_id.isin(ids_in_tables)
    pool = pool.rename(columns={"club": "club_current"})
    missing = discover_missing_leagues(discovery)
    if missing:
        LOG.warning("leagues with Czech players not yet fetched: %s", missing)
    write_parquet(pool, config.PROCESSED_DIR / "pool.parquet")
    LOG.info("pool: %d players, %d with metrics", len(pool), pool.in_fbref_tables.sum())
    return pool


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    build_pool()


if __name__ == "__main__":
    main()
```
If the fixture's `data-stat` names differ from the alternatives tried above,
read them from the fixture (`grep -o 'data-stat="[a-z_]*"' tests/fixtures/fbref_country_cze.html | sort -u`)
and adjust the `find(attrs=...)` names — the test pins the contract, not the names.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_pool.py -q` → 2 passed.

- [ ] **Step 5: Run discovery live, extend `config/leagues.yaml`**

Run: `uv run python -m src.pool`
Expected: log line `pool: N players` and possibly a warning listing leagues
with ≥ 3 Czech players not yet in config. Add each of those to
`config.leagues.custom` (comp_id from the log, slug from the FBref URL), rerun
`make fetch` for the new leagues, rerun `python -m src.pool`.

- [ ] **Step 6: Commit**

```bash
git add src/pool.py tests/test_pool.py config/leagues.yaml
git commit -m "Pool discovery from FBref country page; missing-league report"
```

---

### Task 4: National-team flags from Wikipedia (`fetch_squads.py`)

**Files:**
- Create: `src/fetch_squads.py`, `config/squads.yaml`
- Test: `tests/test_fetch_squads.py`, fixture `tests/fixtures/wiki_squad_euro2024.html`

**Interfaces:**
- Produces: `data/processed/nt_flags.parquet` with columns
  `player_norm, player, born, team (A|U21), event, year`; helper
  `normalize_name(s: str) -> str` (ASCII, lowercase, single spaces).
- Consumed by Task 6 (`features.py`) to set `nt_flag` and `nt_events`.

- [ ] **Step 1: Config**

`config/squads.yaml`:
```yaml
# Wikipedia pages with a Czech squad table (wikitable with "Player" and "Date of birth" columns).
events:
  - {team: A,   event: "UEFA Euro 2024",                  year: 2024, url: "https://en.wikipedia.org/wiki/UEFA_Euro_2024_squads", section: "Czech Republic"}
  - {team: A,   event: "2024–25 Nations League",          year: 2025, url: "https://en.wikipedia.org/wiki/Czech_Republic_national_football_team", section: "Current squad"}
  - {team: A,   event: "2026 World Cup qualification",    year: 2025, url: "https://en.wikipedia.org/wiki/Czech_Republic_national_football_team", section: "Recent call-ups"}
  - {team: U21, event: "UEFA European Under-21 Championship 2025", year: 2025, url: "https://en.wikipedia.org/wiki/2025_UEFA_European_Under-21_Championship_squads", section: "Czech Republic"}
```

- [ ] **Step 2: Save a fixture and write the failing test**

Run once: `curl -sA "Mozilla/5.0" "https://en.wikipedia.org/wiki/UEFA_Euro_2024_squads" > tests/fixtures/wiki_squad_euro2024.html`

```python
from pathlib import Path
from src.fetch_squads import parse_squad_section, normalize_name

FIX = Path(__file__).parent / "fixtures" / "wiki_squad_euro2024.html"


def test_normalize_name():
    assert normalize_name("Tomáš  Souček") == "tomas soucek"


def test_parse_czech_euro2024_squad():
    df = parse_squad_section(FIX.read_text(encoding="utf-8"), section="Czech Republic")
    assert 23 <= len(df) <= 26
    assert (df.player_norm == "patrik schick").any()
    assert df.born.between(1985, 2006).all()
```

- [ ] **Step 3: Run to verify it fails** → `ModuleNotFoundError`.

- [ ] **Step 4: Implement**

```python
"""National-team call-ups (A + U21) from Wikipedia squad tables -> nt_flags.parquet."""
from __future__ import annotations

import logging
import re

import pandas as pd
from bs4 import BeautifulSoup
from unidecode import unidecode

from src import config
from src.utils import http_get, write_parquet

LOG = logging.getLogger(__name__)


def normalize_name(s: str) -> str:
    return re.sub(r"\s+", " ", unidecode(s or "").lower()).strip()


def _birth_year(text: str) -> int | None:
    m = re.search(r"(19|20)\d{2}", text or "")
    return int(m.group(0)) if m else None


def parse_squad_section(html: str, section: str) -> pd.DataFrame:
    """Find the heading whose text starts with `section`, take the first wikitable after it."""
    soup = BeautifulSoup(html, "lxml")
    heading = next((h for h in soup.find_all(["h2", "h3", "h4"]) if h.get_text(strip=True).startswith(section)), None)
    if heading is None:
        raise ValueError(f"section {section!r} not found")
    table = heading.find_next("table", class_=re.compile("wikitable"))
    rows = []
    for tr in table.select("tr"):
        cells = tr.find_all(["td", "th"])
        texts = [c.get_text(" ", strip=True) for c in cells]
        if len(texts) < 4:
            continue
        name_cell = next((c for c in cells if c.find("a") and c.find("a").get("title")), None)
        dob = next((t for t in texts if re.search(r"\(\d{4}-\d{2}-\d{2}\)|\d{1,2} \w+ (19|20)\d{2}", t)), None)
        if name_cell is None or dob is None:
            continue
        name = name_cell.find("a").get_text(strip=True)
        rows.append({"player": name, "player_norm": normalize_name(name), "born": _birth_year(dob)})
    return pd.DataFrame(rows).drop_duplicates("player_norm")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    frames = []
    for ev in config.load_yaml("squads.yaml")["events"]:
        html = http_get(ev["url"], cache_key=f"wiki_{ev['year']}_{ev['team']}_{normalize_name(ev['event']).replace(' ', '_')}")
        df = parse_squad_section(html, ev["section"])
        df["team"], df["event"], df["year"] = ev["team"], ev["event"], ev["year"]
        frames.append(df)
        LOG.info("%s %s: %d players", ev["team"], ev["event"], len(df))
    write_parquet(pd.concat(frames, ignore_index=True), config.PROCESSED_DIR / "nt_flags.parquet")


if __name__ == "__main__":
    main()
```
(`src/utils.http_get` already exists from hockey; check its signature —
`http_get(url, cache_key=...)` — and adapt the call if it differs.)

- [ ] **Step 5: Run tests, then live run; commit**

Run: `uv run pytest tests/test_fetch_squads.py -q && uv run python -m src.fetch_squads`
Expected: 2 passed; four log lines with 20–40 players each.

```bash
git add src/fetch_squads.py config/squads.yaml tests/test_fetch_squads.py tests/fixtures/wiki_squad_euro2024.html
git commit -m "National-team flags from Wikipedia squad tables"
```

---

### Task 5: League multipliers from ClubElo (`fetch_elo.py`)

**Files:**
- Create: `src/fetch_elo.py`
- Test: `tests/test_fetch_elo.py`
- Produces: `config/league_quality.yaml` (generated, committed) with
  `multipliers: {<league key>: float}` and `source:` line; function
  `league_multipliers(elo: pd.DataFrame, league_map: dict[str, tuple[str, int]]) -> dict[str, float]`.

- [ ] **Step 1: Failing test**

```python
import pandas as pd
from src.fetch_elo import league_multipliers


def test_multipliers_scale_strongest_to_one():
    elo = pd.DataFrame({
        "Club": ["A", "B", "C", "D"], "Country": ["ENG", "ENG", "CZE", "CZE"],
        "Level": [1, 1, 1, 1], "Elo": [1900, 1800, 1500, 1400]})
    m = league_multipliers(elo, {"ENG-Premier League": ("ENG", 1), "CZE-First League": ("CZE", 1)})
    assert m["ENG-Premier League"] == 1.0
    assert 0.5 < m["CZE-First League"] < 0.9
```

- [ ] **Step 2: Run to verify it fails** → `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
"""League quality multipliers from ClubElo (api.clubelo.com/<date>).

multiplier(league) = exp((mean_elo(league) - mean_elo(strongest)) / 400)
i.e. the Elo win-odds scale, so a 120-point gap ≈ 0.74. Strongest = 1.00.
"""
from __future__ import annotations

import logging
import math

import pandas as pd
import yaml

from src import config
from src.utils import http_get

LOG = logging.getLogger(__name__)


def league_multipliers(elo: pd.DataFrame, league_map: dict[str, tuple[str, int]]) -> dict[str, float]:
    means = {}
    for key, (country, level) in league_map.items():
        sub = elo[(elo.Country == country) & (elo.Level == level)]
        if sub.empty:
            LOG.warning("no ClubElo rows for %s (%s L%d)", key, country, level)
            continue
        means[key] = float(sub.Elo.mean())
    top = max(means.values())
    return {k: round(math.exp((v - top) / 400), 3) for k, v in means.items()}


def _league_map() -> dict[str, tuple[str, int]]:
    cfg = config.leagues()
    big5 = {"ENG-Premier League": ("ENG", 1), "ITA-Serie A": ("ITA", 1), "ESP-La Liga": ("ESP", 1),
            "GER-Bundesliga": ("GER", 1), "FRA-Ligue 1": ("FRA", 1)}
    custom = {k: (v["country"], v["tier"]) for k, v in cfg["custom"].items()}
    return {**big5, **custom}


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    date = config.seasons()["metrics"].split("-")[1] + "-06-01"   # season end
    csv = http_get(f"http://api.clubelo.com/{date}", cache_key=f"clubelo_{date}")
    from io import StringIO
    elo = pd.read_csv(StringIO(csv))
    m = league_multipliers(elo, _league_map())
    out = {"source": f"ClubElo {date}, league mean of tier clubs, exp(dElo/400), strongest = 1.00",
           "multipliers": m}
    (config.CONFIG_DIR / "league_quality.yaml").write_text(yaml.safe_dump(out, sort_keys=False, allow_unicode=True))
    LOG.info("multipliers: %s", m)


if __name__ == "__main__":
    main()
```
ClubElo country codes are 3-letter but not always ISO (`ENG`, `GER`, `NED`,
`POR`, `BEL`, `TUR`, `CZE`); verify against the CSV on the live run and fix
`config/leagues.yaml` `country` values if they differ.

- [ ] **Step 4: Tests, live run, commit**

Run: `uv run pytest tests/test_fetch_elo.py -q && uv run python -m src.fetch_elo && cat config/league_quality.yaml`
Expected: 1 passed; a yaml with ≈ 10–15 leagues, ENG = 1.0, CZE ≈ 0.55–0.7.

```bash
git add src/fetch_elo.py tests/test_fetch_elo.py config/league_quality.yaml
git commit -m "League multipliers derived from ClubElo"
```

---

### Task 6: Features per position group (`features.py`)

**Files:**
- Modify: `src/features.py` (was `features_forwards.py`; rewrite the body,
  keep the module docstring style)
- Test: `tests/test_features.py`

**Interfaces:**
- Produces: `data/processed/features_{FW,MF,DF}.parquet` with columns
  `fbref_id, player, season, league, team, nation, born, age, pos_group,
  min, mp, npg, ast, cards, npg_p90, ast_p90, min_share, cards_p90,
  <feature>_shrunk, <feature>_quality, <feature>_z, league_multiplier,
  czech_eligible, nt_flag, nt_events`; functions
  `per90(df) -> df`, `bayesian_shrink(df, k_minutes=900) -> df`,
  `add_quality(df) -> df`, `zscore(df, cols) -> df`.

- [ ] **Step 1: Failing tests**

```python
import pandas as pd
from src.features import per90, bayesian_shrink, add_quality


def _toy():
    return pd.DataFrame({
        "fbref_id": ["a", "b", "c"], "league": ["L", "L", "L"], "team": ["T", "T", "U"],
        "min": [2700, 90, 1800], "mp": [30, 1, 20], "gls": [10, 1, 4], "pk": [2, 0, 0],
        "ast": [5, 0, 6], "crdy": [3, 0, 8], "crdr": [0, 0, 1], "team_matches": [34, 34, 34]})


def test_per90_and_min_share():
    out = per90(_toy())
    a = out[out.fbref_id == "a"].iloc[0]
    assert abs(a.npg_p90 - (8 / 30)) < 1e-9
    assert abs(a.min_share - 2700 / (34 * 90)) < 1e-9
    assert abs(out[out.fbref_id == "c"].iloc[0].cards_p90 - (10 / 20)) < 1e-9


def test_shrink_pulls_small_sample_to_league_median():
    out = bayesian_shrink(per90(_toy()), k_minutes=900)
    b = out[out.fbref_id == "b"].iloc[0]          # 1 goal in 90 min: raw 1.0 p90
    assert b.npg_p90_shrunk < 0.5
    a = out[out.fbref_id == "a"].iloc[0]
    assert abs(a.npg_p90_shrunk - a.npg_p90) < 0.05  # 2700 min barely moves


def test_quality_multiplies_by_league(monkeypatch):
    from src import config
    monkeypatch.setattr(config, "league_quality", lambda: {"multipliers": {"L": 0.5}})
    out = add_quality(bayesian_shrink(per90(_toy())))
    a = out[out.fbref_id == "a"].iloc[0]
    assert abs(a.npg_p90_quality - a.npg_p90_shrunk * 0.5) < 1e-9
```

- [ ] **Step 2: Run to verify it fails** → `ImportError: cannot import name 'per90'`.

- [ ] **Step 3: Rewrite `src/features.py`**

```python
"""Per-90 features, Bayesian shrinkage and league-quality projection per position group.

Reads:  data/processed/fbref_players.parquet, pool.parquet, nt_flags.parquet
Writes: data/processed/features_FW.parquet, features_MF.parquet, features_DF.parquet

Rates are per 90 minutes; shrinkage uses K = 900 phantom minutes:
    shrunk = (count + K/90 * league_median_p90) / (minutes/90 + K/90)
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from src import config
from src.fetch_squads import normalize_name
from src.utils import read_parquet, write_parquet

LOG = logging.getLogger(__name__)
FEATURES = ["npg_p90", "ast_p90", "min_share", "age", "cards_p90"]
RATE_FEATURES = {"npg_p90": "npg", "ast_p90": "ast", "cards_p90": "cards"}


def per90(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["npg"] = out["gls"] - out["pk"]
    out["cards"] = out["crdy"] + 2 * out["crdr"]
    n90 = out["min"] / 90.0
    for feat, cnt in RATE_FEATURES.items():
        out[feat] = np.where(n90 > 0, out[cnt] / n90, np.nan)
    out["min_share"] = out["min"] / (out["team_matches"] * 90.0)
    return out


def bayesian_shrink(df: pd.DataFrame, k_minutes: int = 900) -> pd.DataFrame:
    out = df.copy()
    k90 = k_minutes / 90.0
    for feat, cnt in RATE_FEATURES.items():
        out[f"{feat}_shrunk"] = np.nan
        for league, sub in out.groupby("league"):
            well = sub[sub["min"] >= k_minutes]
            med = float(well[feat].median()) if len(well) else float(sub[feat].median())
            mask = out["league"] == league
            out.loc[mask, f"{feat}_shrunk"] = (out.loc[mask, cnt] + k90 * med) / (out.loc[mask, "min"] / 90.0 + k90)
    out["min_share_shrunk"] = out["min_share"]
    if "age" in out.columns:
        out["age_shrunk"] = out["age"]
    return out


def add_quality(df: pd.DataFrame) -> pd.DataFrame:
    mult = config.league_quality()["multipliers"]
    out = df.copy()
    out["league_multiplier"] = out["league"].map(mult).astype(float)
    for feat in ("npg_p90", "ast_p90"):
        out[f"{feat}_quality"] = out[f"{feat}_shrunk"] * out["league_multiplier"]
    for feat in ("min_share", "age", "cards_p90"):      # not production: unscaled
        if f"{feat}_shrunk" in out.columns:
            out[f"{feat}_quality"] = out[f"{feat}_shrunk"]
    return out


def zscore(df: pd.DataFrame, cols) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        x = out[c].astype(float)
        sd = x.std()
        out[f"{c}_z"] = 0.0 if not np.isfinite(sd) or sd == 0 else (x - x.mean()) / sd
    return out


def _team_matches(tables: pd.DataFrame) -> pd.DataFrame:
    tm = tables.groupby(["league", "season", "team"])["mp"].max().rename("team_matches").reset_index()
    return tables.merge(tm, on=["league", "season", "team"], how="left")


def _attach_flags(df: pd.DataFrame) -> pd.DataFrame:
    pool = read_parquet(config.PROCESSED_DIR / "pool.parquet")
    nt = read_parquet(config.PROCESSED_DIR / "nt_flags.parquet")
    out = df.copy()
    out["czech_eligible"] = out["nation"].eq("CZE") | out["fbref_id"].isin(pool.fbref_id)
    out["player_norm"] = out["player"].map(normalize_name)
    events = nt.groupby("player_norm")["event"].agg(lambda s: " · ".join(sorted(set(s))))
    out["nt_events"] = out["player_norm"].map(events).fillna("")
    out["nt_flag"] = out["nt_events"].ne("")
    return out.drop(columns=["player_norm"])


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    cfg = config.features()
    tables = read_parquet(config.PROCESSED_DIR / "fbref_players.parquet")
    tables = tables[tables.season.isin([config.seasons()["previous"], config.seasons()["metrics"]])]
    tables = _team_matches(tables)
    tables["pos_group"] = tables["pos"].where(tables["pos"].isin(cfg["groups"]))
    tables = tables.dropna(subset=["pos_group"])
    tables = tables[tables["min"] >= cfg["min_minutes"]]
    for group in cfg["groups"]:
        sub = tables[tables.pos_group == group]
        sub = zscore(add_quality(bayesian_shrink(per90(sub), cfg["phantom_minutes"])),
                     [f"{f}_shrunk" for f in FEATURES] + [f"{f}_quality" for f in FEATURES])
        sub = _attach_flags(sub)
        write_parquet(sub, config.PROCESSED_DIR / f"features_{group}.parquet")
        LOG.info("%s: %d player-seasons, %d Czech", group, len(sub), sub.czech_eligible.sum())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Tests, run on real data, commit**

Run: `uv run pytest tests/test_features.py -q && uv run python -m src.features`
Expected: 3 passed; three log lines with thousands of player-seasons and
dozens of Czech rows each.

```bash
git add src/features.py tests/test_features.py
git commit -m "Per-90 features, shrinkage and quality projection per position group"
```

---

### Task 7: Reduce, cluster, trajectory on the new columns

**Files:**
- Modify: `src/reduce.py`, `src/cluster.py`, `src/trajectory.py`, `config/cluster_labels.yaml`
- Test: `tests/test_reduce.py`

**Interfaces:**
- `reduce.reduce_group(df: pd.DataFrame, group: str) -> tuple[coords, loadings]`
  writing `coords_{group}.parquet` (columns `fbref_id, player, season, league, team,
  born, pos_group, czech_eligible, nt_flag, min, pc1_style, pc2_style, pc1_quality, pc2_quality`)
  and `pca_loadings.parquet`; `cluster.py` adds `cluster_style, cluster_quality`;
  `trajectory.py` writes `trajectory_{group}.parquet` with
  `fbref_id, player, league, min_prev, min_curr, npg_ast_quality_prev, npg_ast_quality_curr, delta, direction`.

- [ ] **Step 1: Failing test**

```python
import numpy as np, pandas as pd
from src.reduce import reduce_group


def test_reduce_group_returns_two_projections():
    rng = np.random.default_rng(42)
    n = 60
    df = pd.DataFrame({"fbref_id": [f"p{i}" for i in range(n)], "player": "x", "season": "2024-2025",
                       "league": "L", "team": "T", "born": 1998, "pos_group": "FW",
                       "czech_eligible": False, "nt_flag": False, "min": 1500})
    for f in ["npg_p90", "ast_p90", "min_share", "age", "cards_p90"]:
        df[f"{f}_shrunk"] = rng.normal(size=n); df[f"{f}_quality"] = rng.normal(size=n)
        df[f"{f}_shrunk_z"] = df[f"{f}_shrunk"]; df[f"{f}_quality_z"] = df[f"{f}_quality"]
    coords, loadings = reduce_group(df, "FW")
    assert {"pc1_style", "pc2_style", "pc1_quality", "pc2_quality"} <= set(coords.columns)
    assert len(coords) == n and loadings["projection"].nunique() == 2
```

- [ ] **Step 2: Run to verify it fails** → `ImportError: reduce_group`.

- [ ] **Step 3: Edit `src/reduce.py`**

Rename `reduce_position` → `reduce_group`; in `_build_matrix` use the columns
`[f"{f}_{suffix}_z" for f in features.FEATURES]` (import `FEATURES` from
`src.features`); replace `meta_cols` with
`["fbref_id", "player", "season", "league", "team", "born", "pos_group", "czech_eligible", "nt_flag", "min"]`;
rename output columns from `pc1_style`… as already used in hockey (check
`_reduce_one` — hockey names are `pc1_style`, keep them). In `main()` loop over
`config.features()["groups"]`, read `features_{group}.parquet`, write
`coords_{group}.parquet`; concatenate loadings to `pca_loadings.parquet` with a
`position` column equal to the group.

- [ ] **Step 4: Edit `src/cluster.py`**

Same loop; `select_k` unchanged (silhouette over 3..6); write clusters back
into `coords_{group}.parquet` as `cluster_style`, `cluster_quality`. Then run
`uv run python -m src.reduce && uv run python -m src.cluster` and **write
`config/cluster_labels.yaml` by reading each cluster's medians**:

```bash
uv run python - <<'EOF'
import pandas as pd
for g in ["FW","MF","DF"]:
    c = pd.read_parquet(f"data/processed/coords_{g}.parquet").merge(
        pd.read_parquet(f"data/processed/features_{g}.parquet")[["fbref_id","season","npg_p90_quality","ast_p90_quality","min_share","age","cards_p90"]],
        on=["fbref_id","season"])
    for proj in ["style","quality"]:
        print(g, proj); print(c.groupby(f"cluster_{proj}")[["npg_p90_quality","ast_p90_quality","min_share","age","cards_p90"]].median().round(2))
EOF
```
Label each cluster in plain words (e.g. `FW.style.C0: "High-volume scorers"`),
descriptive of the medians, never evaluative. Format:
```yaml
FW: {style: {C0: "...", C1: "..."}, quality: {C0: "...", ...}}
MF: {...}
DF: {...}
```

- [ ] **Step 5: Edit `src/trajectory.py`**

Replace the GP filter with `min >= 900` in both seasons
(`config.seasons()["previous"]`, `["metrics"]`), the metric with
`npg_p90_quality + ast_p90_quality`, direction thresholds ±0.05 per 90
(`improving` / `stable` / `declining`); loop over groups; write
`trajectory_{group}.parquet`.

- [ ] **Step 6: Run everything, commit**

Run: `uv run pytest -q && uv run python -m src.trajectory`
Expected: all tests pass; three trajectory files with ≥ 30 rows each for the
whole corpus (Czech subset may be small — that is a finding, not a bug).

```bash
git add src/reduce.py src/cluster.py src/trajectory.py tests/test_reduce.py config/cluster_labels.yaml
git commit -m "PCA, clustering and trajectories per position group"
```

---

### Task 8: Per-capita benchmark and cohort gaps (`international_benchmark.py`)

**Files:**
- Modify: `src/international_benchmark.py` (rewrite; keep `render_cohort_heatmap` styling)
- Test: `tests/test_benchmark.py`

**Interfaces:**
- Produces: `per_capita(tables, peers, headline_leagues, season) -> pd.DataFrame`
  (`country, name, n_players, population_m, per_million, rank`),
  `cohort_table(features_by_group, peers) -> pd.DataFrame`
  (`country, pos_group, cohort, n, median_npg_ast_p90`), files
  `data/processed/per_capita.parquet`, `cohorts.parquet`,
  `outputs/intl_cohort_heatmap.svg`, `outputs/benchmark_narrative.md`.

- [ ] **Step 1: Failing test**

```python
import pandas as pd
from src.international_benchmark import per_capita, assign_cohort


def test_per_capita_counts_distinct_players_in_headline_leagues():
    tables = pd.DataFrame({
        "fbref_id": ["a", "a", "b", "c", "d"], "nation": ["CZE", "CZE", "CZE", "DEN", "CZE"],
        "league": ["ENG-Premier League", "GER-Bundesliga", "ITA-Serie A", "ENG-Premier League", "CZE-First League"],
        "season": ["2025-2026"] * 5})
    peers = {"CZE": {"name": "Czechia", "population_m": 10.0}, "DEN": {"name": "Denmark", "population_m": 5.0}}
    out = per_capita(tables, peers, ["ENG-Premier League", "GER-Bundesliga", "ITA-Serie A"], "2025-2026")
    cze = out[out.country == "CZE"].iloc[0]
    assert cze.n_players == 2 and abs(cze.per_million - 0.2) < 1e-9
    assert out.sort_values("rank").iloc[0].country == "DEN"


def test_assign_cohort():
    assert assign_cohort(2004, "2024-2025") == "U22"
    assert assign_cohort(1994, "2024-2025") == "30+"
```

- [ ] **Step 2: Run to verify it fails** → `ImportError`.

- [ ] **Step 3: Rewrite the module**

```python
"""Per-capita benchmark (headline) and cohort gaps for the peer countries.

per-capita: distinct players with `nation` == peer on `current`-season rosters
of the headline leagues, divided by population (millions).
cohorts: metrics season, median npG+A per 90 (quality-adjusted) by country ×
position group × age cohort, players with >= min_minutes.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from src import config
from src.utils import read_parquet, write_parquet

LOG = logging.getLogger(__name__)
COHORTS = [("U22", 0, 21), ("23-25", 23, 25), ("26-29", 26, 29), ("30+", 30, 99)]


def assign_cohort(born: int, season: str) -> str | None:
    age = int(season[:4]) + 1 - born        # age at the season's calendar turn, as in hockey
    if age <= 22:
        return "U22"
    for label, lo, hi in COHORTS[1:]:
        if lo <= age <= hi:
            return label
    return None


def per_capita(tables: pd.DataFrame, peers: dict, headline_leagues: list[str], season: str) -> pd.DataFrame:
    sub = tables[(tables.season == season) & tables.league.isin(headline_leagues) & tables.nation.isin(peers)]
    n = sub.groupby("nation")["fbref_id"].nunique()
    rows = []
    for code, meta in peers.items():
        cnt = int(n.get(code, 0))
        rows.append({"country": code, "name": meta["name"], "n_players": cnt,
                     "population_m": meta["population_m"], "per_million": round(cnt / meta["population_m"], 2)})
    out = pd.DataFrame(rows).sort_values("per_million", ascending=False)
    out["rank"] = range(1, len(out) + 1)
    return out


def cohort_table(features_by_group: dict[str, pd.DataFrame], peers: dict) -> pd.DataFrame:
    season = config.seasons()["metrics"]
    rows = []
    for group, df in features_by_group.items():
        d = df[(df.season == season) & df.nation.isin(peers) & df.league.isin(config.HEADLINE_LEAGUES)].copy()
        d["cohort"] = d["born"].map(lambda b: assign_cohort(int(b), season))
        d["npg_ast_q"] = d["npg_p90_quality"] + d["ast_p90_quality"]
        for (c, coh), g in d.groupby(["nation", "cohort"]):
            rows.append({"country": c, "pos_group": group, "cohort": coh, "n": len(g),
                         "median_npg_ast_p90": round(float(g.npg_ast_q.median()), 2)})
    return pd.DataFrame(rows)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    peers = config.countries()["peers"]
    tables = read_parquet(config.PROCESSED_DIR / "fbref_players.parquet")
    pc = per_capita(tables, peers, config.HEADLINE_LEAGUES, config.seasons()["current"])
    write_parquet(pc, config.PROCESSED_DIR / "per_capita.parquet")
    feats = {g: read_parquet(config.PROCESSED_DIR / f"features_{g}.parquet") for g in config.features()["groups"]}
    coh = cohort_table(feats, peers)
    write_parquet(coh, config.PROCESSED_DIR / "cohorts.parquet")
    render_cohort_heatmap(coh, config.OUTPUTS_DIR / "intl_cohort_heatmap.svg")
    LOG.info("per capita:\n%s", pc.to_string(index=False))


if __name__ == "__main__":
    main()
```
Keep the hockey `render_cohort_heatmap` but make it draw **three** panels
(FW / MF / DF) with countries ordered by `per_capita.rank`, highlighted row =
CZE, titles in English (`"Forwards  ·  median npG+A per 90"` etc.).

- [ ] **Step 4: Tests, live run, commit**

Run: `uv run pytest tests/test_benchmark.py -q && uv run python -m src.international_benchmark`
Expected: 2 passed; the per-capita table printed — this is the headline
number; write it down in the commit message.

```bash
git add src/international_benchmark.py tests/test_benchmark.py
git commit -m "Per-capita benchmark and cohort gaps for nine peer countries"
```

---

### Task 9: Photos from Wikidata (`fetch_photos.py`)

**Files:**
- Create: `src/fetch_photos.py`
- Test: `tests/test_fetch_photos.py` (uses `tests/fixtures/wikidata_sample.json`)

**Interfaces:**
- Produces: `docs/img/players/<fbref_id>.jpg` (≤ 480 px wide) and
  `site/players.json` mapping `fbref_id -> {name, image, credit, license}`;
  functions `sparql_for(names: list[str]) -> str`,
  `match_images(bindings: list[dict], pool: pd.DataFrame) -> pd.DataFrame`
  (`fbref_id, player, image_url, credit`).

- [ ] **Step 1: Failing test**

```python
import json
from pathlib import Path
import pandas as pd
from src.fetch_photos import match_images, sparql_for

FIX = json.loads((Path(__file__).parent / "fixtures" / "wikidata_sample.json").read_text())


def test_sparql_embeds_names_and_czech_citizenship():
    q = sparql_for(["Patrik Schick"])
    assert '"Patrik Schick"@en' in q and "wd:Q213" in q


def test_match_by_name_and_birth_year():
    pool = pd.DataFrame({"fbref_id": ["x1"], "player": ["Patrik Schick"], "born": [1996]})
    out = match_images(FIX["results"]["bindings"], pool)
    assert len(out) == 1 and out.iloc[0].image_url.startswith("http")
```

- [ ] **Step 2: Run to verify it fails** → `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
"""Player photos: Wikidata P18 -> Wikimedia Commons file, downsized into docs/img/players/.

Match rule: label equals the FBref name (accent-insensitive) AND birth year equals.
Credit = Commons file name (attribution required by CC-BY-SA); the page footer
lists every credit.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import urllib.parse

import pandas as pd
import requests
from PIL import Image

from src import config
from src.fetch_squads import normalize_name
from src.utils import read_parquet

LOG = logging.getLogger(__name__)
UA = {"User-Agent": "czefootball-player-pool-atlas/1.0 (barbora@datasimply.eu)"}
IMG_DIR = config.ROOT_DIR / "docs" / "img" / "players"


def sparql_for(names: list[str]) -> str:
    values = " ".join(f'"{n}"@en' for n in names)
    return f"""SELECT ?p ?pLabel ?dob ?img WHERE {{
  VALUES ?name {{ {values} }}
  ?p rdfs:label ?name ; wdt:P27 wd:Q213 .
  OPTIONAL {{ ?p wdt:P569 ?dob }} OPTIONAL {{ ?p wdt:P18 ?img }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }} }}"""


def match_images(bindings: list[dict], pool: pd.DataFrame) -> pd.DataFrame:
    by_norm = {}
    for b in bindings:
        if "img" not in b:
            continue
        name = b["pLabel"]["value"]
        year = int(b["dob"]["value"][:4]) if "dob" in b else None
        by_norm.setdefault(normalize_name(name), []).append((year, b["img"]["value"]))
    rows = []
    for r in pool.itertuples():
        for year, url in by_norm.get(normalize_name(r.player), []):
            if year is None or pd.isna(r.born) or year == int(r.born):
                rows.append({"fbref_id": r.fbref_id, "player": r.player, "image_url": url,
                             "credit": urllib.parse.unquote(url.rsplit("/", 1)[-1])})
                break
    return pd.DataFrame(rows, columns=["fbref_id", "player", "image_url", "credit"])


def _download(url: str, dest) -> None:
    r = requests.get(url + "?width=480", headers=UA, timeout=60)
    r.raise_for_status()
    Image.open(io.BytesIO(r.content)).convert("RGB").save(dest, "JPEG", quality=85)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    pool = read_parquet(config.PROCESSED_DIR / "pool.parquet")
    frames = []
    names = pool.player.tolist()
    for i in range(0, len(names), 40):                       # WDQS is happier with small VALUES blocks
        q = sparql_for(names[i:i + 40])
        r = requests.get("https://query.wikidata.org/sparql", params={"query": q, "format": "json"}, headers=UA, timeout=120)
        r.raise_for_status()
        frames.append(match_images(r.json()["results"]["bindings"], pool))
    matched = pd.concat(frames, ignore_index=True).drop_duplicates("fbref_id")
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    out = {}
    for r in matched.itertuples():
        dest = IMG_DIR / f"{r.fbref_id}.jpg"
        if not dest.exists():
            try:
                _download(r.image_url, dest)
            except Exception as exc:
                LOG.warning("%s: %s", r.player, exc); continue
        out[r.fbref_id] = {"name": r.player, "image": f"img/players/{r.fbref_id}.jpg",
                           "credit": r.credit, "license": "Wikimedia Commons, see file page"}
    (config.ROOT_DIR / "site" / "players.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    LOG.info("photos: %d of %d pool players", len(out), len(pool))


if __name__ == "__main__":
    main()
```
Add `pillow>=10` to dependencies.

- [ ] **Step 4: Tests, live run, commit**

Run: `uv run pytest tests/test_fetch_photos.py -q && uv run python -m src.fetch_photos`
Expected: 2 passed; coverage logged (expect 30–60 % of the pool; internationals
near 100 %).

```bash
git add src/fetch_photos.py tests/test_fetch_photos.py site/players.json docs/img/players pyproject.toml
git commit -m "Player photos from Wikidata/Commons with credits"
```

---

### Task 10: Historical analogs and sensitivity on the football corpus

**Files:**
- Modify: `src/historical_analogs.py`, `src/sensitivity.py`
- Test: `tests/test_analogs.py`

**Interfaces:**
- `historical_analogs.find_analogs(corpus: pd.DataFrame, target_id: str, k: int = 5) -> pd.DataFrame`
  (`rank, fbref_id, player, nation, league, season, min, npg_ast_q, distance, followed: list[dict]`);
  output `data/processed/analogs.json` keyed by showcase `fbref_id`.
- `sensitivity.main()` unchanged in interface; multipliers now from
  `config/league_quality.yaml`; metric = `npg_p90_quality + ast_p90_quality`.

- [ ] **Step 1: Failing test**

```python
import pandas as pd
from src.historical_analogs import find_analogs


def _corpus():
    rows = []
    for pid, born, seasons in [("t", 2002, ["2024-2025"]), ("a", 1998, ["2020-2021", "2021-2022"]),
                               ("b", 1990, ["2012-2013", "2013-2014"])]:
        for s in seasons:
            rows.append({"fbref_id": pid, "player": pid.upper(), "nation": "X", "league": "L", "season": s,
                         "born": born, "min": 2000, "npg_ast_q": 0.5, "league_multiplier": 0.8})
    return pd.DataFrame(rows)


def test_analogs_match_same_age_and_list_following_seasons():
    out = find_analogs(_corpus(), "t", k=2)
    assert list(out.fbref_id) == ["a", "b"]          # both aged 22 in their first listed season
    assert out.iloc[0].followed[0]["season"] == "2021-2022"
```

- [ ] **Step 2: Run to verify it fails** → assertion / import error.

- [ ] **Step 3: Rewrite `find_analogs`**

```python
def _age(born: int, season: str) -> int:
    return int(season[:4]) + 1 - int(born)


def find_analogs(corpus: pd.DataFrame, target_id: str, k: int = 5) -> pd.DataFrame:
    tgt = corpus[corpus.fbref_id == target_id].sort_values("season").iloc[-1]
    age = _age(tgt.born, tgt.season)
    cand = corpus[(corpus.fbref_id != target_id)].copy()
    cand["age"] = [_age(b, s) for b, s in zip(cand.born, cand.season)]
    cand = cand[cand.age == age]
    feats = ["npg_ast_q", "min", "league_multiplier"]
    mu, sd = corpus[feats].mean(), corpus[feats].std().replace(0, 1)
    z = (cand[feats] - mu) / sd
    zt = (tgt[feats].astype(float) - mu) / sd
    cand["distance"] = ((z - zt) ** 2).sum(axis=1) ** 0.5
    best = cand.sort_values("distance").head(k).reset_index(drop=True)
    best["rank"] = best.index + 1
    followed = []
    for r in best.itertuples():
        later = corpus[(corpus.fbref_id == r.fbref_id) & (corpus.season > r.season)].sort_values("season").head(4)
        followed.append([{"season": s, "league": l, "min": int(m), "npg_ast_q": round(float(q), 2)}
                         for s, l, m, q in zip(later.season, later.league, later["min"], later.npg_ast_q)])
    best["followed"] = followed
    return best[["rank", "fbref_id", "player", "nation", "league", "season", "min", "npg_ast_q", "distance", "followed"]]
```
The corpus for the live run = all `features_*.parquet` rows for both seasons
plus the same tables for `2020-2021 … 2022-2023` fetched once by extending
`fetch_fbref.main()`'s season list with `config.load_yaml("seasons.yaml").get("history", [])`
(add `history: ["2020-2021", "2021-2022", "2022-2023"]` to `config/seasons.yaml`
and rerun `make fetch` — Big-5 + headline leagues only, to keep it to ~30 calls).
Showcase targets: computed by the rule in spec §2 inside `main()`:
```python
def showcase_ids(feats_by_group: dict[str, pd.DataFrame]) -> list[str]:
    ids = []
    for g, df in feats_by_group.items():
        cz = df[(df.season == config.seasons()["metrics"]) & df.czech_eligible & (df["min"] >= 900)].copy()
        cz["q"] = cz.npg_p90_quality + cz.ast_p90_quality
        ids.append(cz.sort_values("q", ascending=False).iloc[0].fbref_id)
        nt = cz[cz.nt_flag].sort_values("born", ascending=False)
        if len(nt) and nt.iloc[0].fbref_id not in ids:
            ids.append(nt.iloc[0].fbref_id)
    return ids
```

- [ ] **Step 4: `sensitivity.py`** — replace the metric and multiplier source
as stated in Interfaces; scenarios: each league ±20 % and all ±20 %; report
top-10 overlap/churn and mean Δrank (top 20) exactly like hockey.

- [ ] **Step 5: Tests, run, commit**

Run: `uv run pytest -q && uv run python -m src.historical_analogs && uv run python -m src.sensitivity`

```bash
git add src/historical_analogs.py src/sensitivity.py tests/test_analogs.py config/seasons.yaml
git commit -m "Historical analogs and multiplier sensitivity for football"
```

---

### Task 10b: Pathways and differences (`pathways.py`)

**Files:**
- Create: `src/pathways.py`
- Test: `tests/test_pathways.py`

**Interfaces:**
- Produces `data/processed/pathways.json` with keys `youth_exposure`
  (list of `{league, country, share_u21, share_u23, minutes_total}`),
  `export_route` (list of `{country, n, median_export_age, origin_shares:
  {domestic, stepping_stone, other_top9, not_covered}, censored_share}`),
  `fare` (list of `{country, n, median_min_share, median_club_elo_pct}`),
  `profile` (list of `{country, tier, pos_group, n, median_npg_ast_q}`); functions
  `youth_exposure(tables, season, league_country) -> pd.DataFrame`,
  `export_route(tables, headline, stepping, peer_domestic, peers) -> pd.DataFrame`,
  `fare(tables, elo_pct, headline, peers, season) -> pd.DataFrame`.
- Consumes: `fbref_players.parquet` (all seasons), `config.leagues()`,
  ClubElo CSV cached by Task 5 (`http_get` cache key `clubelo_<date>`).

- [ ] **Step 1: Failing tests**

```python
import pandas as pd
from src.pathways import youth_exposure, export_route


def test_youth_exposure_counts_own_young_nationals():
    t = pd.DataFrame({"league": ["CZE-First League"] * 3, "season": ["2024-2025"] * 3,
                      "fbref_id": list("abc"), "nation": ["CZE", "CZE", "SVK"],
                      "born": [2004, 1995, 2004], "min": [900, 2700, 900]})
    out = youth_exposure(t, "2024-2025", {"CZE-First League": "CZE"})
    row = out.iloc[0]
    assert abs(row.share_u21 - 900 / 4500) < 1e-9 and row.minutes_total == 4500


def test_export_route_age_and_origin():
    t = pd.DataFrame({
        "fbref_id": ["x", "x", "x", "y", "y"], "nation": ["CZE"] * 3 + ["DEN"] * 2,
        "born": [2001] * 3 + [2000] * 2,
        "league": ["CZE-First League", "NED-Eredivisie", "ENG-Premier League", "DEN-Superliga", "ITA-Serie A"],
        "season": ["2022-2023", "2023-2024", "2025-2026", "2024-2025", "2025-2026"], "min": [1000] * 5})
    out = export_route(t, ["ENG-Premier League", "ITA-Serie A"], ["NED-Eredivisie"],
                       {"CZE-First League": "CZE", "DEN-Superliga": "DEN"}, ["CZE", "DEN"])
    cze, den = out[out.country == "CZE"].iloc[0], out[out.country == "DEN"].iloc[0]
    assert cze.median_export_age == 25 and cze.origin_shares["stepping_stone"] == 1.0
    assert den.median_export_age == 26 and den.origin_shares["domestic"] == 1.0
```

- [ ] **Step 2: Run to verify it fails** → `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
"""Pathways and differences: youth exposure at home, export route, how exports fare, profile by tier."""
from __future__ import annotations

import json
import logging
from io import StringIO

import pandas as pd

from src import config
from src.utils import http_get, read_parquet

LOG = logging.getLogger(__name__)


def _age(born, season: str) -> int:
    return int(season[:4]) + 1 - int(born)


def youth_exposure(tables: pd.DataFrame, season: str, league_country: dict[str, str]) -> pd.DataFrame:
    rows = []
    for league, country in league_country.items():
        t = tables[(tables.league == league) & (tables.season == season)]
        if t.empty:
            continue
        age = t["born"].map(lambda b: _age(b, season))
        own = t.nation == country
        total = float(t["min"].sum())
        rows.append({"league": league, "country": country, "minutes_total": total,
                     "share_u21": float(t.loc[own & (age <= 21), "min"].sum()) / total,
                     "share_u23": float(t.loc[own & (age <= 23), "min"].sum()) / total})
    return pd.DataFrame(rows)


def export_route(tables, headline: list[str], stepping: list[str], peer_domestic: dict[str, str], peers: list[str]) -> pd.DataFrame:
    current = config.seasons()["current"] if "seasons" in dir(config) else tables.season.max()
    first_hist = tables.season.min()
    rows = []
    for country in peers:
        on_roster = tables[(tables.season == current) & tables.league.isin(headline) & (tables.nation == country)]
        ages, origins, censored = [], [], 0
        for pid in on_roster.fbref_id.unique():
            hist = tables[tables.fbref_id == pid].sort_values("season")
            top = hist[hist.league.isin(headline)]
            first = top.iloc[0]
            if first.season == first_hist:
                censored += 1
            ages.append(_age(first.born, first.season))
            before = hist[hist.season < first.season]
            if before.empty:
                origins.append("not_covered")
            else:
                lg = before.iloc[-1].league
                origins.append("domestic" if peer_domestic.get(lg) == country else
                               "stepping_stone" if lg in stepping else
                               "other_top9" if lg in headline else "not_covered")
        n = len(ages)
        shares = {k: (origins.count(k) / n if n else 0.0) for k in ("domestic", "stepping_stone", "other_top9", "not_covered")}
        rows.append({"country": country, "n": n, "median_export_age": float(pd.Series(ages).median()) if n else None,
                     "origin_shares": shares, "censored_share": censored / n if n else 0.0})
    return pd.DataFrame(rows)


def club_elo_percentiles(date: str, league_map: dict[str, tuple[str, int]]) -> pd.DataFrame:
    elo = pd.read_csv(StringIO(http_get(f"http://api.clubelo.com/{date}", cache_key=f"clubelo_{date}")))
    frames = []
    for league, (country, level) in league_map.items():
        sub = elo[(elo.Country == country) & (elo.Level == level)].copy()
        sub["league"], sub["elo_pct"] = league, sub["Elo"].rank(pct=True)
        frames.append(sub[["league", "Club", "elo_pct"]])
    return pd.concat(frames, ignore_index=True)


def fare(tables, elo_pct: pd.DataFrame, headline: list[str], peers: list[str], season: str) -> pd.DataFrame:
    t = tables[(tables.season == season) & tables.league.isin(headline) & tables.nation.isin(peers)].copy()
    tm = tables[tables.season == season].groupby(["league", "team"])["mp"].max().rename("team_matches")
    t = t.join(tm, on=["league", "team"])
    t["min_share"] = t["min"] / (t["team_matches"] * 90)
    t = t.merge(elo_pct, left_on=["league", "team"], right_on=["league", "Club"], how="left")  # name mismatches -> NaN, reported
    out = t.groupby("nation").agg(n=("fbref_id", "nunique"), median_min_share=("min_share", "median"),
                                  median_club_elo_pct=("elo_pct", "median")).reset_index().rename(columns={"nation": "country"})
    LOG.info("fare: %d of %d rows matched a ClubElo club", t.elo_pct.notna().sum(), len(t))
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    cfg, seasons, peers = config.leagues(), config.seasons(), config.PEER_COUNTRIES
    tables = read_parquet(config.PROCESSED_DIR / "fbref_players.parquet")
    peer_domestic = {k: v["country"] for k, v in cfg["peer_domestic"].items()} | {cfg["domestic"]: "CZE"}
    out = {
        "youth_exposure": youth_exposure(tables, seasons["metrics"], peer_domestic).to_dict("records"),
        "export_route": export_route(tables, cfg["headline"], cfg["stepping_stone"], peer_domestic, peers).to_dict("records"),
    }
    from src.fetch_elo import _league_map
    pct = club_elo_percentiles(seasons["current"].split("-")[0] + "-08-01", _league_map())
    out["fare"] = fare(tables, pct, cfg["headline"], peers, seasons["metrics"]).to_dict("records")
    feats = pd.concat([read_parquet(config.PROCESSED_DIR / f"features_{g}.parquet") for g in config.features()["groups"]])
    f = feats[(feats.season == seasons["metrics"]) & feats.nation.isin(peers)].copy()
    f["tier"] = f.league.map(lambda l: "top9" if l in cfg["headline"] else "stepping_stone" if l in cfg["stepping_stone"] else "domestic")
    f["q"] = f.npg_p90_quality + f.ast_p90_quality
    out["profile"] = (f.groupby(["nation", "tier", "pos_group"]).agg(n=("fbref_id", "nunique"), median_npg_ast_q=("q", "median"))
                       .reset_index().rename(columns={"nation": "country"}).to_dict("records"))
    (config.PROCESSED_DIR / "pathways.json").write_text(json.dumps(out, indent=1, default=float))
    LOG.info("pathways written")


if __name__ == "__main__":
    main()
```
ClubElo club names differ from FBref team names for some clubs; after the
live run, read the `fare:` log line and add a `config/club_aliases.yaml`
(`FBref name: ClubElo name`) for the unmatched top-9 clubs of peer players —
there are few.

- [ ] **Step 4: Tests, live run, commit**

Run: `uv run pytest tests/test_pathways.py -q && uv run python -m src.pathways`

```bash
git add src/pathways.py tests/test_pathways.py config/club_aliases.yaml
git commit -m "Pathways: youth exposure, export route, how exports fare, profile by tier"
```

The report gets a chapter between the clusters and the AI/cards chapter:
**"Where the train leaves"** — exhibit A as a bar list (`.capita` markup,
CZE highlighted), exhibit B as a small table (country × median export age ×
origin shares), exhibit C as bars (minutes share, club percentile), exhibit D
folded under the cohort tables. Task 11's template and `render.py` load
`pathways.json` into `ctx["pathways"]`; the test in Task 11 asserts
`class="pathways"` is present.

---

### Task 11: Report template and render (English source)

**Files:**
- Modify: `src/render.py`, `templates/report.html.j2`
- Test: `tests/test_render.py`

**Interfaces:**
- Produces: `outputs/index.html`, `outputs/atlas_{FW,MF,DF}.svg`,
  `outputs/style.css` (copied), consumed by `site/build.sh`.
- Template context keys (the site scripts rely on the same class names as
  hockey — keep them): `per_capita` (list of dicts), `cohorts` (nested by
  group → cohort → country), `clusters` (group → projection → list of
  `{id, label, n, nt_pool, median_born, top: [names]}`), `movers`
  (group → up/down lists), `cards` (showcase list: `fbref_id, name, pos,
  age, league, club, nt_events, stats, clusters, tactical, trajectory,
  analogs, photo`), `multipliers`, `loadings`, `sensitivity`, `limitations`,
  `rendered_at`, `hero` (`per_million, rank, n_peers, n_players, population_m`),
  `photo_credits`.

- [ ] **Step 1: Failing render test**

```python
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from src.render import build_context_from_fixtures


def test_template_renders_with_fixture_context():
    ctx = build_context_from_fixtures()
    env = Environment(loader=FileSystemLoader("templates"), autoescape=False)
    html = env.get_template("report.html.j2").render(**ctx)
    assert '<html lang="en">' in html
    assert 'class="hero-num-figure"' in html and "*" in html
    for cls in ("capita-row", "cohort-table", "cluster-list", "cycle-card", "analog-block", "limitations"):
        assert f'class="{cls}' in html, cls
```
`build_context_from_fixtures()` returns a small hand-written context (two
countries, one group, one card) so the template is testable offline.

- [ ] **Step 2: Run to verify it fails** → `ImportError`.

- [ ] **Step 3: Rewrite the template copy in English**

Structure identical to hockey (masthead → hero → benchmark → observations →
clusters → trajectories → chapter II: cards + analogs → chapter III:
methodology → limitations → reproducibility → footer). Replace every hockey
noun: NHL → "top-9 leagues", GP → minutes/90, WC 24/25 → "NT call-up 2024–26",
MS → NT. Three atlas figures with `data-atlas="fw|mf|df"` and three
`.cluster-list[data-atlas-clusters="fw|mf|df"]`. Hero copy:

```html
<span class="hero-num-figure">{{ "%.2f"|format(hero.per_million) }}<span class="ast" aria-hidden="true">*</span></span>
<span class="hero-num-unit">players in Europe's nine strongest leagues per million inhabitants, 2025/26 rosters</span>
...
<p class="hero-footnote">* {{ hero.n_players }} players with FBref nationality CZE on 2025/26 rosters of the UEFA top-9 leagues ÷ {{ hero.population_m }} M inhabitants (Eurostat 2024); peer countries computed the same way. <a href="#methodology">Methodology</a>.</p>
```
Limitations (spec §10): leagues without metrics, free-tier feature set,
NT-flag source, photo coverage, season split, no xG in PCA, no market values.

- [ ] **Step 4: `render.py`**

Keep the hockey structure; swap loaders to the new parquet names; `_render_atlas`
per group with `nt_flag` rings (label "NT 2024–26") and top-10 Czech names
annotated; cards from `showcase_ids` (import from `historical_analogs`),
photos from `site/players.json`; tactical read per cluster from
`config/cluster_labels.yaml` (label only — tactical prose is written by hand in
`config/cluster_labels.yaml` under `tactical:` after clusters are seen).
`main()` also copies `templates/style.css` to `outputs/`.

- [ ] **Step 5: Render, eyeball, commit**

Run: `uv run pytest tests/test_render.py -q && uv run python -m src.render && python -m http.server 8020 --directory outputs`
Open `http://localhost:8020/index.html`; every number on the page must come
from the context (grep the template for digits outside `{{ }}` — only
years and K = 10 may be literal).

```bash
git add src/render.py templates/report.html.j2 tests/test_render.py config/cluster_labels.yaml
git commit -m "English report template and render for the football atlas"
```

---

### Task 12: Site build — English source, Czech translation, photos, deploy

**Files:**
- Modify: `site/build.sh`, `site/enrich_index.py`, `site/translate_index.py`,
  `site/svg_labels.py`, `site/atlas_meta.py`, `docs/atlas.js` (three figures — no change needed if selectors are data-driven), `Makefile` (`pages`)
- Create: `site/source/index.en.html` (from `outputs/index.html`)
- Test: `tests/test_site_build.py`

**Interfaces:**
- `site/build.sh` reads `site/source/index.en.html`, writes `docs/index.html`
  (EN) and `docs/cs/index.html` (CS), `docs/atlas_meta.json`, `docs/*.svg`
  (EN, copied) and `docs/cs/*.svg` (CS labels via `svg_labels.py`).

- [ ] **Step 1: Failing test**

```python
import subprocess, re
from pathlib import Path


def test_build_produces_both_languages(tmp_path):
    subprocess.run(["./site/build.sh"], check=True)
    en = Path("docs/index.html").read_text(encoding="utf-8")
    cs = Path("docs/cs/index.html").read_text(encoding="utf-8")
    assert '<html lang="en">' in en and '<html lang="cs">' in cs
    assert 'href="cs/"' in en and 'href="../"' in cs
    # no untranslated section headings in the Czech page
    for en_heading in re.findall(r"<h2[^>]*>([^<]+)</h2>", en):
        assert en_heading not in cs, en_heading
```

- [ ] **Step 2: Flip the translation direction**

In `site/translate_index.py`: pairs become `R(<english>, <czech>)`; the
decimal step becomes point → comma inside `<body>` only, protecting
`"1,177"`-style thousands the other way round (`(?<=\d)\.(?=\d)` → `,` except
inside `style=`, `data-tex=` and `<code>`: apply on text nodes only — simplest
is to run it through `re.sub` on segments between `>` and `<`). Language switch
block: EN page current, CS link `cs/`; CS page gets `../`. Topbar labels, tile
labels, fold summaries, `hero-footnote`, atlas hint strings all get pairs.
`enrich_index.py`: photos come from `site/players.json` keyed by `fbref_id`
(cards carry `data-player-id`), cast strip = showcase ids, hero cut-out = first
showcase; remove the hockey-specific Nečas block and NHL API calls; `IMG_ATTRS`
keeps the monogram fallback. `svg_labels.py`: `T` maps EN → CS and writes
`docs/cs/*.svg` from `docs/*.svg`. `atlas_meta.py`: reads `docs/*.svg`
(English originals now), three atlases + heatmap. `atlas.js`: cluster names
from `.cluster-list[data-atlas-clusters]` — already generic; the CS strings
table stays.

- [ ] **Step 3: Build, run the test, review in the browser at 390 px and 1440 px**

Run: `make pages && uv run pytest tests/test_site_build.py -q && python -m http.server 8765 --directory docs`
Check: hero tiles, three atlases interactive (hover gives PC1/PC2, name click
opens a card), TOC panel on phone, no horizontal overflow
(`document.documentElement.scrollWidth === innerWidth`).

- [ ] **Step 4: Snapshot the processed data and commit**

```bash
make snapshot
git add -A
git commit -m "Site build for the football atlas (EN default, CS), data snapshot"
```

- [ ] **Step 5: Publish**

```bash
gh repo create sandovabarbora/czefootball-player-pool-atlas --public --source=. --remote=origin --push
gh api -X POST repos/sandovabarbora/czefootball-player-pool-atlas/pages -f 'source[branch]=main' -f 'source[path]=/docs'
gh api -X PUT repos/sandovabarbora/czefootball-player-pool-atlas/pages -f cname=football.datasimply.eu
```
Then Bára adds the Wedos DNS record `football CNAME sandovabarbora.github.io.`;
once `dig +short football.datasimply.eu` resolves, `gh api -X PUT .../pages -F https_enforced=true`
after the certificate state is `approved`.

---

### Task 13: README, limitations, memory

**Files:**
- Modify: `README.md`, `templates/report.html.j2` (limitations copy check), `docs/superpowers/specs/...` (status → implemented)

- [ ] **Step 1: README**

Sections: what it is (two sentences), the headline number with its footnote,
run it (`make install && make all && make pages`), data sources with access
notes (FBref free tier, ClubElo, Wikipedia, Wikidata/Commons credits), known
gaps (copied from the Limitations section), how the site is built
(`site/build.sh`, translation pairs fail loudly), licence (MIT; photos
CC-BY-SA per credit list).

- [ ] **Step 2: Final checks and commit**

Run: `uv run ruff check src tests && uv run pytest -q`

```bash
git add README.md docs/superpowers
git commit -m "README and spec status for the football atlas v1"
git push
```

- [ ] **Step 3: Write the decision to `~/Documents/memory/decisions.md`**

Headline number, peer ranking, pool size, photo coverage, anything that broke
in FBref access, and the football.datasimply.eu DNS status.

---

## Self-review

- **Spec coverage:** corpus (T2/T3), headline (T8), cohorts (T8), pathways (T10b/T11), atlas
  (T7/T11), trajectories (T7), NT flag (T4/T6), cards + analogs (T10/T11),
  site bilingual (T12), snapshot (T12), method rules (T5/T6), limitations
  (T11/T13), DoD (T12/T13). Out-of-scope items untouched.
- **Placeholders:** none; the two "read from the fixture" notes (T3 `data-stat`
  names, T2 `league_dict` schema) point at concrete files to consult.
- **Type consistency:** `fbref_id` is the key everywhere; `pos_group` in
  `{FW, MF, DF}`; seasons `YYYY-YYYY`; feature names `npg_p90, ast_p90,
  min_share, age, cards_p90` with `_shrunk/_quality/_z` suffixes match between
  T6, T7, T8, T10.
