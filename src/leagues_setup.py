"""Register custom FBref competitions with soccerdata (merge, never overwrite).

soccerdata knows the Big-5 out of the box; everything else must be declared in
~/soccerdata/config/league_dict.json. Entries come from config/leagues.yaml's
`custom` and `peer_domestic` sections.

Schema note (verified by reading soccerdata/_config.py and soccerdata/fbref.py,
not by reading the whole package): soccerdata does NOT resolve a competition
from an id or URL. `FBref.read_leagues()` scrapes the https://fbref.com/en/comps/
overview table at request time and matches rows by the exact "FBref" display
name string via `_translate_league` (soccerdata/_common.py, BaseReader). So the
only key soccerdata actually consumes from a league_dict.json entry is:
  - "FBref": the exact competition name as FBref displays it on that page
  - "season_start" / "season_end": month names used to infer single-year vs.
    multi-year season codes (or an explicit "season_code" override)
`comp_id` and `slug` in config/leagues.yaml are NOT read by soccerdata at all
-- they exist purely for humans to sanity-check the competition against its
FBref URL (/en/comps/<comp_id>/<slug>-Stats). Getting the "FBref" name wrong
(not the comp_id) is what actually breaks a fetch.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from src import config

LOG = logging.getLogger(__name__)
LEAGUE_DICT = Path.home() / "soccerdata" / "config" / "league_dict.json"

# Exact FBref display names, verified against soccerdata's own successfully
# cached player tables (~/soccerdata/data/FBref/players_<key>_*_standard.html)
# for NED, BEL, POR, POL, SUI, NOR and confirmed via the FBref seasons page
# cache for HUN. The rest (AUT, SVK, CRO, DEN, TUR, GER-2.Bundesliga) are
# best-knowledge and were verified live during this task's fetch run -- see
# task-2-report.md for corrections.
FBREF_NAME_OVERRIDES: dict[str, str] = {
    "NED-Eredivisie": "Eredivisie",
    "POR-Primeira Liga": "Primeira Liga",
    "BEL-Pro League": "Belgian Pro League",
    "TUR-Süper Lig": "Süper Lig",
    "CZE-First League": "Czech First League",
    "GER-2. Bundesliga": "2. Fußball-Bundesliga",
    "SVK-Super Liga": "Slovak Super Liga",
    "AUT-Bundesliga": "Austrian Football Bundesliga",
    "HUN-NB I": "Nemzeti Bajnokság I",
    "POL-Ekstraklasa": "Ekstraklasa",
    "CRO-HNL": "Croatian Football League",
    "DEN-Superliga": "Danish Superliga",
    "SUI-Super League": "Swiss Super League",
    "NOR-Eliteserien": "Eliteserien",
}

# Most European top flights run Jul/Aug-May (multi-year season code, e.g.
# "2425"). Norway's Eliteserien runs Apr-Dec within a single calendar year
# (single-year season code, e.g. "2024") -- soccerdata infers that from these
# two months, so getting it wrong here silently breaks season resolution.
DEFAULT_SEASON_BOUNDS = ("Jul", "May")
SEASON_BOUNDS_OVERRIDES: dict[str, tuple[str, str]] = {
    "NOR-Eliteserien": ("Apr", "Dec"),
}


def entries() -> dict[str, dict]:
    """Build league_dict.json entries for every `custom` and `peer_domestic` league."""
    out: dict[str, dict] = {}
    all_leagues = {**config.leagues()["custom"], **config.leagues().get("peer_domestic", {})}
    for key, meta in all_leagues.items():
        season_start, season_end = SEASON_BOUNDS_OVERRIDES.get(key, DEFAULT_SEASON_BOUNDS)
        out[key] = {
            "FBref": FBREF_NAME_OVERRIDES.get(key, meta["slug"].replace("-", " ")),
            "season_start": season_start,
            "season_end": season_end,
            # informational only -- not read by soccerdata; kept for traceability
            # against config/leagues.yaml's comp_id/slug.
            "comp_id": meta["comp_id"],
        }
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
