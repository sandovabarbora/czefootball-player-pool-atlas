"""Every pool player's career, season by season -> charts/careers.json.

The report answers questions about the pool; the atlas page (docs/atlas/)
lets a reader pick a player and see his seasons in the covered leagues:
club, league and its rung, minutes, goals and assists per
90 and the same league-adjusted, national-team call-ups, and the
percentile profile of the metrics season. Two players can be laid side by
side, so a trend is a comparison rather than a line on its own.

Sources, all already on disk: `fbref_players.parquet` (every fetched
league-season) unioned with `fbref_history.parquet` (the history years of
the non-headline leagues, src.fetch_history) for the raw seasons;
`config.league_quality()` multipliers for the league adjustment, the same
factors the feature tables use; `nt_flags.parquet` for call-ups;
`pool_table.json` for the metrics-season profile. A season in a league the
pipeline does not fetch is simply absent, and the page says so.

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


def seasons_table(players: pd.DataFrame, history: pd.DataFrame | None) -> pd.DataFrame:
    frames = [players] + ([history] if history is not None and len(history) else [])
    t = pd.concat(frames, ignore_index=True).drop_duplicates(["league", "season", "team", "player_key"])
    return t


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
    rows = careers(seasons_table(players, history), pool, nt, mult, cfg, config.features()["min_minutes"], profiles)
    out = config.OUTPUTS_DIR / "charts"
    out.mkdir(parents=True, exist_ok=True)
    payload = {"home": config.HOME, "metrics_season": pt.get("season"), "seasons_covered": sorted(set(players.season) | (set(history.season) if history is not None else set())),
               "min_minutes": config.features()["min_minutes"], "players": rows}
    (out / "careers.json").write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
    LOG.info("careers: %d players, %d seasons covered, history table %s", len(rows), len(payload["seasons_covered"]),
             "present" if history is not None else "absent")


if __name__ == "__main__":
    main()
