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
    mult = config.league_quality()["multipliers"]
    mech = {}
    for r in peers_pc:
        c = r["country"]
        y = next((x for x in paths.get("youth_exposure", []) if x["country"] == c), {})
        st = next((x for x in facts.get("youth_starts", []) if x["country"] == c), {})
        f = next((x for x in facts.get("first_move_abroad", []) if x["country"] == c), {})
        fa = next((x for x in paths.get("fare", []) if x["country"] == c), {})
        mech[c] = {"per_million": r["per_million"], "share_u21": y.get("share_u21"), "regulars_per_club": st.get("regulars_per_club"),
                   "first_move_age": f.get("median_age"), "first_move_n": f.get("n"), "fare_min_share": fa.get("median_min_share"),
                   "multiplier": mult.get(y.get("league") or st.get("league") or "")}
    contrasts = []
    for c in (gap or {}).get("contrasts", []):
        contrasts.append({"contrast": c["contrast"], "gap_total": c["gap_total"], "residual": c.get("residual"),
                          "channels": [{"name": ch["name"], "contribution": ch["contribution"], "share": ch["share"]} for ch in c["channels"]]})
    brk = (sm or {}).get("break") or {}
    series = (b5 or {}).get("countries", {}).get(code, {})
    # where the covered era's exports left from (charts/generations.json, src.careers_export)
    gen_path = config.ROOT_DIR / "outputs" / nation / "charts" / "generations.json"
    origins = None
    if gen_path.exists():
        o = json.loads(gen_path.read_text(encoding="utf-8")).get("origins") or {}
        if o.get("n"):
            top2 = sum(c["n"] for c in o["clubs"][:2])
            origins = {"n": o["n"], "n_clubs": len(o["clubs"]), "top2_share": round(top2 / o["n"], 3), "top2": [c["club"] for c in o["clubs"][:2]],
                       "from": o.get("from"), "to": o.get("to")}
    return {
        "nation": nation, "code": code, "name": cfg["name"], "adjective": cfg["adjective"],
        "population_m": cfg["population_m"], "home_league": cfg["home_league"], "domestic_league": cfg["domestic_league"],
        "per_million": home_pc.get("per_million"), "rank": int(home_pc["rank"]) if home_pc else None, "n_peers": int(len(pc)),
        "peers": peers_pc,
        "mechanisms": mech,
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
        "origins": origins,
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
        ages_s = ages[(ages.nation == code) & (ages["min"] >= MIN_MINUTES)].groupby("season")["age"].median().reindex(seasons)
        entry = {"name": meta["name"], "population_m": meta["population_m"], "n": [int(v) for v in y],
                 "per_million": [round(float(v) / meta["population_m"], 2) for v in y],
                 "age_median": [None if pd.isna(v) else round(float(v), 1) for v in ages_s.to_numpy()],
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


def recent_youth(nations: list[str], countries: dict[str, dict]) -> dict:
    """Own-national under-21 (and under-23) share of every covered league's
    minutes for the recent seasons the pipeline fetched in full (2020/21 on
    for the headline leagues; the history fetch for the rest) -- the
    within-country change the cross-section cannot see. The domestic table
    of the first nation found is used together with its history table; the
    leagues are the same for every nation."""
    frames = []
    for n in nations:
        for name in ("fbref_players.parquet", "fbref_history.parquet"):
            p = config.ROOT_DIR / "data" / "processed" / n / name
            if p.exists():
                frames.append(read_parquet(p))
        if frames:
            break
    if not frames:
        return {}
    t = pd.concat(frames, ignore_index=True).drop_duplicates(["league", "season", "team", "player_key"])
    lg = config.leagues()
    # top flights only: the second tiers in the fetched set (GER-2. Bundesliga) are not a country's home league here
    league_country = {**{k: v["country"] for k, v in lg["custom"].items() if v.get("tier", 1) == 1},
                      **{k: v["country"] for k, v in lg.get("peer_domestic", {}).items() if v.get("tier", 1) == 1},
                      "ENG-Premier League": "ENG", "ITA-Serie A": "ITA", "ESP-La Liga": "ESP", "GER-Bundesliga": "GER", "FRA-Ligue 1": "FRA"}
    t = t[t.league.isin(league_country)]
    t["age_jul1"] = t["season"].str.slice(0, 4).astype(int) - t["born"]
    metrics = config.seasons()["metrics"]
    seasons = sorted(s for s in t.season.unique() if s <= metrics)   # complete seasons only
    out = {}
    for league, code in league_country.items():
        if code not in countries:
            continue
        L = t[(t.league == league) & t.season.isin(seasons)]
        if L.empty:
            continue
        tot = L.groupby("season")["min"].sum().reindex(seasons)
        own21 = L[(L.nation == code) & (L.age_jul1 <= U21_AGE)].groupby("season")["min"].sum().reindex(seasons).fillna(0)
        own23 = L[(L.nation == code) & (L.age_jul1 <= 23)].groupby("season")["min"].sum().reindex(seasons).fillna(0)
        share = lambda a: [None if pd.isna(x) or not x else round(float(v / x), 4) for v, x in zip(a.to_numpy(), tot.to_numpy())]
        out[code] = {"league": league, "u21_share": share(own21), "u23_share": share(own23)}
    return {"seasons": seasons, "leagues": out}


# ---------------------------------------------------------------- the conclusions, written from the numbers
CHANNEL = {"u21_share": "youth minutes at home", "league_strength": "home-league strength", "export_age": "the age of the first move"}
BIG_FIVE = {"ENG", "FRA", "GER", "ESP", "ITA"}


def _short(season: str) -> str:
    return f"{season[2:4]}/{season[7:9]}"


def _pct(v, d=0) -> str:
    return "—" if v is None else f"{v * 100:.{d}f} %"


def _steps(v: dict) -> list[dict]:
    b = v["breaks"]
    out = [{"season": s["season"], "factor": s["factor"], "kind": "rise" if s["factor"] > 1 else "fall"} for s in (b["fall"], b["other"])]
    return sorted(out, key=lambda s: s["season"])


def takeaways(home: str, editions: list[dict], long: dict | None, recent: dict | None, reforms: list[dict], names: dict[str, str]) -> list[dict]:
    """Four statements for one home nation, each written from the numbers
    it rests on (the page says so), in the order a reader needs them: the
    long run, the decomposition, the recent trend, the causal reading."""
    name = lambda c: names.get(c, c)   # noqa: E731
    ed = next((e for e in editions if e["code"] == home), None)
    items: list[dict] = []
    # 1 · the long run
    if long and home in long["countries"] and long["countries"][home].get("breaks"):
        L = long
        small = [(c, v) for c, v in L["countries"].items() if c not in BIG_FIVE and v.get("breaks")]
        h = L["countries"][home]
        hs, n = _steps(h), h["n"]
        peak = max(n)
        peak_s = L["seasons"][n.index(peak)]
        ends_in_fall = [c for c, v in small if _steps(v)[1]["kind"] == "fall"]
        came_back = [(c, _steps(v)) for c, v in small if _steps(v)[0]["kind"] == "fall" and _steps(v)[1]["kind"] == "rise" and _steps(v)[1]["factor"] >= 1.2]
        if home in BIG_FIVE:
            items.append({
                "head": f"{name(home)}'s Big-5 count is mostly its own league: {n[-1]} players with 450+ Big-5 minutes now, {peak} at the {_short(peak_s)} peak.",
                "body": "The steps the model dates — " + ", then ".join(f"{s['kind']} in {_short(s['season'])} (×{s['factor']:.2f})" for s in hs) +
                        " — say how international the home league became, not how many of its players play abroad; the mechanisms below are the sharper read.",
            })
        elif hs[1]["kind"] == "fall":
            others = [c for c in ends_in_fall if c != home]
            who = f"one of {len(others) + 1} small nations" if others else "the one small nation"
            back = "; ".join(f"{name(c)} fell too ({_short(st[0]['season'])}) and came back {int(st[1]['season'][:4]) - int(st[0]['season'][:4])} seasons later" for c, st in came_back)
            # the generation behind the peak and the fall: who was there, how old, whether anyone followed
            i_fall = L["seasons"].index(hs[1]["season"])
            age_fall, deb_fall = h.get("age_median", [None] * len(n))[i_fall], h["debut_n"][i_fall]
            i_peak = L["seasons"].index(peak_s)
            age_peak = h.get("age_median", [None] * len(n))[i_peak]
            gen = ""
            if age_fall is not None and age_peak is not None:
                gen = (f" At the {_short(peak_s)} peak the nation's Big-5 players had a median age of {age_peak:.0f}; in the {_short(hs[1]['season'])} fall season it was {age_fall:.0f} and "
                       f"{'no debutant arrived' if deb_fall == 0 else str(deb_fall) + ' debutant' + ('s' if deb_fall != 1 else '') + ' arrived'} — a generation retired and what followed was thinner.")
            items.append({
                "head": f"{name(home)} is {who} whose Big-5 presence fell and has not come back.",
                "body": f"It rose in {_short(hs[0]['season'])} (×{hs[0]['factor']:.2f}) and fell in {_short(hs[1]['season'])} (×{hs[1]['factor']:.2f}); "
                        f"{n[-1]} players with 450+ Big-5 minutes now against {peak} at the {_short(peak_s)} peak.{gen}\n\n{back + '. ' if back else ''}"
                        "Every other small peer's later step is a rise.",
            })
        else:
            items.append({
                "head": f"{name(home)}'s Big-5 presence: " + ", then ".join(f"{s['kind']} in {_short(s['season'])} (×{s['factor']:.2f})" for s in hs) + ".",
                "body": f"{n[-1]} players with 450+ Big-5 minutes now, {peak} at the {_short(peak_s)} peak. "
                        + (f"{len(ends_in_fall)} small peer{'s' if len(ends_in_fall) != 1 else ''} ({', '.join(name(c) for c in ends_in_fall)}) ended in a fall." if ends_in_fall else "No small peer's later step is a fall."),
            })
    # 2 · the decomposition
    if ed and ed["decomposition"]["contrasts"]:
        cs = [(c, max(c["channels"], key=lambda ch: ch["contribution"])) for c in ed["decomposition"]["contrasts"]]
        behind = [(c, top) for c, top in cs if c["gap_total"] > 0]
        ahead = [(c, top) for c, top in cs if c["gap_total"] <= 0]
        tops = list(dict.fromkeys(top["name"] for c, top in behind))
        if behind:
            clause = "; ".join(f"against {name(c['contrast'])} {CHANNEL[top['name']]} carries {_pct(top['share']) if top['share'] is not None else 'most'} of a {c['gap_total']:.1f}-per-million gap" for c, top in behind)
            items.append({
                "head": "Two problems at once, not one: which mechanism carries the gap depends on the peer." if len(tops) > 1
                        else f"One mechanism carries the gap to every peer it trails: {CHANNEL[tops[0]]}.",
                "body": clause[0].upper() + clause[1:] + ". " + ("They add up rather than compete: a league that gives its young few minutes and is weak besides loses on both counts." if len(tops) > 1 else ""),
            })
        elif ahead:
            clause = "; ".join(f"ahead of {name(c['contrast'])} by {abs(c['gap_total']):.1f} per million, {CHANNEL[top['name']]} carrying {_pct(top['share']) if top['share'] is not None else 'most'} of it" for c, top in ahead)
            items.append({"head": f"{name(home)} is ahead of the peers it is measured against, and the same mechanisms say why.",
                          "body": clause[0].upper() + clause[1:] + "."})
    # 3 · the recent trend
    if recent and home in recent.get("leagues", {}) and long:
        S = recent["seasons"]
        v = recent["leagues"][home]["u21_share"]
        a = next((x for x in v if x is not None), None)
        b = next((x for x in reversed(v) if x is not None), None)
        i0, i1 = (long["seasons"].index(S[0]) if S[0] in long["seasons"] else -1), (long["seasons"].index(S[-1]) if S[-1] in long["seasons"] else -1)

        def pm_change(c):
            cc = long["countries"].get(c)
            return None if not cc or i0 < 0 or i1 < 0 else cc["per_million"][i1] - cc["per_million"][i0]

        peers = [c["contrast"] for c in (ed["decomposition"]["contrasts"] if ed else []) if c["contrast"] in recent["leagues"]]
        peer_text = "; ".join(
            f"{name(c)} {_pct(next(x for x in recent['leagues'][c]['u21_share'] if x is not None))} → {_pct(next(x for x in reversed(recent['leagues'][c]['u21_share']) if x is not None))}"
            + (f" and {pm_change(c):+.1f} per million in the Big-5" if pm_change(c) is not None else "") for c in peers)
        d_home = pm_change(home)
        if a is not None and b is not None:
            flat = abs(b - a) < 0.015   # a point and a half is a wobble, not a trend
            head = (f"No trend at home: {name(home)}'s own under-21s held at {_pct(b)} of home-league minutes across {len(S)} seasons." if flat else
                    f"The trend runs {'the wrong' if b < a else 'the right'} way: {name(home)}'s own under-21s went from {_pct(a)} to {_pct(b)} of home-league minutes in {len(S)} seasons.")
            items.append({
                "head": head,
                "body": (f"Over the same seasons {peer_text}" if peer_text else "Over the same seasons") + (f"; {name(home)} {d_home:+.1f} per million" if d_home is not None else "")
                        + f". Across the {len(recent['leagues'])} covered leagues the change in youth minutes and the change in Big-5 presence lean the same way — a weak signal with the right sign, not a law.",
            })
    # 5 · where the nation is out of line with its peers, and what the peers show is reachable
    if ed and ed.get("mechanisms") and home in ed["mechanisms"]:
        M = ed["mechanisms"]
        peers = [c for c in M if c != home]
        # rank the home nation on each mechanism (1 = best); "better" is more youth, earlier move, stronger league, more exports
        def rank(key, higher_is_better=True):
            vals = [(c, M[c][key]) for c in M if M[c].get(key) is not None]
            if not vals or M[home].get(key) is None:
                return None
            ordered = sorted(vals, key=lambda kv: (-kv[1] if higher_is_better else kv[1]))
            return [c for c, _ in ordered].index(home) + 1, len(ordered), ordered[0]
        r_u21 = rank("share_u21"); r_reg = rank("regulars_per_club"); r_age = rank("first_move_age", False)
        r_mult = rank("multiplier"); r_fare = rank("fare_min_share"); r_n = rank("first_move_n")
        h = M[home]
        weak, fine, labels = [], [], []
        best = lambda r: f" ({name(r[2][0])} {r[2][1]:.0f})" if r[2][0] != home else ""   # noqa: E731
        if r_u21 and r_reg:
            is_weak = r_u21[0] > (r_u21[1] + 1) // 2
            (weak if is_weak else fine).append(
                f"minutes for its own under-21s at home: {_pct(h['share_u21'], 1)} of league minutes and {h['regulars_per_club']:.1f} regular under-21 starters per club, "
                f"{'last' if r_u21[0] == r_u21[1] else str(r_u21[0]) + ' of ' + str(r_u21[1])} among the peers "
                f"({name(r_u21[2][0])} {_pct(r_u21[2][1], 1)}; {name(r_reg[2][0])} {r_reg[2][1]:.1f} starters per club)")
            if is_weak: labels.append("the first rung — minutes for its own under-21s")
        if r_age:
            is_weak = r_age[0] > (r_age[1] + 1) // 2
            (weak if is_weak else fine).append(
                f"the first move abroad at a median {h['first_move_age']:.0f}{best(r_age)}; the exporters move at 22–23")
            if is_weak: labels.append("the timing of the first move")
        if r_mult:
            (fine if r_mult[0] <= (r_mult[1] + 1) // 2 else weak).append(
                f"the home league itself: multiplier ×{h['multiplier']:.2f}, {r_mult[0]} of {r_mult[1]} among the peers")
        if r_fare:
            is_weak = r_fare[0] > (r_fare[1] + 1) // 2
            (weak if is_weak else fine).append(
                f"how its exports fare: a median {_pct(h['fare_min_share'])} of their club's minutes, {r_fare[0]} of {r_fare[1]}")
            if is_weak: labels.append("how its exports fare once abroad")
        if r_n:
            is_weak = r_n[0] > (r_n[1] + 1) // 2
            (weak if is_weak else fine).append(f"how many leave at all: {h['first_move_n']} first moves in the covered seasons ({name(r_n[2][0])} {r_n[2][1]})")
            if is_weak: labels.append("how many leave at all")
        # the breadth of the ladder: how many clubs the exports leave from (only editions whose home league is not itself top-9)
        og = ed.get("origins")
        if og and og["n"] >= 10:
            others = [(e["code"], e["origins"]) for e in editions if e.get("origins") and e["origins"]["n"] >= 10 and e["code"] != home]
            wide = sorted(others, key=lambda kv: kv[1]["top2_share"])[:1]
            line = (f"how many clubs the exports leave from: {_pct(og['top2_share'])} of the {og['n']} players who went from the home league to a top-9 league since {_short(og['from'])} "
                    f"left from {' or '.join(og['top2'])}" + (f" ({name(wide[0][0])}: {_pct(wide[0][1]['top2_share'])} from its top two, {wide[0][1]['n']} exports in all)" if wide else ""))
            if og["top2_share"] >= 0.45:
                weak.append(line); labels.append("the breadth of the ladder")
            else:
                fine.append(line)
        if weak:
            body = f"Out of line: {'; '.join(weak)}." + (f"\n\nNot the problem: {'; '.join(fine)}." if fine else "") + "\n\n"
            # what the peers show is reachable, on the mechanisms where the home nation trails
            targets = []
            if r_reg and r_reg[0] > (r_reg[1] + 1) // 2:
                top3 = sorted(((c, M[c]["regulars_per_club"]) for c in peers if M[c].get("regulars_per_club")), key=lambda kv: -kv[1])[:3]
                targets.append(f"two regular under-21 starters per club (from {h['regulars_per_club']:.1f}) — {', '.join(f'{name(c)} {v:.1f}' for c, v in top3)} already do")
            if r_age and r_age[0] > (r_age[1] + 1) // 2:
                targets.append(f"the first move at 22–23, not {h['first_move_age']:.0f} — the route the peers that grew use")
            if r_n and r_n[0] > (r_n[1] + 1) // 2 and r_fare and r_fare[0] <= (r_fare[1] + 1) // 2:
                targets.append("more of them, not better ones: the exports that do go hold their place")
            watch = "The four numbers to watch every summer: under-21 share, regular under-21 starters per club, age of the first move, first Big-5 seasons."
            reach = ("What the peers show is reachable: " + "; ".join(targets) + ".\n\n") if targets else ""
            items.append({
                "head": f"Where the mistake shows: {name(home)} is out of line on {' and '.join(labels[:2])}.",
                "body": body + reach + watch + " None of this is a proven cause; it is where the nation is out of line with the peers that grew, on the mechanisms the gap decomposition weighs most.",
            })

    # 4 · the causal reading
    if long and long.get("youth") and reforms:
        cases = []
        for r in reforms:
            Y = long["youth"].get(r["country"])
            if not Y or r["season"] not in long["seasons"]:
                continue
            i = long["seasons"].index(r["season"])
            before = Y["own_u21_share"][max(0, i - 1)]
            after = [x for x in Y["own_u21_share"][i:i + 12] if x is not None]
            peak_after = max(after) if after else None
            peak_season = long["seasons"][Y["own_u21_share"].index(peak_after, i)] if peak_after is not None else None
            now = next((x for x in reversed(Y["own_u21_share"]) if x is not None), None)
            rose = peak_after is not None and before is not None and peak_after >= before * 1.5
            held = now is not None and before is not None and now >= before * 1.5
            cases.append((r, Y, before, peak_after, peak_season, now, rose, held))
        if cases:
            text = ". ".join(
                (f"{name(r['country'])} after its {r['label']} ({_short(r['season'])}): its own under-21s' share of {Y['league'].split('-', 1)[1]} minutes went from {_pct(before)} to {_pct(peak_after)} by {_short(peak_season)}"
                 + (f" and is {_pct(now)} now — the turn held" if held else f" but is {_pct(now)} now — the turn did not hold"))
                if rose else
                f"{name(r['country'])} after its {r['label']} ({_short(r['season'])}): no such turn ({_pct(before)} before, {_pct(peak_after)} at best after)"
                for r, Y, before, peak_after, peak_season, now, rose, held in cases)
            items.append({
                "head": f"Can a reform cause it? The data can follow {'one documented case' if len(cases) == 1 else str(len(cases)) + ' documented cases'}, and only as a sequence.",
                "body": text + ". A sequence in one country against none in another is the strongest thing this data can say; it is not a counterfactual. "
                        "Read as a heuristic: minutes for the young at home are the lever a federation holds, the effect is counted in seasons, and a weaker league yields less from it.",
            })
    return items


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
        "recent": recent_youth(nations, countries),
        "reforms": REFORMS,
        "metrics_season": config.seasons()["metrics"],
    }
    names = {c: m["name"] for c, m in countries.items()}
    payload["takeaways"] = {e["code"]: takeaways(e["code"], eds, payload["long_run"], payload["recent"], REFORMS, names) for e in eds}
    out = config.ROOT_DIR / "outputs" / "nations"
    out.mkdir(parents=True, exist_ok=True)
    (out / "nations.json").write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    LOG.info("wrote %s: %d editions, %d panel countries, long run for %d countries",
             out / "nations.json", len(eds), len(payload["panel"]), len((payload["long_run"] or {}).get("countries", {})))


if __name__ == "__main__":
    main()
