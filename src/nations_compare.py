"""Across the editions: the same five mechanisms side by side, the gap
decomposition of each home nation against its own peers, and the long
run -- every country's presence in the Big-5 since 1990/91 with its two
dated breaks, and how much of each Big-5 league's minutes its own under-21s
got, season by season. -> outputs/nations/nations.json, one file for the
/nations/ page (site/build_nations.py).

What this can and cannot say. The mechanisms are measured the same way for
every nation, so a difference between two nations is a real difference in
the data, and the decomposition (src.gap_decomposition, a cross-country
regression on youth share, league strength and export age) says which
mechanism carries most of a gap. None of it identifies a cause: a reform
date drawn on a series is a timing marker, and "youth minutes rose, then
exports rose" is a sequence, not an effect. The page says so in words.

Inputs: data/processed/<nation>/ for every nation that has a render
(per_capita, pipeline_facts, pathways, squad_lens, gap_decomposition,
series_model, big5_series), plus one Big-5 history table (identical across
nations -- the first one found is used) for the long run.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd

from src import config, series_model
from src.utils import read_parquet

LOG = logging.getLogger(__name__)
MIN_MINUTES = 450          # the Big-5 series' own floor (src.big5_series)
U21_AGE = 21               # src.pathways' convention: age at the season's Jul 1 <= 21

# Documented reform dates drawn as timing markers on the long-run charts --
# keys into config/refs.yaml; each is a date a reader can check, not a claim
# that the reform moved the series.
REFORMS = [
    {"country": "GER", "season": "2001-2002", "label": "DFB/DFL academy licensing", "ref": "honigstein2015"},
    {"country": "ENG", "season": "2012-2013", "label": "Elite Player Performance Plan", "ref": "premierleague2011"},
]


def editions() -> list[str]:
    """Nations with a finished run: a rendered page in outputs/<nation>/."""
    out = []
    for p in sorted((config.ROOT_DIR / "outputs").glob("*/index.html")):
        n = p.parent.name
        if (config.ROOT_DIR / "config" / "nations" / f"{n}.yaml").exists():
            out.append(n)
    return out


def _load(nation: str, name: str):
    p = config.ROOT_DIR / "data" / "processed" / nation / name
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8")) if name.endswith(".json") else read_parquet(p)


def _nation_cfg(nation: str) -> dict:
    import yaml
    return yaml.safe_load((config.ROOT_DIR / "config" / "nations" / f"{nation}.yaml").read_text(encoding="utf-8"))


def edition_summary(nation: str) -> dict | None:
    """The five mechanisms and the decomposition for one edition, read from
    that edition's own outputs -- the numbers its report shows."""
    cfg = _nation_cfg(nation)
    code = cfg["code"]
    pc = _load(nation, "per_capita.parquet")
    facts = _load(nation, "pipeline_facts.json")
    paths = _load(nation, "pathways.json")
    lens = _load(nation, "squad_lens.json")
    gap = _load(nation, "gap_decomposition.json")
    sm = _load(nation, "series_model.json")
    b5 = _load(nation, "big5_series.json")
    yp = _load(nation, "youth_panel.json")
    if pc is None or facts is None or paths is None:
        return None
    row = pc[pc.country == code]
    home_pc = row.iloc[0].to_dict() if len(row) else {}
    ys = next((r for r in facts.get("youth_starts", []) if r["country"] == code), {})
    fm = next((r for r in facts.get("first_move_abroad", []) if r["country"] == code), {})
    age = next((r for r in facts.get("age_structure", []) if r["country"] == code), {})
    ye = next((r for r in paths.get("youth_exposure", []) if r["country"] == code), {})
    er = next((r for r in paths.get("export_route", []) if r["country"] == code), {})
    fare = next((r for r in paths.get("fare", []) if r["country"] == code), {})
    sq = next((r for r in (lens or {}).get("countries", []) if r["country"] == code), {})
    sq_top9 = (sq.get("tiers", {}).get("top9", 0) / sq["matched"]) if sq.get("matched") else None
    peers_pc = pc.sort_values("rank")[["country", "per_million", "rank"]].to_dict("records")
    contrasts = []
    for c in (gap or {}).get("contrasts", []):
        contrasts.append({"contrast": c["contrast"], "gap_total": c["gap_total"], "residual": c.get("residual"),
                          "channels": [{"name": ch["name"], "contribution": ch["contribution"], "share": ch["share"]} for ch in c["channels"]]})
    brk = (sm or {}).get("break") or {}
    series = (b5 or {}).get("countries", {}).get(code, {})
    return {
        "nation": nation, "code": code, "name": cfg["name"], "adjective": cfg["adjective"],
        "population_m": cfg["population_m"], "home_league": cfg["home_league"], "domestic_league": cfg["domestic_league"],
        "per_million": home_pc.get("per_million"), "rank": int(home_pc["rank"]) if home_pc else None, "n_peers": int(len(pc)),
        "peers": peers_pc,
        "youth": {"share_minutes_u21": ye.get("share_u21"), "share_starts_u21": ys.get("share_starts"),
                  "regulars_per_club": ys.get("regulars_per_club"), "share_le22": age.get("share_le22"),
                  "weighted_mean_age": age.get("weighted_mean_age")},
        "export": {"first_move_median_age": fm.get("median_age"), "first_move_n": fm.get("n"),
                   "export_age_recent": er.get("median_export_age_recent"), "origin_shares": er.get("origin_shares"),
                   "fare_min_share": fare.get("median_min_share")},
        "squad": {"event": (lens or {}).get("event"), "top9_share": sq_top9, "n": sq.get("matched")},
        "big5": {"n": series.get("n"), "seasons": (b5 or {}).get("seasons"),
                 "break": {"season": (brk.get("modal") or (brk.get("top") or [{}])[0]).get("season"),
                           "prob": (brk.get("modal") or (brk.get("top") or [{}])[0]).get("prob"),
                           "factor": (brk.get("delta_factor") or {}).get("median")},
                 "rise": ({"season": (brk["rise"].get("modal") or brk["rise"]["top"][0])["season"],
                           "prob": (brk["rise"].get("modal") or brk["rise"]["top"][0])["prob"],
                           "factor": brk["rise"]["delta_factor"]["median"]}
                          if brk.get("rise") and brk["rise"]["delta_factor"]["median"] > 1 else None)},
        "decomposition": {"contrasts": contrasts, "coefficients": (gap or {}).get("coefficients"), "n": (gap or {}).get("n")},
        # the youth-share link measured two ways (src.youth_panel): across
        # countries, and within countries season to season -- the second is
        # the one that would speak to change, and is the honest zero so far
        "youth_link": ({"between": (yp.get("between") or {}).get("beta_per_10pp"), "within": (yp.get("within") or {}).get("beta_per_10pp"),
                        "n_countries": yp.get("n_countries"), "n": yp.get("n"), "seasons": yp.get("seasons_used")} if yp else None),
    }


def union_panel(nations: list[str]) -> list[dict]:
    """The decomposition panel (country: per-million y, youth share x1,
    league strength x2, export age x3) unioned across editions; the same
    country computed by two editions is the same season and formula, so the
    first one wins."""
    seen: dict[str, dict] = {}
    for n in nations:
        gap = _load(n, "gap_decomposition.json")
        for r in (gap or {}).get("panel", []):
            seen.setdefault(r["country"], {k: r.get(k) for k in ("country", "y", "x1", "x2", "x3", "league")})
    return sorted(seen.values(), key=lambda r: r["country"])


def big5_table(nations: list[str]) -> pd.DataFrame | None:
    for n in nations:
        p = config.ROOT_DIR / "data" / "processed" / n / "big5_history.parquet"
        if p.exists():
            return read_parquet(p)
    return None


def long_run(big5: pd.DataFrame, countries: dict[str, dict], fit_breaks: bool = True) -> dict:
    """Every country's Big-5 presence since the history starts (players with
    >= MIN_MINUTES, per season, and per million), with the two-break model
    fitted per country; and each Big-5 league's own-national U-21 minute
    share per season."""
    # seasons every one of the five leagues is present for (see src.big5_series)
    n_leagues = big5.groupby("season")["league"].nunique()
    big5 = big5[big5.season.isin(n_leagues[n_leagues == n_leagues.max()].index)]
    seasons = sorted(big5.season.unique())
    per = big5.groupby(["season", "player_key", "nation"], as_index=False)["min"].sum()
    per = per[per["min"] >= MIN_MINUTES]
    counts = per.groupby(["nation", "season"]).player_key.nunique().unstack("season").reindex(columns=seasons).fillna(0).astype(int)
    # the mechanisms the history can carry back for every country: when its
    # players first reach the Big-5 (age at the first season of >= MIN_MINUTES)
    # and how much of its Big-5 minutes its under-23s play
    b = big5.copy()
    b["age_jul1"] = b["season"].str.slice(0, 4).astype(int) - b["born"]
    first = per.groupby(["nation", "player_key"])["season"].min().rename("first_season").reset_index()
    ages = b.groupby(["nation", "player_key", "season"], as_index=False).agg(age=("age_jul1", "first"), min=("min", "sum"))
    debut = first.merge(ages, left_on=["nation", "player_key", "first_season"], right_on=["nation", "player_key", "season"], how="left")
    debut = debut[debut["min"] >= MIN_MINUTES]
    out_countries = {}
    for code, meta in countries.items():
        if code not in counts.index:
            continue
        y = counts.loc[code].to_numpy()
        d = debut[debut.nation == code].groupby("first_season")["age"]
        deb_n = d.size().reindex(seasons).fillna(0).astype(int)
        deb_age = d.median().reindex(seasons)
        bc = b[b.nation == code]
        tot = bc.groupby("season")["min"].sum().reindex(seasons)
        u23 = bc[bc.age_jul1 <= 23].groupby("season")["min"].sum().reindex(seasons).fillna(0)
        entry = {"name": meta["name"], "population_m": meta["population_m"], "n": [int(v) for v in y],
                 "per_million": [round(float(v) / meta["population_m"], 2) for v in y],
                 "debut_n": [int(v) for v in deb_n.to_numpy()],
                 "debut_age": [None if pd.isna(v) else round(float(v), 1) for v in deb_age.to_numpy()],
                 "u23_share": [None if pd.isna(t) or not t else round(float(u / t), 3) for u, t in zip(u23.to_numpy(), tot.to_numpy())]}
        if fit_breaks and y.sum() >= 5 * len(y):   # a series of near-zeros has no break to date
            t0 = time.time()
            idata, grid = series_model.fit_change_point(y.astype("float64"), n_breaks=2, seed=config.RANDOM_SEED)
            s = series_model.break_summary(idata, y.astype("float64"), grid, seasons)
            entry["breaks"] = {
                "fall": {**s["modal"], "factor": s["delta_factor"]["median"]},
                "other": {**s["rise"]["modal"], "factor": s["rise"]["delta_factor"]["median"],
                          "kind": "rise" if s["rise"]["delta_factor"]["median"] > 1 else "fall"},
                "fall_is_a_fall": s["fall_is_a_fall"],
            }
            LOG.info("%s: two-break fit %.1f s -> %s", code, time.time() - t0, entry["breaks"])
        out_countries[code] = entry
    # own-national under-21 share of each league's minutes, by season
    league_country = {"ENG-Premier League": "ENG", "ITA-Serie A": "ITA", "ESP-La Liga": "ESP",
                      "GER-Bundesliga": "GER", "FRA-Ligue 1": "FRA"}
    youth = {}
    for league, code in league_country.items():
        L = b[b.league == league]
        tot = L.groupby("season")["min"].sum()
        own = L[(L.nation == code)].groupby("season")["min"].sum()
        own_u21 = L[(L.nation == code) & (L.age_jul1 <= U21_AGE)].groupby("season")["min"].sum()
        all_u21 = L[L.age_jul1 <= U21_AGE].groupby("season")["min"].sum()
        youth[code] = {"league": league,
                       "own_share": [round(float(own.get(s, 0) / tot[s]), 4) if s in tot.index and tot[s] else None for s in seasons],
                       "own_u21_share": [round(float(own_u21.get(s, 0) / tot[s]), 4) if s in tot.index and tot[s] else None for s in seasons],
                       "all_u21_share": [round(float(all_u21.get(s, 0) / tot[s]), 4) if s in tot.index and tot[s] else None for s in seasons]}
    return {"seasons": seasons, "min_minutes": MIN_MINUTES, "countries": out_countries, "youth": youth}


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    nations = editions()
    LOG.info("editions with a render: %s", nations)
    countries = config.countries()["peers"]
    eds = [e for e in (edition_summary(n) for n in nations) if e]
    big5 = big5_table(nations)
    payload = {
        "editions": eds,
        "panel": union_panel(nations),
        "countries": {c: {"name": m["name"], "population_m": m["population_m"]} for c, m in countries.items()},
        "long_run": long_run(big5, countries) if big5 is not None else None,
        "reforms": REFORMS,
        "metrics_season": config.seasons()["metrics"],
    }
    out = config.ROOT_DIR / "outputs" / "nations"
    out.mkdir(parents=True, exist_ok=True)
    (out / "nations.json").write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    LOG.info("wrote %s: %d editions, %d panel countries, long run for %d countries",
             out / "nations.json", len(eds), len(payload["panel"]), len((payload["long_run"] or {}).get("countries", {})))


if __name__ == "__main__":
    main()
