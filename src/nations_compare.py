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
    gpanel = {r["country"]: r for r in (gap or {}).get("panel", [])}
    for c in (gap or {}).get("contrasts", []):
        contrasts.append({"contrast": c["contrast"], "gap_total": c["gap_total"], "residual": c.get("residual"),
                          "x2": gpanel.get(c["contrast"], {}).get("x2"), "x3": gpanel.get(c["contrast"], {}).get("x3"),
                          "channels": [{"name": ch["name"], "contribution": ch["contribution"], "share": ch["share"],
                                        "lo": ch.get("lo"), "hi": ch.get("hi")} for ch in c["channels"]]})
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
        "youth": {"share_minutes_u21": ye.get("share_u21"), "share_minutes_u21_upper": ys.get("share_minutes_upper"),
                  "share_starts_u21": ys.get("share_starts"),
                  "regulars_per_club": ys.get("regulars_per_club"), "share_le22": age.get("share_le22"),
                  "weighted_mean_age": age.get("weighted_mean_age")},
        "export": {"first_move_median_age": fm.get("median_age"), "first_move_n": fm.get("n"),
                   "export_age_recent": er.get("median_export_age_recent"), "origin_shares": er.get("origin_shares"),
                   "fare_min_share": fare.get("median_min_share")},
        "squad": {"event": (lens or {}).get("event"), "top9_share": sq_top9, "n": sq.get("matched")},
        "big5": {"n": series.get("n"), "seasons": (b5 or {}).get("seasons"),
                 "break": {"season": (brk.get("modal") or (brk.get("top") or [{}])[0]).get("season"),
                           "prob": (brk.get("modal") or (brk.get("top") or [{}])[0]).get("prob"),
                           "factor": (brk.get("delta_factor") or {}).get("median"),
                           "lo": (brk.get("delta_factor") or {}).get("lo"), "hi": (brk.get("delta_factor") or {}).get("hi")},
                 "rise": ({"season": (brk["rise"].get("modal") or brk["rise"]["top"][0])["season"],
                           "prob": (brk["rise"].get("modal") or brk["rise"]["top"][0])["prob"],
                           "factor": brk["rise"]["delta_factor"]["median"],
                           "lo": brk["rise"]["delta_factor"].get("lo"), "hi": brk["rise"]["delta_factor"].get("hi")}
                          if brk.get("rise") and brk["rise"]["delta_factor"]["median"] > 1 else None)},
        "decomposition": {"contrasts": contrasts, "coefficients": (gap or {}).get("coefficients"), "n": (gap or {}).get("n"),
                          "ridge_alpha": (gap or {}).get("ridge_alpha"),
                          "home_x2": gpanel.get(code, {}).get("x2"), "home_x3": gpanel.get(code, {}).get("x3")},
        "origins": origins,
        # the youth-share link measured two ways (src.youth_panel): across
        # countries, and within countries season to season -- the second is
        # the one that would speak to change, and is the honest zero so far
        "youth_link": ({"between": (yp.get("between") or {}).get("beta_per_10pp"), "within": (yp.get("within") or {}).get("beta_per_10pp"),
                        "n_countries": yp.get("n_countries"), "n": yp.get("n"), "seasons": yp.get("seasons_used")} if yp else None),
    }


def _existing_long_run() -> dict | None:
    p = config.ROOT_DIR / "outputs" / "nations" / "nations.json"
    return json.loads(p.read_text(encoding="utf-8")).get("long_run") if p.exists() else None


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
        share = lambda a: [None if pd.isna(x) or not x else round(float(v / x), 5) for v, x in zip(a.to_numpy(), tot.to_numpy())]
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


def _f2(x: float) -> str:
    return f"{x:.2f}".replace("-", "−")


def _signed(x: float, d: int = 2) -> str:
    if round(x, d) == 0:
        return f"{0:.{d}f}"
    return f"{x:+.{d}f}".replace("-", "−")


def _num(x: float) -> str:
    """22 -> '22', 22.5 -> '22.5' (no rounding of a half-year median)."""
    return f"{x:g}"


def _trend(values: list[float | None]) -> dict | None:
    """OLS slope of a short yearly series, per season, with its 90 % CI
    (t distribution, n - 2 degrees of freedom)."""
    from scipy import stats
    pts = [(i, v) for i, v in enumerate(values) if v is not None]
    if len(pts) < 4:
        return None
    x = np.array([p[0] for p in pts], dtype=float)
    y = np.array([p[1] for p in pts], dtype=float)
    res = stats.linregress(x, y)
    tq = stats.t.ppf(0.95, len(x) - 2)
    return {"slope": float(res.slope), "lo": float(res.slope - tq * res.stderr), "hi": float(res.slope + tq * res.stderr), "n": len(x)}


def takeaways(home: str, editions: list[dict], long: dict | None, recent: dict | None, reforms: list[dict], names: dict[str, str]) -> list[dict]:
    """Up to five descriptive findings for one home nation, each generated
    from the numbers it rests on, in the order a reader needs them: the long
    run, the decomposition, the recent youth-minutes series, where the nation
    ranks on the pathway measures, and the two reform sequences. Every
    estimate carries its interval and interval type; every count its n; no
    finding gives advice or reads a cause into a timing or an association
    (editorial standard v1, 29 September 2026)."""
    name = lambda c: names.get(c, c)   # noqa: E731
    ed = next((e for e in editions if e["code"] == home), None)
    items: list[dict] = []
    # 1 · the long run, from the edition's own change-point fit (the one its Big-5 page shows)
    if long and home in long["countries"] and ed and ed["big5"].get("break", {}).get("season"):
        h = long["countries"][home]
        n = h["n"]
        peak = max(n)
        peak_s = long["seasons"][n.index(peak)]
        br, rise = ed["big5"]["break"], ed["big5"].get("rise")
        inc = br.get("lo") is not None and br["lo"] <= 1.0 <= br["hi"]
        kind = "fall" if br["factor"] < 1 else "rise"
        fall = (f"The change-point model’s most probable season for the {kind} is {season_slash(br['season'])} "
                f"(posterior {br['prob'] * 100:.0f} %), a level change of ×{_f2(br['factor'])} (90 % HDI {_f2(br['lo'])}–{_f2(br['hi'])})"
                + (f"; that interval includes ×1.00, so the {kind} is not distinguishable from no change at the 90 % level." if inc else "."))
        kind2 = "rise" if rise and rise["factor"] > 1 else "fall"
        rise_txt = (f" Its most probable season for the other step, a {kind2}, is {season_slash(rise['season'])} (posterior {rise['prob'] * 100:.0f} %), "
                    f"×{_f2(rise['factor'])} (90 % HDI {_f2(rise['lo'])}–{_f2(rise['hi'])})." if rise and rise.get("lo") is not None else "")
        gen = ""
        i_fall = long["seasons"].index(br["season"]) if br["season"] in long["seasons"] else None
        age = h.get("age_median", [None] * len(n))
        if i_fall is not None and age[i_fall] is not None and age[n.index(peak)] is not None:
            deb = h["debut_n"][i_fall]
            gen = (f"\n\nThe median age of the nation’s Big-5 players was {age[n.index(peak)]:.0f} at the {season_slash(peak_s)} peak and "
                   f"{age[i_fall]:.0f} in {season_slash(br['season'])}, when " + ("no player" if deb == 0 else f"{deb} player{'s' if deb != 1 else ''}") + f" made a first Big-5 season of {MIN_MINUTES}+ minutes.")
        if home in BIG_FIVE:
            head = f"{ed['adjective']} players with {MIN_MINUTES}+ Big-5 minutes: {peak} at the {season_slash(peak_s)} peak, {n[-1]} in {season_slash(long['seasons'][-1])}; most of them play in their own league."
        else:
            head = f"{ed['adjective']} players with {MIN_MINUTES}+ minutes in the Big-5 leagues: {peak} at the {season_slash(peak_s)} peak, {n[-1]} in {season_slash(long['seasons'][-1])}."
        items.append({"head": head, "body": fall + rise_txt + " A break model dates a change in level; it identifies no cause." + gen})
    # 2 · the decomposition, with intervals, the sign of the league term and the zero export-age channel
    if ed and ed["decomposition"]["contrasts"]:
        dec = ed["decomposition"]
        n_c = dec.get("n")
        parts = []
        for c in dec["contrasts"]:
            ch = {x["name"]: x for x in c["channels"]}
            parts.append(f"against {name(c['contrast'])} ({_f2(c['gap_total'])} per million) youth minutes go with {_signed(ch['u21_share']['contribution'])} "
                         f"(90 % bootstrap interval {_signed(ch['u21_share']['lo'])} to {_signed(ch['u21_share']['hi'])}), league strength with "
                         f"{_signed(ch['league_strength']['contribution'])} ({_signed(ch['league_strength']['lo'])} to {_signed(ch['league_strength']['hi'])}) "
                         f"and export age with {_signed(ch['export_age']['contribution'])}, residual {_signed(c['residual'])}")
        body = ("In a ridge fit over " + str(n_c) + " countries, " + "; ".join(parts) + ".")
        b2 = ((dec.get("coefficients") or {}).get("b") or {}).get("x2")
        if b2 is not None and dec.get("home_x2") is not None:
            if b2 < 0:
                body += (f"\n\nThe league-strength coefficient in this fit is negative ({_signed(b2, 1)} per unit of the league multiplier): a weaker home league goes with more players "
                         f"in the top-ranked leagues per million, so a peer whose league is weaker than {name(home)}’s (m_L {dec['home_x2']:.3f}) gets a positive league-strength contribution.")
            else:
                body += f"\n\nThe league-strength coefficient in this fit is positive ({_signed(b2, 1)} per unit of the league multiplier): a stronger home league goes with more players per million."
        x3s = [dec.get("home_x3")] + [c.get("x3") for c in dec["contrasts"]]
        if None not in x3s and len(set(x3s)) == 1:
            trio = [name(home)] + [name(c["contrast"]) for c in dec["contrasts"]]
            body += (" The export-age channel is zero by construction: " + ", ".join(trio[:-1]) + " and " + trio[-1]
                     + f" share the same median age at the first top-9 season among recent entrants ({_num(x3s[0])}).")
        body += " The split describes an association across few, correlated national measures; it is not a causal accounting."
        items.append({"head": f"The per-head gap to {' and '.join(name(c['contrast']) for c in dec['contrasts'])}, split over three measured channels (descriptive).",
                      "body": body})
    # 3 · the recent youth-minutes series: a slope with its interval, not two endpoints
    if recent and home in recent.get("leagues", {}):
        S = recent["seasons"]
        v = recent["leagues"][home]["u21_share"]
        tr = _trend(v)
        if tr:
            upper = (ed or {}).get("youth", {}).get("share_minutes_u21_upper")
            v_hi = list(v)
            if upper is not None and v_hi[-1] is not None and upper - v_hi[-1] >= 0.001:
                v_hi[-1] = upper
            tr_hi = _trend(v_hi) if v_hi != v else None
            series = ", ".join("—" if x is None else f"{x * 100:.1f}" for x in v)
            body = (f"The share by season, {season_slash(S[0])} to {season_slash(S[-1])}: {series} %. An OLS line through the {tr['n']} seasons falls by "
                    if tr["slope"] < 0 else f"The share by season, {season_slash(S[0])} to {season_slash(S[-1])}: {series} %. An OLS line through the {tr['n']} seasons rises by ")
            body += (f"{abs(tr['slope']) * 100:.2f} percentage points a season (90 % CI {_signed(tr['lo'] * 100)} to {_signed(tr['hi'] * 100)} pp)"
                     + (", an interval that includes zero." if tr["lo"] <= 0 <= tr["hi"] else "."))
            if tr_hi:
                body += (f" The last season’s share is a floor (FBref leaves part of the league’s rows without a nationality): at its ceiling of {upper * 100:.1f} % the slope is "
                         f"{_signed(tr_hi['slope'] * 100)} pp a season (90 % CI {_signed(tr_hi['lo'] * 100)} to {_signed(tr_hi['hi'] * 100)}).")
            peers = [c["contrast"] for c in ((ed or {}).get("decomposition") or {}).get("contrasts", []) if c["contrast"] in recent["leagues"]]
            others = []
            for c in peers + [c for c in recent["leagues"] if c not in peers and c != home]:
                w = recent["leagues"][c]["u21_share"]
                if len(w) < 2 or w[-1] is None or w[-2] is None:
                    continue
                # the comparison countries always; any other league only where its last step also fell by 2 points or more
                if c in peers or w[-1] - w[-2] <= -0.02:
                    others.append(f"{name(c)} {w[-2] * 100:.1f} → {w[-1] * 100:.1f} %")
            if others:
                body += (f" The last step, {season_slash(S[-2])} to {season_slash(S[-1])}, for the comparison countries and for other leagues whose share also fell "
                         f"by 2 points or more: " + "; ".join(others) + ".")
            items.append({"head": f"{name(home)}’s own under-21 nationals’ share of home-league minutes over {len(S)} seasons: a trend of "
                                  f"{_signed(tr['slope'] * 100)} pp a season (90 % CI {_signed(tr['lo'] * 100)} to {_signed(tr['hi'] * 100)}).",
                          "body": body})
    # 4 · where the nation ranks on the pathway measures, with values and samples, no targets
    if ed and ed.get("mechanisms") and home in ed["mechanisms"]:
        M = ed["mechanisms"]
        n_all = len(M)

        def rank(key, higher_is_better=True):
            vals = [(c, M[c][key]) for c in M if M[c].get(key) is not None]
            if not vals or M[home].get(key) is None:
                return None
            ordered = sorted(vals, key=lambda kv: (-kv[1] if higher_is_better else kv[1]))
            mine = M[home][key]
            ahead = sum(1 for _, x in ordered if (x > mine if higher_is_better else x < mine))
            same = sum(1 for _, x in ordered if x == mine)
            pos = f"{ahead + 1}" if same == 1 else f"{ahead + 1}–{ahead + same}"
            return pos, len(ordered), (None if ordered[0][0] == home else ordered[0])
        h = M[home]
        lines = []
        def best(r, label, fmt):
            return f" ({label}: {name(r[2][0])} {fmt(r[2][1])})" if r[2] else ""
        r = rank("share_u21")
        if r:
            up = (ed.get("youth") or {}).get("share_minutes_u21_upper")
            lines.append(f"under-21 share of home-league minutes {h['share_u21'] * 100:.1f} %"
                         + (f" (a floor; up to {up * 100:.1f} %)" if up and up - h["share_u21"] >= 0.001 else "")
                         + f", {r[0]} of {r[1]}" + best(r, "highest", lambda v: f"{v * 100:.1f} %"))
        r = rank("regulars_per_club")
        if r:
            lines.append(f"regular under-21 starters per club {h['regulars_per_club']:.2f}, {r[0]} of {r[1]}" + best(r, "highest", lambda v: f"{v:.2f}"))
        r = rank("first_move_age", False)
        if r:
            lines.append(f"median age at the first season with real playing time abroad {_num(h['first_move_age'])} (n = {h['first_move_n']}), "
                         f"{r[0]} of {r[1]} from youngest" + best(r, "youngest", _num))
        r = rank("first_move_n")
        if r:
            lines.append(f"first moves abroad in the covered seasons {h['first_move_n']}, {r[0]} of {r[1]}" + best(r, "most", str))
        r = rank("multiplier")
        if r:
            lines.append(f"home-league UEFA-coefficient multiplier ×{h['multiplier']:.2f}, {r[0]} of {r[1]}")
        r = rank("fare_min_share")
        if r:
            lines.append(f"median share of club minutes for exports {h['fare_min_share'] * 100:.0f} %, {r[0]} of {r[1]}")
        og = ed.get("origins")
        if og and og["n"] >= 10:
            lines.append(f"{og['top2_share'] * 100:.0f} % of the {og['n']} players who went from the home league to a top-9 league since {season_slash(og['from'])} left from {' or '.join(og['top2'])}")
        if lines:
            items.append({
                "head": f"Where {name(home)} ranks among {n_all} countries on the pathway measures, {season_slash(recent['seasons'][-1]) if recent else ''} (1 = highest share, youngest age, most moves).",
                "body": "; ".join(lines)[:1].upper() + "; ".join(lines)[1:] + ". These are descriptive ranks on medians and counts without intervals, so neighbouring ranks can swap with a few players; none of them is shown to cause the per-head count.",
            })
    # 5 · the two documented reforms, as sequences
    if long and long.get("youth") and reforms:
        cases = []
        cite = {"honigstein2015": "Honigstein, 2015", "premierleague2011": "Premier League, 2011"}
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
            if before is None or peak_after is None or now is None:
                continue
            cases.append(f"{name(r['country'])} after its {r['label']} ({season_slash(r['season'])}; {cite.get(r['ref'], r['ref'])}): its own under-21 nationals played "
                         f"{before * 100:.0f} % of {Y['league'].split('-', 1)[1]} minutes the season before, {peak_after * 100:.0f} % at the highest point within twelve seasons "
                         f"({season_slash(peak_season)}) and {now * 100:.0f} % in {season_slash(long['seasons'][-1])}")
        if cases:
            items.append({
                "head": "Youth minutes in Germany and England after two academy reforms (descriptive).",
                "body": ". ".join(cases) + ". Each is one sequence in one country without a comparison group, so it describes timing and does not estimate an effect of either reform.",
            })
    return items


def season_slash(season: str) -> str:
    """'2014-2015' -> '2014/15'."""
    return f"{season[:4]}/{season[7:9]}" if season and len(season) == 9 else str(season)


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--reuse-long-run", action="store_true",
                    help="keep long_run (the per-country change-point fits) from the existing outputs/nations/nations.json "
                         "instead of refitting it; everything else is recomputed")
    args = ap.parse_args()
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
        "long_run": (_existing_long_run() if args.reuse_long_run else None) or (long_run(big5, countries) if big5 is not None else None),
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
