"""Exhibit F: the national-team squad of `nt_core_event` by league tier, cohort and minutes,
next to the peer squads on the same Wikipedia page (`nation()["squads"]["peer_squads"]`).
Descriptive only -- no player-selection recommendation.

Inputs:
    data/processed/peer_squads.parquet (src.fetch_squads; CZE + peer countries'
        squads for `nt_core_event`, one row per player)
    data/processed/fbref_players.parquet
    config/leagues.yaml (headline, stepping_stone, peer_domestic, domestic)
    config/league_quality.yaml (multipliers)
    config/seasons.yaml (metrics season)

Output:
    data/processed/squad_lens.json
"""

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
    """One row per squad country: tier/cohort counts, median minutes and median league multiplier.

    Matching a squad row to `tables`: same `normalize_name(player)` and, when
    both are known, the same `born` (any nation -- a squad player can be
    tracked at a club under a different roster nationality than their
    national team). Of a matched player's candidate rows (season == `season`),
    the one with the most minutes decides both the tier (`_tier`, same
    top9 -> stepping_stone -> domestic -> other precedence as
    `src.pathways.profile`) and the `min` reported for that player -- a
    single club/league's minutes, not summed across a mid-season move.
    `median_minutes` is the median of those per-player minutes over matched
    players only; `median_multiplier` is the median of
    `multipliers[league]` over the same matched players' tier-defining
    league. A squad player with no candidate row at all is `unmatched`.
    Cohorts (`international_benchmark.assign_cohort`) are computed for
    every squad player with a known birth year, regardless of match status.
    """
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
                         "min": int(best["min"]), "league": best.league, "born": r.born})
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
    cfg, lq = config.leagues(), config.league_quality()
    squads = read_parquet(config.PROCESSED_DIR / "peer_squads.parquet")
    tables = read_parquet(config.PROCESSED_DIR / "fbref_players.parquet")
    # config/leagues.yaml::peer_domestic values are dicts ({comp_id, slug,
    # country, tier}); the league -> country map needs the "country" field,
    # not the dict itself.
    peer_domestic = {lg: v["country"] for lg, v in cfg.get("peer_domestic", {}).items()}
    peer_domestic[config.DOMESTIC_LEAGUE] = config.HOME
    out = build_squad_lens(squads, tables, list(cfg["headline"]), list(cfg.get("stepping_stone", [])),
                           peer_domestic, config.seasons()["metrics"], lq["multipliers"])
    (config.PROCESSED_DIR / "squad_lens.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    for c in out["countries"]:
        LOG.info("%s: %d in squad, %d matched, tiers %s", c["country"], c["n"], c["matched"], c["tiers"])


if __name__ == "__main__":
    main()
