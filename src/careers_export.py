"""Every pool player's career, season by season -> charts/careers.json.

The report answers questions about the pool; the atlas page (docs/atlas/)
lets a reader pick a player and see his seasons in the covered leagues:
club, league and its rung, minutes, goals and assists per
90 and the same league-adjusted, national-team call-ups, and the
percentile profile of the metrics season. Two players can be laid side by
side, so a trend is a comparison rather than a line on its own.

Sources, all already on disk: `fbref_players.parquet` (every fetched
league-season) unioned with `fbref_history.parquet` (the history years of
the non-headline leagues, src.fetch_history) and `big5_history.parquet`
(the five biggest leagues back to 1990/91, src.fetch_big5_history) for the
raw seasons -- so a pool player's Big-5 seasons before 2020/21 are there too;
`config.league_quality()` multipliers for the league adjustment, the same
factors the feature tables use; `nt_flags.parquet` for call-ups;
`pool_table.json` for the metrics-season profile. A season in a league the
pipeline does not fetch is simply absent, and the page says so.

Two more files ride along when the Big-5 history exists: `careers_history.json`,
the same shape for every home-nation player of that history who is not in
today's pool (Nedvěd is searchable, with his Lazio and Juventus seasons),
and `eras.json`, the nation in the Big-5 season by season since 1990/91.

Rates here are raw per-90 times the league multiplier, not the shrunk
rates the report's own metrics use, so a ten-minute cameo shows as the
noisy thing it is; the page marks seasons under the inclusion floor.
"""

from __future__ import annotations

import json
import logging

import pandas as pd

from src import config
from src.pool_table import _tier
from src.utils import normalize_name, read_parquet

LOG = logging.getLogger(__name__)


def seasons_table(players: pd.DataFrame, *more: pd.DataFrame | None) -> pd.DataFrame:
    frames = [players] + [m for m in more if m is not None and len(m)]
    t = pd.concat(frames, ignore_index=True).drop_duplicates(["league", "season", "team", "player_key"])
    return t


def past_players(big5: pd.DataFrame, pool: pd.DataFrame, min_minutes: int) -> pd.DataFrame:
    """Home-nation players of the Big-5 history who are not in today's pool,
    shaped like pool rows, so `careers` can treat them the same. The floor
    keeps out the one-appearance names (each would be a panel with one
    dimmed bar); a player who once had a real season anywhere is kept."""
    h = big5[(big5.nation == config.HOME) & ~big5.player_key.isin(pool.player_key)]
    keep = h.groupby("player_key")["min"].max()
    keep = keep[keep >= min_minutes].index
    h = h[h.player_key.isin(keep)].sort_values("season")
    last = h.groupby("player_key").tail(1)
    return pd.DataFrame({
        "player_key": last.player_key.values, "fbref_id": None, "player": last.player.values,
        "born": last.born.values, "pos_group": [str(v).split(",")[0] if isinstance(v, str) and v else None for v in last.pos.values],
        "club_current": None,
    })


def eras(big5: pd.DataFrame) -> list[dict]:
    """The home nation in the Big-5, season by season since the history
    starts: how many, how many minutes, how old, how many debutants and at
    what age -- and who. A player's debut is his first Big-5 season in the
    table, so the first season of the history has none by construction."""
    h = big5[big5.nation == config.HOME].copy()
    seasons_all = sorted(big5.season.unique())
    covered = big5.groupby("season")["league"].nunique()   # FBref's Ligue 1 starts 1995/96, the PL page 1992/93
    first = h.groupby("player_key")["season"].min()
    h["debut"] = (h["season"] == h["player_key"].map(first)) & (h["season"] != seasons_all[0])
    out = []
    for s in seasons_all:
        g = h[h.season == s]
        per = g.groupby("player_key").agg(name=("player", "first"), min=("min", "sum"), age=("age", "first"),
                                          debut=("debut", "any"), team=("team", "first"), league=("league", "first"),
                                          gls=("gls", "sum"), ast=("ast", "sum")).sort_values("min", ascending=False)
        deb = per[per.debut & (per["min"] >= 450)]
        ages = per["age"].dropna()
        out.append({
            "season": s, "n": int(len(per)), "min": int(per["min"].sum()), "leagues": int(covered.get(s, 0)),
            "age_median": float(ages.median()) if len(ages) else None,
            "u23_share": round(float((ages <= 22).mean()), 3) if len(ages) else None,
            "debut_n": int(len(deb)), "debut_age_median": float(deb["age"].median()) if len(deb) else None,
            "leagues": {k: int(v) for k, v in per.league.value_counts().items()},
            "players": [{"key": k, "name": r["name"], "team": r["team"], "league": r["league"], "min": int(r["min"]),
                         "age": None if pd.isna(r["age"]) else int(r["age"]), "debut": bool(r["debut"]), "gls": int(r["gls"]), "ast": int(r["ast"])}
                        for k, r in per.iterrows()],
        })
    return out


def _pos_from_rows(rows: pd.DataFrame) -> str | None:
    last = rows[rows.season == rows.season.max()].sort_values("min", ascending=False)
    for v in last["pos"]:
        if isinstance(v, str) and v:
            return v.split(",")[0].strip()
    return None


def careers(tables: pd.DataFrame, pool: pd.DataFrame, nt: pd.DataFrame, mult: dict, cfg: dict,
            min_minutes: int, profiles: dict[str, dict]) -> list[dict]:
    headline, stepping, domestic = cfg["headline"], cfg["stepping_stone"], config.DOMESTIC_LEAGUE
    keys = set(pool["player_key"])
    t = tables[tables.player_key.isin(keys)].copy()
    t["m"] = t["league"].map(mult).astype(float)
    t["npg"] = (t["gls"] - t["pk"]).clip(lower=0)
    calls = {}
    for r in nt.itertuples():
        calls.setdefault((normalize_name(r.player), int(r.born) if pd.notna(r.born) else None), []).append({"event": r.event, "year": int(r.year), "team": r.team})
    out = []
    for p in pool.itertuples():
        rows = t[t.player_key == p.player_key].sort_values(["season", "min"], ascending=[True, False])
        if rows.empty:
            continue
        seasons = []
        for s, g in rows.groupby("season", sort=True):
            stints = []
            for r in g.itertuples():
                m90 = r.min / 90.0 if r.min else 0.0
                stints.append({
                    "league": r.league, "team": r.team, "tier": _tier(r.league, headline, stepping, domestic),
                    "min": int(r.min), "mp": int(r.mp), "gls": int(r.gls), "ast": int(r.ast), "npg": int(r.npg),
                    "ga90": round((r.npg + r.ast) / m90, 3) if m90 else None,
                    "ga90_adj": round((r.npg + r.ast) / m90 * r.m, 3) if m90 and pd.notna(r.m) else None,
                    "age": None if pd.isna(r.age) else int(r.age),
                })
            lead = max(stints, key=lambda x: x["min"])
            seasons.append({"season": s, "min": sum(x["min"] for x in stints), "lead": lead["league"], "team": lead["team"],
                            "tier": lead["tier"], "age": lead["age"], "under_floor": sum(x["min"] for x in stints) < min_minutes,
                            "stints": stints})
        born = None if pd.isna(p.born) else int(p.born)
        # the pool table leaves goalkeepers (and a few others) without a
        # group; the position FBref lists for his longest recent stint fills it
        pos = p.pos_group if isinstance(p.pos_group, str) and p.pos_group else _pos_from_rows(rows)
        out.append({
            "key": p.player_key, "name": p.player, "fbref_id": p.fbref_id, "born": born,
            "pos": pos, "club_now": p.club_current or None,
            "calls": calls.get((normalize_name(p.player), born), []),
            "profile": profiles.get(p.player_key),
            "seasons": seasons,
        })
    return out


def generations(big5: pd.DataFrame, tables: pd.DataFrame, cfg: dict, min_minutes: int, metrics: str) -> dict:
    """The home nation by birth year: how many of each cohort ever had a
    Big-5 season of `min_minutes`, at what age the first came, and who --
    the generation behind the peak and the gap behind it, in one table.
    The Big-5 history starts in the mid-1990s, so cohorts born before about
    1972 are cut off on the left (a player born in 1965 who left the Big-5
    before 1995 is not seen); the youngest cohorts are still arriving.
    And where the covered era's exports come from: the last home-league
    club before a player's first headline-league season."""
    h = big5[big5.nation == config.HOME]
    per = h.groupby(["player_key", "season"], as_index=False)["min"].sum()
    per = per[per["min"] >= min_minutes]
    born = h.groupby("player_key")["born"].first()
    name = h.groupby("player_key")["player"].first()
    minutes = h.groupby("player_key")["min"].sum()
    first = per.groupby("player_key")["season"].min()
    year_end = int(metrics[:4]) + 1
    rows = []
    if len(first):
        df = pd.DataFrame({"born": born.reindex(first.index), "first": first, "min": minutes.reindex(first.index), "name": name.reindex(first.index)}).dropna(subset=["born"])
        df["born"] = df["born"].astype(int)
        df["age"] = df["first"].str.slice(0, 4).astype(int) - df["born"]
        y0 = max(int(df.born.min()), int(big5.season.min()[:4]) - 24)
        for y in range(y0, year_end - 17):
            g = df[df.born == y].sort_values("min", ascending=False)
            rows.append({"born": y, "n": int(len(g)), "first_age": None if g.empty else float(g["age"].median()),
                         "names": [{"key": k, "name": r["name"], "min": int(r["min"]), "first": r["first"], "age": int(r["age"])} for k, r in g.head(6).iterrows()],
                         "left_censored": y < int(big5.season.min()[:4]) - 20, "right_censored": y > year_end - 24})
    # where the covered era's exports come from
    headline, domestic = set(cfg["headline"]), config.DOMESTIC_LEAGUE
    t = tables[tables.player_key.isin(set(tables[tables.league == domestic].player_key))]
    first_head = t[t.league.isin(headline)].groupby("player_key")["season"].min()
    origins = []
    for key, s in first_head.items():
        home_before = t[(t.player_key == key) & (t.league == domestic) & (t.season < s)]
        if home_before.empty:
            continue
        last = home_before.sort_values(["season", "min"]).iloc[-1]
        origins.append({"key": key, "name": last["player"], "club": last["team"], "season": s, "born": None if pd.isna(last["born"]) else int(last["born"])})
    by_club = {}
    for o in origins:
        by_club.setdefault(o["club"], []).append(o)
    clubs = sorted(({"club": c, "n": len(v), "players": sorted(v, key=lambda o: o["season"])} for c, v in by_club.items()), key=lambda x: -x["n"])
    return {"home": config.HOME, "min_minutes": min_minutes, "history_from": big5.season.min(), "cohorts": rows,
            "origins": {"from": tables.season.min(), "to": metrics, "clubs": clubs, "n": len(origins)}}


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    p, cfg = config.PROCESSED_DIR, config.leagues()
    players = read_parquet(p / "fbref_players.parquet")
    hist_path = p / "fbref_history.parquet"
    history = read_parquet(hist_path) if hist_path.exists() else None
    pool = read_parquet(p / "pool.parquet")
    nt = read_parquet(p / "nt_flags.parquet")
    pt_path = p / "pool_table.json"
    pt = json.loads(pt_path.read_text()) if pt_path.exists() else {"rows": []}
    profiles = {r["player_key"]: {"season": pt.get("season"), "rank": r.get("rank_q"), "n": r.get("n_group"),
                                  "axes": r.get("profile"), "q": r.get("q"), "min_share": r.get("min_share")}
                for r in pt["rows"]}
    mult = config.league_quality()["multipliers"]
    floor = config.features()["min_minutes"]
    big5_path = p / "big5_history.parquet"
    big5 = read_parquet(big5_path) if big5_path.exists() else None
    tables = seasons_table(players, history, big5)
    rows = careers(tables, pool, nt, mult, cfg, floor, profiles)
    out = config.OUTPUTS_DIR / "charts"
    out.mkdir(parents=True, exist_ok=True)
    payload = {"home": config.HOME, "metrics_season": pt.get("season"), "seasons_covered": sorted(set(players.season) | (set(history.season) if history is not None else set())),
               "min_minutes": floor, "players": rows}
    (out / "careers.json").write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
    LOG.info("careers: %d players, %d seasons covered, history table %s", len(rows), len(payload["seasons_covered"]),
             "present" if history is not None else "absent")
    if big5 is None:
        return
    # the past: every home-nation player of the Big-5 history outside today's
    # pool (a second file, loaded by the page only when asked for), and the
    # nation in the Big-5 season by season
    past = careers(tables, past_players(big5, pool, floor), nt, mult, cfg, floor, {})
    (out / "careers_history.json").write_text(json.dumps(
        {"home": config.HOME, "first_season": min(big5.season), "players": past}, separators=(",", ":"), ensure_ascii=False))
    (out / "generations.json").write_text(json.dumps(
        generations(big5, seasons_table(players, history), cfg, floor, pt.get("season") or max(players.season)), separators=(",", ":"), ensure_ascii=False))
    (out / "eras.json").write_text(json.dumps(
        {"home": config.HOME, "seasons": eras(big5), "metrics_season": pt.get("season")}, separators=(",", ":"), ensure_ascii=False))
    LOG.info("history: %d past players, %d seasons of the nation in the Big-5", len(past), big5.season.nunique())


if __name__ == "__main__":
    main()
