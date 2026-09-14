# v1.1 Block A — season shift + content additions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the atlas to the completed 2025/26 season (rosters/current club 2026/27), add the fifth card rule, the WC 2026 squad lens, the executive-summary findings + method note, the data-quality log and the "how this was built" section — all bilingual, all numbers computed.

**Architecture:** Same pipeline as v1 (`src/*.py` → `data/processed/*` → `src/render.py` + `templates/report.html.j2` → `site/build.sh` → `docs/`). New processed artefacts: `squad_lens.json`, `data_quality.json`. New template sections read from the context only; copy lives in `src/i18n.py` (EN) + `config/i18n/cs.yaml` (CS) and the completeness check fails when a key is missing.

**Tech Stack:** Python 3.13, pandas, Jinja2, pytest, soccerdata (FBref), BeautifulSoup (Wikipedia), matplotlib. `uv run` for everything.

**Spec:** `docs/superpowers/specs/2026-09-14-v1-1-portfolio-edition-design.md` (§2A, §2b) on top of `docs/superpowers/specs/2026-09-12-czech-football-player-pool-atlas-design.md`.

## Global Constraints

- Descriptive only: no predictions, no selection recommendations, in copy, logs and names alike. Every strong claim in the report ends in `*` with a mono footnote naming the number's source.
- Numbers are computed, never typed. A typed number in a template or i18n string is a defect (dates of recorded events in the data-quality log are the one exception and are marked as recorded).
- Cards are rule-based, never hand-picked; the reason string is descriptive.
- Every user-facing string goes through `t()`/`term()`; EN default in `src/i18n.py::EN`, CS in `config/i18n/cs.yaml`. `src/i18n.py::check_complete` must pass (run `uv run python -m src.render` to prove it; it fails loudly).
- Seasons come from `config/seasons.yaml` (`previous` 2024-2025, `metrics` 2025-2026, `current` 2026-2027, `history` 2020-21..2023-24). No season string in code except tests and docstrings.
- Commit after every task with a plain message: **no `Co-Authored-By` trailer, no `Claude-Session:` line**. Never commit `data/raw/`, `data/processed/`, `outputs/`; `data/snapshot/` is committed only by the controller (Task 8).
- Never dispatch subagents from an implementer. Tests: `uv run pytest -q` must stay green; new behaviour gets a test.
- Working tree: `.worktrees/v1_1`, branch `v1.1`.

---

### Task 1: Season labels from config; per-capita on the metrics season

**Files:**
- Modify: `src/render.py:67` (`NT_LABEL`), `src/render.py:247-256` (atlas suptitle + caption), `src/international_benchmark.py:245` (heatmap title), `src/international_benchmark.py:270-271, 350`
- Modify: `src/i18n.py` (keys `mast.nt`, `hero.meta.nt`, `ch1.atlas.caption`, `ch3.card.nt`, `pi.note`, `lim.nt.body`, `lim.seasons.body`), `config/i18n/cs.yaml` (same keys)
- Modify: `site/svg_labels.py:27-36` (pairs built from the season label, not typed)
- Test: `tests/test_render.py`, `tests/test_international_benchmark.py`, `tests/test_site_build.py`

**Interfaces:**
- Produces: `src/config.py::nt_years() -> str` returning `"2024–26"`-style span computed from `config/squads.yaml` event years (min–max, en dash, two-digit end); `src/render.py::season_label(season)` already exists (`"2025-2026" → "2025/26"`).
- Consumes: `config.seasons()`, `config.load_yaml("squads.yaml")`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_config.py (append)
def test_nt_years_span_from_squads_yaml():
    from src import config
    years = [e["year"] for e in config.load_yaml("squads.yaml")["events"]]
    assert config.nt_years() == f"{min(years)}–{str(max(years))[-2:]}"


# tests/test_render.py (append)
def test_no_typed_season_in_render_or_i18n_module():
    import re
    from pathlib import Path
    for f in ("src/render.py", "src/i18n.py", "src/international_benchmark.py", "site/svg_labels.py"):
        src = Path(f).read_text(encoding="utf-8")
        body = "\n".join(l for l in src.splitlines() if not l.strip().startswith(("#", '"""', "'''")))
        assert not re.search(r"20\d\d[/–-]\d\d\b", body.replace("2024–26", "")), f
```

The second test will still see docstring seasons; keep the filter as written (line-start comments/docstrings) and move any docstring example that trips it to a comment line.

- [ ] **Step 2: Run to verify they fail** → `uv run pytest tests/test_config.py tests/test_render.py -q` → 2 failures.

- [ ] **Step 3: Implement**

`src/config.py`:
```python
def nt_years() -> str:
    """'2024–26': span of the squad events in config/squads.yaml (national-team flag window)."""
    years = [int(e["year"]) for e in load_yaml("squads.yaml")["events"]]
    return f"{min(years)}–{str(max(years))[-2:]}"
```

`src/render.py`: `NT_LABEL = f"NT {config.nt_years()}"`; in `_render_atlas` the caption sentence `f"call-up 2024–26."` → `f"call-up {config.nt_years()}."`. In `build_context`, add `"nt_years": config.nt_years()` to `facts` and pass `nt_years=facts["nt_years"]` wherever the template calls `t('hero.meta.nt')`, `t('mast.nt')`, `t('ch3.card.nt')`, `t('pi.note', …)`, `t('ch1.atlas.caption', …)`; change the EN strings to `"NT call-up {nt_years}"`, `"NT {nt_years}"`, `"… call-up {nt_years} …"` and the CS ones likewise (`"Reprezentace {nt_years}"` etc.). `lim.nt.body` gets `{nt_years}` in place of "since 2024".

`src/international_benchmark.py`: title → `f"International cohort benchmark  ·  UEFA top-9 leagues {season_label(metrics)}"` where `season_label` is imported from `src.render`? No — `render` imports `international_benchmark`; put `season_label` into `src/utils.py` and import it in both (`render.py` keeps a re-export `from src.utils import season_label`). Line 350: `per_capita(tables, peers, config.HEADLINE_LEAGUES, config.seasons()["metrics"])` and the narrative line 270 says `{metrics} rosters (per-capita) and {metrics} season (cohorts)`.

`src/render.py` hero: the per-capita season passed to `hero.unit`, `hero.footnote`, `obs.1.body` becomes `seasons.metrics` (template `seasons.current` → `seasons.metrics` in those three calls; `hero.stamp.atlas` keeps `current`). `lim.seasons.body` EN: "The headline per-capita count and every metric use the complete {metrics} season; trajectories run {previous} → {metrics}; the club on a card is the {current} club (season in progress at build time)." CS accordingly.

`site/svg_labels.py`: build the season-bearing pairs from config:
```python
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config
from src.utils import season_label
METRICS = season_label(config.seasons()["metrics"])
T = {
    ...
    f"Czech football · Forwards {METRICS}": f"Český fotbal · Útočníci {METRICS}",
    f"Czech football · Midfielders {METRICS}": f"Český fotbal · Záložníci {METRICS}",
    f"Czech football · Defenders {METRICS}": f"Český fotbal · Obránci {METRICS}",
    f"NT {config.nt_years()}": "Reprezentace",
    f"International cohort benchmark  ·  UEFA top-9 leagues {METRICS}": f"Mezinárodní kohortový benchmark  ·  top-9 ligy UEFA {METRICS}",
}
```

- [ ] **Step 4: Run tests** → `uv run pytest -q` → green. `uv run python -m src.render` must run on the snapshot (restore it first: `make restore-snapshot`) and produce `outputs/index.html` + `outputs/cs/index.html` with no missing-key error.

- [ ] **Step 5: Commit** — `git add src config site tests && git commit -m "Season labels and NT window from config; per-capita on the metrics season"`

---

### Task 2 (controller, not a subagent): pipeline rerun on 2025/26 + cluster labels

- [ ] `make pool photos features reduce benchmark analogs sensitivity pathways` after the fetch finishes; kill automation Chrome. Check: `fbref_players.parquet` has 2026-2027 rows for all 18 leagues with the page `<h1>` guard passing; pool ≈ 475; features per group.
- [ ] Rewrite `config/cluster_labels.yaml` labels + tactical reads for the new k-means fit (authorial; no counts, no forward-looking phrases).
- [ ] `make render`; sanity-read the observations; commit `config/cluster_labels.yaml`.

---

### Task 3: Fifth card rule — national-team core

**Files:**
- Modify: `src/historical_analogs.py:115-190` (`showcase_ids`), `src/render.py:69-80` (`RULE_KICKERS`, `RULE_KICKER_KEYS`), `src/i18n.py` (`kicker.ntcore`, `ch3.cards.rules`), `config/i18n/cs.yaml`, `templates/report.html.j2` (cards framing + "why these cards" note)
- Test: `tests/test_historical_analogs.py`

**Interfaces:**
- Consumes: `features_*.parquet` columns `nt_events` (string, events joined by `" · "`), `nt_flag`, `league`, `min`, `season`, `czech_eligible`; `config.load_yaml("squads.yaml")["events"]`.
- Produces: `showcase_ids(..., nt_core_event: str | None = None)`; reason string prefix `"most top-9 minutes among <event> squad "` → kicker `kicker.ntcore`; showcase length cap 15.

- [ ] **Step 1: Failing test**

```python
def test_rule_e_picks_wc_squad_member_with_most_top9_minutes_per_group(monkeypatch):
    # FW: A (chosen by rule a), B in WC squad with 1800 top-9 min, C in WC squad 900 min
    fw = pd.DataFrame({
        "player_key": ["a|1", "b|2", "c|3"], "player": ["A", "B", "C"], "season": ["2025-2026"] * 3,
        "czech_eligible": [True] * 3, "min": [2000, 1800, 900], "born": [1996, 1998, 2001],
        "league": ["GER-Bundesliga", "ENG-Premier League", "ITA-Serie A"],
        "npg_p90_quality": [1.0, 0.3, 0.2], "ast_p90_quality": [0.5, 0.1, 0.1],
        "nt_flag": [False, True, True],
        "nt_events": ["", "2026 FIFA World Cup", "UEFA Euro 2024 · 2026 FIFA World Cup"],
    })
    out = showcase_ids({"FW": fw}, "2025-2026", headline_leagues=["GER-Bundesliga", "ENG-Premier League", "ITA-Serie A"],
                       domestic_league="CZE-First League", nt_core_event="2026 FIFA World Cup")
    reasons = {s["player_key"]: s["reason"] for s in out}
    assert reasons["a|1"].startswith("highest quality-adjusted")
    assert reasons["c|3"].startswith("youngest national-team")      # rule (b) → C (born 2001)
    assert reasons["b|2"] == "most top-9 minutes among 2026 FIFA World Cup squad FW"
```

- [ ] **Step 2: Run** → `uv run pytest tests/test_historical_analogs.py -q -k rule_e` → fails on the unexpected keyword.

- [ ] **Step 3: Implement** in `showcase_ids` (after rule (d), inside the group loop; signature gains `nt_core_event: str | None = None`; docstring adds rule (e)):

```python
        if nt_core_event and "nt_events" in cz.columns:
            core = cz[cz.nt_events.fillna("").str.contains(nt_core_event, regex=False) & cz.league.isin(headline)]
            core_min = core.groupby("player_key")["min"].sum().sort_values(ascending=False)
            for key in core_min.index:
                if key in seen:
                    continue
                row = core[core.player_key == key].iloc[0]
                _add(row, group, f"most top-9 minutes among {nt_core_event} squad {group}")
                break
    return showcase[:15]
```

`main()` passes `nt_core_event=config.load_yaml("squads.yaml").get("nt_core_event")`; add to `config/squads.yaml`: `nt_core_event: "2026 FIFA World Cup"` (must equal an `events[].event`; assert that in `main()`).

`src/render.py`: append `("most top-9 minutes among", "National-team core")` to `RULE_KICKERS` and `"most top-9 minutes among": "kicker.ntcore"` to `RULE_KICKER_KEYS` — note rule (c)'s prefix is `"most top-9 league minutes"`, rule (e)'s is `"most top-9 minutes among"`, both are matched by `startswith`; order (c) before (e). `Translator.reason` handles the `{pos}` suffix already; add the reason pattern to CS `terms`: `"most top-9 minutes among 2026 FIFA World Cup squad {pos}": "nejvíc minut v top-9 ligách mezi nominovanými na MS 2026 ({pos})"`.

i18n: `"kicker.ntcore": "National-team core — most top-9 minutes in the {event} squad"` (render passes `event`), CS `"Jádro reprezentace — nejvíc minut v top-9 ligách mezi nominovanými na {event}"`; `"ch3.cards.rules": "Why these cards: one card per position group per rule — (a) highest quality-adjusted npG+A per 90, (b) youngest national-team call-up, (c) most top-9 minutes, (d) most domestic minutes under 23 without a top-9 season, (e) most top-9 minutes among the {event} squad. Already-chosen players fall through to the next name."` + CS. Template: `<p class="capita-note">{{ t('ch3.cards.rules', event=nt_core_event) }}</p>` right under the cards framing; `build_context` adds `"nt_core_event"`.

- [ ] **Step 4: Run** `uv run pytest -q` → green; `uv run python -m src.historical_analogs && uv run python -m src.render` on processed data → up to 15 cards, log shows the new reasons.

- [ ] **Step 5: Commit** — `git commit -m "Fifth card rule: national-team core (most top-9 minutes in the WC 2026 squad)"`

---

### Task 4: WC 2026 squad lens (exhibit F)

**Files:**
- Create: `src/squad_lens.py`, `tests/test_squad_lens.py`
- Modify: `config/squads.yaml` (peer squads), `src/fetch_squads.py` (write `peer_squads.parquet`), `src/render.py` (`_build_squad_lens`, context key), `templates/report.html.j2` (exhibit F after exhibit E), `src/i18n.py`, `config/i18n/cs.yaml`, `Makefile` (`benchmark` target also runs `src.squad_lens`)
- Test fixture: reuse `tests/fixtures/wiki_squad_euro2024.html` (has a "Croatia" section too — check; otherwise trim the cached `data/raw/wiki/wiki_2026_A_2026_fifa_world_cup.html` to three sections and commit it as `tests/fixtures/wiki_squad_wc2026.html`, ≤ 200 KB).

**Interfaces:**
- `config/squads.yaml` gains:
  ```yaml
  peer_squads:   # same page, other sections; the lens compares these squads with the Czech one
    - {country: CRO, section: "Croatia"}
    - {country: DEN, section: "Denmark"}
  ```
  and `nt_core_event: "2026 FIFA World Cup"` (Task 3). The lens event is `nt_core_event`; its Czech page/section is the `events[]` entry with that `event`.
- `src/fetch_squads.py::main` additionally writes `data/processed/peer_squads.parquet` with columns `country, player_norm, player, born, event` (Czech squad included with `country: CZE`).
- `src/squad_lens.py::build_squad_lens(squads: pd.DataFrame, tables: pd.DataFrame, headline, stepping, peer_domestic: dict[str,str], season: str, multipliers: dict) -> dict` returning
  ```python
  {"event": "2026 FIFA World Cup", "season": "2025-2026",
   "countries": [{"country": "CZE", "n": 26, "matched": 25,
                  "tiers": {"top9": 9, "stepping_stone": 3, "domestic": 11, "other": 2, "unmatched": 1},
                  "cohorts": {"U22": 2, "23-25": 8, "26-29": 10, "30+": 6},
                  "median_minutes": 1780.0, "median_multiplier": 0.51}, ...]}
  ```
  Matching: squad row → `tables` rows of `season` with the same `normalize_name(player)` and (when both known) the same `born`, any nation; the tier of the row with the most minutes (`_tier` logic identical to `pathways.profile`, with `peer_domestic` mapping league → country and the squad's `country`); cohort via `international_benchmark.assign_cohort(born, season)`; `median_multiplier` = median of `multipliers[league]` over matched players.
- `render.py::_build_squad_lens(lens, names) -> dict` → context `squad_lens` with `countries` ordered CZE first then by `n top9` desc, tier shares as percentages (one decimal), `cze` row separately.

- [ ] **Step 1: Failing tests**

```python
import pandas as pd
from src.squad_lens import build_squad_lens

HEAD = ["ENG-Premier League"]; STEP = ["AUT-Bundesliga"]; PD = {"CZE-First League": "CZE", "DEN-Superliga": "DEN"}
MULT = {"ENG-Premier League": 1.0, "AUT-Bundesliga": 0.268, "CZE-First League": 0.434, "DEN-Superliga": 0.371}


def _squads():
    return pd.DataFrame({
        "country": ["CZE", "CZE", "CZE", "DEN"], "player": ["A", "B", "C", "D"],
        "player_norm": ["a", "b", "c", "d"], "born": [1995, 2003, 1990, 1999], "event": ["E"] * 4})


def _tables():
    return pd.DataFrame({
        "season": ["2025-2026"] * 4, "player": ["A", "B", "D", "B"], "born": [1995, 2003, 1999, 2003],
        "league": ["ENG-Premier League", "CZE-First League", "DEN-Superliga", "AUT-Bundesliga"],
        "min": [2500, 1200, 900, 300], "nation": ["CZE", "CZE", "DEN", "CZE"], "player_key": ["a|1995", "b|2003", "d|1999", "b|2003"]})


def test_lens_counts_tiers_cohorts_and_unmatched():
    out = build_squad_lens(_squads(), _tables(), HEAD, STEP, PD, "2025-2026", MULT)
    cze = next(c for c in out["countries"] if c["country"] == "CZE")
    assert cze["n"] == 3 and cze["matched"] == 2
    assert cze["tiers"] == {"top9": 1, "stepping_stone": 0, "domestic": 1, "other": 0, "unmatched": 1}  # B: most minutes row = CZE league
    assert cze["cohorts"]["U22"] == 1 and cze["median_minutes"] == 1850.0
    den = next(c for c in out["countries"] if c["country"] == "DEN")
    assert den["tiers"]["domestic"] == 1 and den["median_multiplier"] == 0.371
```

- [ ] **Step 2: Run** → `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/squad_lens.py`**

```python
"""Exhibit F: the national-team squad of `nt_core_event` by league tier, cohort and minutes,
next to the peer squads on the same Wikipedia page. Descriptive."""
from __future__ import annotations

import json
import logging

import pandas as pd

from src import config
from src.international_benchmark import assign_cohort
from src.utils import normalize_name, read_parquet

LOG = logging.getLogger(__name__)
TIERS = ["top9", "stepping_stone", "domestic", "other", "unmatched"]
COHORT_LABELS = ["U22", "23-25", "26-29", "30+"]


def _tier(league: str, country: str, headline: list[str], stepping: list[str], peer_domestic: dict) -> str:
    if league in headline:
        return "top9"
    if league in stepping:
        return "stepping_stone"
    if peer_domestic.get(league) == country:
        return "domestic"
    return "other"


def build_squad_lens(squads: pd.DataFrame, tables: pd.DataFrame, headline: list[str], stepping: list[str],
                     peer_domestic: dict[str, str], season: str, multipliers: dict[str, float]) -> dict:
    t = tables[tables.season == season].copy()
    t["player_norm"] = t.player.map(normalize_name)
    countries = []
    for country, sq in squads.groupby("country", sort=False):
        rows = []
        for r in sq.itertuples():
            cand = t[t.player_norm == r.player_norm]
            if pd.notna(r.born) and "born" in cand.columns:
                cand = cand[cand.born.isna() | (cand.born == r.born)]
            if cand.empty:
                rows.append({"tier": "unmatched", "min": None, "league": None, "born": r.born})
                continue
            best = cand.sort_values("min", ascending=False).iloc[0]
            rows.append({"tier": _tier(best.league, country, headline, stepping, peer_domestic),
                         "min": int(cand["min"].sum()), "league": best.league, "born": r.born})
        df = pd.DataFrame(rows)
        matched = df[df.tier != "unmatched"]
        cohorts = {c: 0 for c in COHORT_LABELS}
        for b in df.born.dropna():
            c = assign_cohort(int(b), season)
            if c in cohorts:
                cohorts[c] += 1
        mult = matched.league.map(multipliers).dropna()
        countries.append({
            "country": country, "n": int(len(df)), "matched": int(len(matched)),
            "tiers": {k: int((df.tier == k).sum()) for k in TIERS},
            "cohorts": cohorts,
            "median_minutes": float(matched["min"].median()) if len(matched) else None,
            "median_multiplier": round(float(mult.median()), 3) if len(mult) else None,
        })
    return {"event": str(squads.event.iloc[0]) if len(squads) else "", "season": season, "countries": countries}


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    cfg, lq = config.leagues(), config.load_yaml("league_quality.yaml")
    squads = read_parquet(config.PROCESSED_DIR / "peer_squads.parquet")
    tables = read_parquet(config.PROCESSED_DIR / "fbref_players.parquet")
    peer_domestic = {lg: c for lg, c in cfg.get("peer_domestic", {}).items()}
    peer_domestic[cfg["domestic"]] = "CZE"
    out = build_squad_lens(squads, tables, list(cfg["headline"]), list(cfg.get("stepping_stone", [])),
                           peer_domestic, config.seasons()["metrics"], lq["multipliers"])
    (config.PROCESSED_DIR / "squad_lens.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for c in out["countries"]:
        LOG.info("%s: %d in squad, %d matched, tiers %s", c["country"], c["n"], c["matched"], c["tiers"])


if __name__ == "__main__":
    main()
```

Check `config.leagues()["peer_domestic"]`'s value shape (`{league: {country: …}}` or `{league: country}`) in `config/leagues.yaml` and adapt the one-line comprehension. `assign_cohort` returns `"U22"`, `"23-25"`, `"26-29"`, `"30+"` — verify against `international_benchmark.COHORTS` and use its labels verbatim.

`src/fetch_squads.py::main`: after the loop, parse the peer sections of the `nt_core_event` page:
```python
    cfg = config.load_yaml("squads.yaml")
    core = next(e for e in cfg["events"] if e["event"] == cfg["nt_core_event"])
    html = _fetch_html(core["url"], f"wiki_{core['year']}_{core['team']}_{normalize_name(core['event']).replace(' ', '_')}")
    peers = [parse_squad_section(html, core["section"]).assign(country="CZE")]
    for p in cfg.get("peer_squads", []):
        peers.append(parse_squad_section(html, p["section"]).assign(country=p["country"]))
    ps = pd.concat(peers, ignore_index=True).assign(event=core["event"])
    write_parquet(ps[["country", "player_norm", "player", "born", "event"]], config.PROCESSED_DIR / "peer_squads.parquet")
```

`render.py`: `load_data` adds `"squad_lens": _load_json(p / "squad_lens.json", {})`; `_build_squad_lens(lens, names)` returns `{"event", "season_label", "rows": [...]}` with each row `{country, name, n, matched, top9_pct, stepping_pct, domestic_pct, other_pct, unmatched, cohorts, median_minutes, median_multiplier}`; CZE row first. Template (after exhibit E, same `<h3>`/table pattern as exhibit D): heading `ch2.f.h3` "F · The {event} squad by league tier", framing `ch2.f.p` ("Where the {n} players named to the {event} squad played in {season}, next to {peers}. Tier = the league of the player's most-minutes {season} row."), table columns country · squad · top-9 % · stepping % · domestic % · other % · median minutes · median multiplier · U22 / 23–25 / 26–29 / 30+; note `ch2.f.note` (`*` footnote: "{unmatched} squad players have no {season} row in the fetched leagues and are counted as unmatched."). CS for all keys. Makefile: `benchmark:` target appends `$(ACT) python -m src.squad_lens`; `fetch` already runs `src.fetch_squads`.

- [ ] **Step 4: Run** `uv run pytest -q`; `uv run python -m src.fetch_squads && uv run python -m src.squad_lens && uv run python -m src.render`; open `outputs/index.html`, exhibit F present with CZE/CRO/DEN.

- [ ] **Step 5: Commit** — `git commit -m "Exhibit F: WC 2026 squads by league tier, cohort and minutes (CZE vs CRO, DEN)"`

---

### Task 5: Executive summary findings + method note

**Files:**
- Modify: `src/render.py` (`_build_findings`, context key `findings`), `templates/report.html.j2` (block right after the hero `</section>`, before the exec-summary chapter), `src/i18n.py`, `config/i18n/cs.yaml`, `docs/modern.css`? — no: styling lives in `site/` (`docs/modern.css` is built from `site/`; check `site/build.sh` for where `modern.css` comes from and edit the source, not `docs/`).
- Test: `tests/test_render.py`

**Interfaces:**
- `render.py::_build_findings(hero, gaps, pathways, squad_lens, seasons, tr) -> list[dict]` → five `{"text": str, "foot": str}`; each `text` ends with `*`; `foot` names the number's source. Sources (all already in the context): (1) per-capita rank + density; (2) largest cohort gap; (3) recent export age CZE vs DEN; (4) exhibit C minutes share (`pathways["fare"]` CZE row vs the lowest/highest peer — use the keys that `_build_pathways` produces; read them, do not guess); (5) exhibit E sideways share; if `squad_lens` is present, finding (5) becomes the WC squad top-9 share vs CRO/DEN and sideways moves to (4)'s footnote — no: keep five fixed findings, (5) = squad lens top-9 share when available, else sideways share.
- Method note: static i18n `method.note.title`, `method.note.body` (one paragraph: "Nothing here is specific to Czech football: the pipeline takes a nationality code, a peer set and a league list. Run for England it would produce the same exhibits for English players abroad and at home. Its data are free-tier FBref tables; the same code path accepts richer event or tracking features as extra columns of the feature vector.") + CS.

- [ ] **Step 1: Failing test**

```python
def test_findings_are_five_and_each_ends_with_asterisk():
    ctx = build_context_from_fixtures("en")
    assert len(ctx["findings"]) == 5
    assert all(f["text"].endswith("*") and f["foot"] for f in ctx["findings"])
    html = render_html(ctx)
    assert 'class="findings"' in html and "Method note" in html
```

- [ ] **Step 2: Run** → KeyError `findings`.

- [ ] **Step 3: Implement.** `_build_findings` pulls numbers from `hero`, `gaps[0]`, `pathways["export_cze"]/["export_den"]`, the fare row for CZE (min share) and the destinations summary (`sideways_share`) or `squad_lens`. EN keys `finding.1..5` with placeholders, `finding.1.foot` … Template:

```html
<section class="findings" id="findings">
  <div class="container">
    <h3>{{ t('findings.h3') }}</h3>
    <ol class="findings-list">
      {% for f in findings %}<li><p>{{ f.text }}</p><p class="mono-foot">{{ f.foot }}</p></li>{% endfor %}
    </ol>
    <aside class="method-note"><h4>{{ t('method.note.title') }}</h4><p>{{ t('method.note.body') }}</p></aside>
  </div>
</section>
```
CSS in the site source stylesheet: `.findings-list` numbered, `.mono-foot` mono small, `.method-note` bordered box in the palette's navy/cream (see existing `.capita-note`/`.hero-footnote` rules for the conventions). Add `findings` to the TOC (`toc.findings` key) and `build_context_from_fixtures` gets a `findings` fixture.

- [ ] **Step 4: Run** `uv run pytest -q`; render both languages.

- [ ] **Step 5: Commit** — `git commit -m "Five computed findings and a method note after the hero"`

---

### Task 6: Data-quality log

**Files:**
- Create: `src/data_quality.py`, `config/data_quality_events.yaml`, `tests/test_data_quality.py`
- Modify: `src/render.py` (load + `_build_data_quality`), `templates/report.html.j2` (chapter IV, before Limitations), `src/i18n.py`, `config/i18n/cs.yaml`, `Makefile` (`render:` depends on `data-quality:` target = `python -m src.data_quality`)

**Interfaces:**
- `config/data_quality_events.yaml` — recorded incidents (typed dates and counts are *recorded facts*, flagged as such):
  ```yaml
  events:
    - id: season_index_stale
      date: 2026-09-14
      recorded_count: 9
      unit: leagues
      en: "A stale FBref season index made soccerdata fetch the season-less URL, which FBref serves as the season in progress: nine leagues' 2025/26 tables were 2026/27 after four rounds. Fixed by checking the page's own heading against the requested season."
      cs: "…"
    - id: clubelo_down
      date: 2026-09-13
      en: "ClubElo's API answered 502 for the whole run; league multipliers fell back to UEFA association coefficients."
      cs: "…"
    - id: photo_occupation
      date: 2026-09-13
      recorded_count: 7
      unit: portraits
      en: "The Wikidata portrait query matched on name, citizenship and birth date only; seven portraits belonged to namesakes in other sports until an occupation filter was added."
      cs: "…"
  ```
- `src/data_quality.py::compute_checks(pool, tables, features_by_group, nt_flags) -> list[dict]` — computed rows, each `{"id", "count", "unit"}`:
  - `women_filtered`: rows of the country page dropped by `is_feminine_surname` — recompute from the cached country page via `pool.parse_country_page` + `pool.is_feminine_surname` (read `data/raw/.../country_cze.html` through `soccerdata`'s data dir, path in `pool.fetch_country_page`'s cache: `fb.data_dir / "country_cze.html"`; if absent, `count: None`).
  - `namesakes`: active pool players sharing a normalised name (`pool.player_norm.duplicated(keep=False).sum()` — `pool.parquet` has `player`, derive norm with `normalize_name`).
  - `no_tables`: `(~pool.in_fbref_tables).sum()`.
  - `split_seasons`: player-season-group rows collapsed by `collapse_player_seasons` across the three feature frames (sum of `len(df) − len(collapsed)`).
  - `nt_unmatched`: squad-table names (`nt_flags.parquet`) that match no Czech-eligible row in any features frame.
  - `missing_born`: table rows of nation CZE with `born` NA.
- Output `data/processed/data_quality.json`: `{"checks": [...], "events": [...]}`.
- `render.py::_build_data_quality(dq, tr)` → rows for a two-part table: computed checks (label from `dq.<id>.label`, count, unit) and recorded events (date, text, `recorded_count` shown as "recorded").

- [ ] **Step 1: Failing test** (`tests/test_data_quality.py`)

```python
import pandas as pd
from src.data_quality import compute_checks


def test_checks_count_split_seasons_and_no_tables():
    pool = pd.DataFrame({"player": ["Ladislav Krejčí", "Ladislav Krejčí", "Jan Novák"], "in_fbref_tables": [True, True, False]})
    tables = pd.DataFrame({"nation": ["CZE", "CZE"], "born": [1999, pd.NA]})
    fw = pd.DataFrame({"player_key": ["x|1", "x|1"], "season": ["2025-2026"] * 2, "pos_group": ["FW"] * 2,
                       "min": [500, 400], "league": ["A", "B"], "team": ["a", "b"], "npg_p90": [0.1, 0.2],
                       "czech_eligible": [True, True], "player": ["X", "X"]})
    nt = pd.DataFrame({"player_norm": ["x", "ghost"], "born": [1, 2]})
    rows = {r["id"]: r["count"] for r in compute_checks(pool, tables, {"FW": fw}, nt, country_page_html=None)}
    assert rows["namesakes"] == 2 and rows["no_tables"] == 1
    assert rows["split_seasons"] == 1 and rows["missing_born"] == 1 and rows["nt_unmatched"] == 1
    assert rows["women_filtered"] is None
```

Read `src/utils.py::collapse_player_seasons`'s required columns before writing the fixture; the test frame must satisfy them (add columns as needed; the assertion is on the count).

- [ ] **Step 2: Run** → fails to import.

- [ ] **Step 3: Implement** `src/data_quality.py` per the interface (`compute_checks(pool, tables, feats, nt, country_page_html)`; `main()` loads processed files, reads the cached country page if present, merges `config/data_quality_events.yaml`, writes the JSON). Template block in chapter IV before Limitations:

```html
<h3 id="data-quality">{{ t('ch4.dq.h3') }}</h3>
<p>{{ t('ch4.dq.p') }}</p>
<table class="dq-table"><thead><tr><th>{{ t('ch4.dq.col.check') }}</th><th>{{ t('ch4.dq.col.count') }}</th><th>{{ t('ch4.dq.col.what') }}</th></tr></thead>
<tbody>{% for r in data_quality.checks %}<tr><td>{{ r.label }}</td><td class="num">{{ r.count if r.count is not none else '—' }} {{ r.unit }}</td><td>{{ r.what }}</td></tr>{% endfor %}</tbody></table>
<ul class="dq-events">{% for e in data_quality.events %}<li><span class="mono">{{ e.date }}</span> {{ e.text }}{% if e.recorded_count %} <span class="mono">({{ t('ch4.dq.recorded', n=e.recorded_count, unit=e.unit) }})</span>{% endif %}</li>{% endfor %}</ul>
```
i18n: `ch4.dq.h3` "Data-quality log", `ch4.dq.p` "Every wrangling decision that changed a count, with the count. The first block is recomputed on every run; the second is the incident record (dates and counts as recorded at the time).", `dq.<id>.label` + `dq.<id>.what` for the six checks, `ch4.dq.recorded` "{n} {unit}, recorded", CS for all. Add `data-quality` to the TOC.

- [ ] **Step 4: Run** tests; `uv run python -m src.data_quality && uv run python -m src.render`.

- [ ] **Step 5: Commit** — `git commit -m "Data-quality log: recomputed checks and the recorded incident list"`

---

### Task 7: "How this was built", tracking credential, README

**Files:**
- Modify: `templates/report.html.j2` (chapter IV after Reproducibility: `#how-built`), `src/i18n.py`, `config/i18n/cs.yaml`, `src/render.py` (`facts["n_tests"]` computed by counting `def test_` in `tests/*.py`; `facts["n_rulings"]` = count of lines starting with `Ruling:` or containing `Ruling:` in `docs/superpowers/ledgers/2026-09-12-v1-progress.md`), `README.md`
- Test: `tests/test_render.py`

**Interfaces:** context keys `facts.n_tests`, `facts.n_rulings`, `ledger_url`, `spec_url`, `plan_url` (GitHub blob URLs under `repo_url`).

- [ ] **Step 1: Failing test**

```python
def test_how_built_section_counts_tests_and_rulings():
    ctx = build_context_from_fixtures("en")
    html = render_html(ctx)
    assert 'id="how-built"' in html and str(ctx["facts"]["n_tests"]) in html
```

- [ ] **Step 2: Run** → fails.

- [ ] **Step 3: Implement.** Section copy (EN, CS mirrored):
  - `ch4.built.h3` "How this was built"
  - `ch4.built.p1` "The report was produced with an agentic workflow: a written design spec, an implementation plan of small tasks, a fresh coding agent per task, a spec-compliance and code-quality review after each, a whole-branch review at the end. Every decision the controller made without the author is a dated <em>ruling</em> in a ledger — {n_rulings} for the first edition. The author wrote the framing, the cluster reads and the rulings; the agents wrote the code under {n_tests} tests."
  - `ch4.built.p2` "Spec: <a href=\"{spec}\">design</a> · plan: <a href=\"{plan}\">tasks</a> · ledger: <a href=\"{ledger}\">rulings</a>."
  - a 5-node inline diagram (spec → plan → task agent → reviews → ledger) as a `<ol class="build-flow">` with CSS arrows in the site stylesheet — no image.
  - Limitations: append `lim.tracking` — title "No event or tracking data", body "Every feature here is a season aggregate from free FBref tables. The author's tracking work lives elsewhere: <a href=\"https://github.com/sandovabarbora/tactical-cz\">tactical-cz</a> (broadcast-video player tracking for Czech football) and the hockey video PoC linked from <a href=\"https://hockey.datasimply.eu\">hockey.datasimply.eu</a>." — verify both URLs resolve (`curl -sI`) before committing; if a URL 404s, link the GitHub profile instead and say so in the report file.
  - README: a "Portability" paragraph: the pipeline is nationality-parameterised; processed tables are flat parquet with stable keys (`player_key`, `league`, `season`) and load into BigQuery unchanged (`bq load --source_format=PARQUET`), so the same exhibits can run as SQL over a warehouse.

- [ ] **Step 4: Run** tests; render both languages.

- [ ] **Step 5: Commit** — `git commit -m "How this was built, tracking-data note, portability paragraph"`

---

### Task 8 (controller): site build, snapshot, deploy

- [ ] `make pages`; check `docs/index.html` and `docs/cs/index.html` (findings block, exhibit F, 15 cards, data-quality log, how-built); phone width sanity via the existing site test.
- [ ] `make snapshot`; commit snapshot; final whole-branch review (opus) + one fix wave; merge `v1.1` → `main` (ff), push; verify `https://football.datasimply.eu`.

## Self-review

- Spec §2A coverage: exec summary (T5), method note (T5), fifth rule (T3), WC lens (T4), data-quality log (T6), how built (T7), tracking credential (T7); README BigQuery (T7); season shift (T1, T2). ✔
- Placeholders: none — every step names files, keys and code; T4's `peer_domestic` shape and `assign_cohort` labels are verification instructions, not gaps.
- Type consistency: `showcase_ids(..., nt_core_event)` (T3) ↔ `main()` call; `build_squad_lens` signature (T4) ↔ test; `facts` keys (T1 `nt_years`, T7 `n_tests`, `n_rulings`) ↔ template calls.
