"""Every player in the pool, as a row -- not just the handful the cards pick.

Chapter III shows seventeen players, each chosen by a rule ("highest
quality-adjusted production among FW", "youngest national-team call-up").
That is a defensible selection and a bad answer to the only question a
federation reader actually arrives with, which is about one named player.
A reader who looks for Vladimír Darida and does not find him cannot tell
whether he is absent from the pool, absent from the data, or merely absent
from a list of seventeen -- three very different facts.

This module emits the whole thing: one row per home-eligible player with a
metrics-season row, carrying what the report already measures about him
(minutes, quality-adjusted production and its rank in his position group)
plus what `src.fetch_roles` added (starts against substitute appearances,
how long he lasts in a start, crossing and defensive volume). The row is
enough to render both a filterable table and a card written in plain
football language, and it is emitted per POSITION GROUP rank so a player is
compared with his own kind rather than with the whole pool.

Mid-season movers get one row, not two. A player who left the domestic
league in January belongs to one career, so his minutes are summed, his
rates minutes-weighted, and each club he played for is kept in `stints`
with its own tier -- Ladislav Krejčí's 2025/26 is a Czech First League
midfielder's half-season followed by a Premier League defender's, and a
table that hides either half is lying about the most interesting player in
the pool.

Goalkeepers come from `fbref_keepers.parquet` and carry goals against and
save percentage instead of production, with `pos_group` "GK": the report
keeps them as a deliberate counter-example and they have to be findable
here for the same reason everyone else does.

Output: data/processed/<nation>/pool_table.json
    {"season": str, "rows": [...], "groups": {"FW": n, ...}}
"""

from __future__ import annotations

import json
import logging

import pandas as pd

from src import config
from src.utils import read_parquet

LOG = logging.getLogger(__name__)

GROUPS = ("FW", "MF", "DF")

ROLE_TOTALS = ("crs", "interceptions", "tklw", "fld", "fls")
"""Miscellaneous-table counts turned into per-90 rates for the role line."""


def _tier(league: str, headline: list[str], stepping: list[str], domestic: str) -> str:
    """The league's place in the pathway, in `src.pathways`' own vocabulary
    and precedence: headline before stepping stone, because four of the five
    stepping-stone leagues are themselves headline leagues."""
    if league == domestic:
        return "domestic"
    if league in headline:
        return "top9"
    if league in stepping:
        return "stepping_stone"
    return "other"


def _weighted(frame: pd.DataFrame, col: str) -> float | None:
    """Minutes-weighted mean of `col` over a player's stints."""
    m = frame["min"].sum()
    if not m or col not in frame:
        return None
    v = (frame[col].fillna(0) * frame["min"]).sum() / m
    return float(v)


PROFILE = (
    # (key, label, higher-is-more-of-what)
    ("min_share", "playing time", "share of his club's minutes"),
    ("starts_share", "selection", "starts among his appearances"),
    ("q", "output", "league-adjusted G+A per 90"),
    ("crs_p90", "crossing", "crosses per 90"),
    ("def_p90", "defending", "tackles won and interceptions per 90"),
    ("fld_p90", "drawing fouls", "fouls won per 90"),
)
"""The six axes of a player's percentile profile. Each is ranked against every
player-season of his position group in the metrics season across every
covered league -- the benchmark SkillCorner-style player pages use, so a
coach reads 'selection: 82nd percentile of midfielders' rather than '20 starts'."""


def _profile_frame(feats: pd.DataFrame, roles: pd.DataFrame | None, season: str) -> pd.DataFrame:
    """Per player-season row of `season` (all nationalities): the six profile
    measures, each summed over a player's stints so a mid-season mover is
    one row -- the same collapsing `build_rows` does for the pool."""
    f = feats[feats.season == season].copy()
    if roles is not None and not roles.empty:
        cols = ["league", "season", "team", "player_key", "starts", "subs", "crs", "interceptions", "tklw", "fld"]
        have = [c for c in cols if c in roles.columns]
        f = f.merge(roles[have], on=["league", "season", "team", "player_key"], how="left")
    for c in ("starts", "subs", "crs", "interceptions", "tklw", "fld"):
        if c not in f:
            f[c] = pd.NA
    f["q"] = f["npg_p90_quality"].fillna(0) + f["ast_p90_quality"].fillna(0)
    g = f.groupby(["player_key", "pos_group"], sort=False)
    out = pd.DataFrame({
        "min": g["min"].sum(),
        "min_share": g["min_share"].max(),
        "q": g.apply(lambda d: (d["q"] * d["min"]).sum() / d["min"].sum() if d["min"].sum() else 0.0),
        "starts": g["starts"].sum(min_count=1), "subs": g["subs"].sum(min_count=1),
        "crs": g["crs"].sum(min_count=1), "interceptions": g["interceptions"].sum(min_count=1),
        "tklw": g["tklw"].sum(min_count=1), "fld": g["fld"].sum(min_count=1),
    }).reset_index()
    apps = out["starts"] + out["subs"]
    out["starts_share"] = (out["starts"] / apps).where(apps > 0)
    for c in ("crs", "fld"):
        out[f"{c}_p90"] = (out[c] / out["min"] * 90).where(out["min"] > 0)
    out["def_p90"] = ((out["interceptions"].fillna(0) + out["tklw"].fillna(0)) / out["min"] * 90).where(out["min"] > 0)
    return out


def percentiles(profile: pd.DataFrame, min_minutes: int = 450) -> dict[tuple[str, str], dict[str, int]]:
    """{(player_key, pos_group): {axis: percentile 0-100}}, each axis ranked
    within the position group among player-seasons with at least
    `min_minutes` -- the report's own inclusion floor, so a ten-minute cameo
    cannot sit at the 99th percentile of crossing."""
    bench = profile[profile["min"] >= min_minutes]
    out: dict[tuple[str, str], dict[str, int]] = {}
    for grp, b in bench.groupby("pos_group"):
        for key, _, _ in PROFILE:
            if key not in b or b[key].notna().sum() < 10:
                continue
            pct = (b[key].rank(pct=True, method="average") * 100).round()
            for k, v in zip(b["player_key"], pct, strict=True):
                if pd.notna(v):
                    out.setdefault((k, grp), {})[key] = int(v)
    return out


def build_rows(
    feats: pd.DataFrame,
    roles: pd.DataFrame | None,
    season: str,
    headline: list[str],
    stepping: list[str],
    domestic: str,
) -> list[dict]:
    """One row per home-eligible player with a `season` row in `feats`.

    `feats` is the concatenation of the three `features_<group>.parquet`
    tables (each already collapsed per player-season-group by
    `src.utils.collapse_player_seasons`, so a mid-season move shows as one
    row per club). Ranks are computed inside a position group on
    quality-adjusted npG+A per 90, descending, ties sharing the better rank.
    """
    f = feats[(feats.season == season) & feats.home_eligible].copy()
    if f.empty:
        return []
    if roles is not None and not roles.empty:
        cols = ["league", "season", "team", "player_key", "starts", "subs", "compl",
                "mn_per_start", *ROLE_TOTALS]
        have = [c for c in cols if c in roles.columns]
        f = f.merge(roles[have], on=["league", "season", "team", "player_key"], how="left")
    for c in ("starts", "subs", "compl", "mn_per_start", *ROLE_TOTALS):
        if c not in f:
            f[c] = pd.NA
    f["tier"] = f["league"].map(lambda lg: _tier(lg, headline, stepping, domestic))
    f["q"] = f["npg_p90_quality"].fillna(0) + f["ast_p90_quality"].fillna(0)
    pcts = percentiles(_profile_frame(feats, roles, season))

    rows = []
    for (key, group), g in f.groupby(["player_key", "pos_group"], sort=False):
        g = g.sort_values("min", ascending=False)
        lead = g.iloc[0]
        minutes = int(g["min"].sum())
        stints = [
            {"league": r.league, "team": r.team, "tier": r.tier, "min": int(r.min),
             "starts": None if pd.isna(r.starts) else int(r.starts),
             "subs": None if pd.isna(r.subs) else int(r.subs)}
            for r in g.itertuples()
        ]
        role = {c: (float(g[c].sum()) / minutes * 90 if minutes and g[c].notna().any() else None)
                for c in ROLE_TOTALS}
        rows.append({
            "player_key": key, "player": lead.player, "pos_group": group,
            "born": None if pd.isna(lead.born) else int(lead.born),
            "age": None if pd.isna(lead.age) else int(lead.age),
            "nt_flag": bool(lead.nt_flag),
            "club": lead.team, "league": lead.league, "tier": lead.tier,
            "min": minutes,
            "starts": None if g["starts"].isna().all() else int(g["starts"].sum()),
            "subs": None if g["subs"].isna().all() else int(g["subs"].sum()),
            "compl": None if g["compl"].isna().all() else int(g["compl"].sum()),
            "mn_per_start": _weighted(g, "mn_per_start"),
            "min_share": float(g["min_share"].max()),
            "npg_p90": _weighted(g, "npg_p90"),
            "ast_p90": _weighted(g, "ast_p90"),
            "q": _weighted(g, "q"),
            "moved": len(stints) > 1,
            "stints": stints,
            **{f"{c}_p90": v for c, v in role.items()},
            # the percentile profile: each axis against the whole position
            # group in the covered leagues this season (see PROFILE)
            "profile": [{"key": k, "label": lab, "what": what, "pct": pcts.get((key, group), {}).get(k)}
                        for k, lab, what in PROFILE],
        })

    out = pd.DataFrame(rows)
    out["rank_q"] = out.groupby("pos_group")["q"].rank(ascending=False, method="min").astype(int)
    out["n_group"] = out.groupby("pos_group")["q"].transform("size").astype(int)
    return out.sort_values(["pos_group", "rank_q"]).to_dict("records")


def build_keeper_rows(keepers: pd.DataFrame, pool: pd.DataFrame, season: str,
                      headline: list[str], stepping: list[str], domestic: str) -> list[dict]:
    """Home-eligible goalkeepers, with goals against and save percentage in
    place of production. `pool` supplies eligibility: the keeper tables carry
    every keeper in every fetched league, and only those on the nation's own
    FBref country page belong in its pool."""
    if keepers.empty or pool.empty:
        return []
    eligible = set(pool["player_key"])
    k = keepers[(keepers.season == season) & keepers.player_key.isin(eligible)].copy()
    if k.empty:
        return []
    rows = []
    for key, g in k.groupby("player_key", sort=False):
        g = g.sort_values("min", ascending=False)
        lead, minutes = g.iloc[0], int(g["min"].sum())
        rows.append({
            "player_key": key, "player": lead.player, "pos_group": "GK",
            "born": None if pd.isna(lead.born) else int(lead.born),
            "age": None if pd.isna(lead.age) else int(lead.age),
            "club": lead.team, "league": lead.league,
            "tier": _tier(lead.league, headline, stepping, domestic), "min": minutes,
            "ga_p90": float(g["ga"].sum()) / minutes * 90 if minutes else None,
            "save_pct": _weighted(g, "save_pct"),
            "cs": int(g["cs"].sum()),
            "moved": len(g) > 1,
        })
    out = pd.DataFrame(rows).sort_values("min", ascending=False)
    return out.to_dict("records")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    p, cfg = config.PROCESSED_DIR, config.leagues()
    season = config.seasons()["metrics"]
    feats = pd.concat([read_parquet(p / f"features_{g}.parquet") for g in GROUPS], ignore_index=True)
    roles_path = p / "fbref_roles.parquet"
    roles = read_parquet(roles_path) if roles_path.exists() else None
    keepers_path = p / "fbref_keepers.parquet"
    keepers = read_parquet(keepers_path) if keepers_path.exists() else pd.DataFrame()

    rows = build_rows(feats, roles, season, cfg["headline"], cfg["stepping_stone"],
                      config.DOMESTIC_LEAGUE)
    gk = build_keeper_rows(keepers, read_parquet(p / "pool.parquet"), season,
                           cfg["headline"], cfg["stepping_stone"], config.DOMESTIC_LEAGUE)
    payload = {
        "season": season,
        "rows": rows + gk,
        "groups": {g: sum(1 for r in rows if r["pos_group"] == g) for g in GROUPS} | {"GK": len(gk)},
    }
    (p / "pool_table.json").write_text(json.dumps(payload, indent=1, default=float))
    LOG.info("pool_table written: %s", payload["groups"])


if __name__ == "__main__":
    main()
