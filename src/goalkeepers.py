"""Goalkeepers: the counter-example (spec ch.IV / Task 18).

The one position where Czech players (and, in general, this home nation's
players) leave young and sit at big clubs is the one where the pool holds
up. Five descriptive exhibits, all restricted to the peer countries
(`config.PEER_COUNTRIES`, home nation included) unless noted:

    per_million: distinct goalkeepers with >= min_minutes in the headline
        (top-9) leagues per peer country, metrics season -- same rule as
        `src.international_benchmark.per_capita`, with an added minutes
        floor (that module has none; a GK's presence on a top-9 roster at
        all isn't the question here, playing time is). Computed off the
        `fbref_keepers.parquet` rows joined to their `fbref_players.parquet`
        GK counterpart (`join_keeper_pool`; see "production" below).

    export age: for the home nation, the age at which each current
        (metrics-season) top-9 goalkeeper (>= min_minutes) first appeared in
        a top-9 table -- against the same figure for outfield exports
        (`fbref_players.parquet` with `pos != "GK"`). Both walked off
        `fbref_players.parquet` (GK rows restricted to `pos == "GK"` for the
        goalkeeper side), NOT `fbref_keepers.parquet` -- the keeper pages are
        only fetched for previous/metrics/current, so a keeper history walked
        off them could never show a first top-9 season earlier than that
        three-season window, while `fbref_players.parquet`'s headline-league
        rows reach back to 2020/21 (`config.seasons()["history"][0]`), same
        as the outfield side. A player whose first top-9 season IS that
        earliest fetched season has an unknown true origin (nothing before
        it is visible to us) and is counted `censored`, exactly as
        `src.pathways.export_route` counts its own `censored_share` -- both
        exhibits share one `first_hist` reference (the whole players table's
        own earliest season) so a goalkeeper and an outfield export whose
        first top-9 season is that same season are censored on the same
        basis. Same age convention and dedupe as `src.pathways.export_route`
        (`_age`, `_dedupe_player_season`, imported from there rather than
        reimplemented) but this module needs the raw per-player ages for the
        strip-plot figure, not just `export_route`'s aggregate median, so it
        walks the same history logic itself instead of reading
        `pathways.json`.

    club tier: for the home nation's current top-9 goalkeepers (the same
        roster `production`/`per_million` use -- see `home_top9_gks`), club,
        league, minutes and the club's goals-scored percentile within its
        league -- the same proxy `src.pathways.fare`/`destinations` use in
        place of the (unavailable) ClubElo rating.

    production: per goalkeeper (>= min_minutes, metrics season), GA/90 and
        saves/90 shrunk toward their (league, season) cohort median with
        the feature pipeline's own K (`config.features()["phantom_minutes"]`,
        same formula as `src.features.bayesian_shrink`), GA/90 additionally
        quality-adjusted by the league multiplier (`ga90_q = ga90_shrunk /
        m_L` -- `m_ENG = 1` is the baseline strength; a weaker league's GA
        scales up, so a goal conceded in a stronger league counts less than
        the same shrunk rate would in a weaker one). Save
        percentage is shrunk the same way but with shots-on-target-against
        (`sota`) as the exposure instead of minutes: a keeper-season's SoTA
        count is almost always far below K, so `save_pct_shrunk` pulls hard
        toward the league median for nearly everyone -- an intentional
        consequence of a thin single-season sample, not a bug (see
        `_shrink_series`'s docstring and the ch4.gk.p paragraph in the
        report). The shrinkage cohort is every qualifying keeper in that
        league-season, any nationality (mirrors `features.bayesian_shrink`'s
        own population, not just the home nation's handful of players), so
        the home nation's table and the peer medians come out of one shrink,
        not several small separately-shrunk samples.

    cards: two of the home nation's current top-9 goalkeepers -- (a) most
        top-9 minutes, (b) youngest with >= min_minutes top-9 minutes.

This module makes no player-selection recommendation; it reports counts,
shares, ages, medians and percentiles, same as `src.pathways`.

Inputs:
    data/processed/<nation>/fbref_keepers.parquet (src.fetch_keepers; any
        nationality, headline + domestic + custom + peer_domestic leagues,
        previous/metrics/current seasons) -- joined to the GK rows of
        `fbref_players.parquet` on (league, season, team, player_key) by
        `join_keeper_pool` before anything else in this module touches it;
        the players table's `born`/`nation`/`min` are canonical (that table
        is the corpus every other chapter already trusts), the keeper page's
        own copies of those same fields are dropped. Rows that fail to join
        are excluded from every GK exhibit; the count is logged
        (`LOG.warning`) and returned to `main()` for `data_quality.json`.
    data/processed/<nation>/fbref_players.parquet (GK rows for the export-
        age walk and the join above; non-GK rows for the outfield export-
        age contrast; `gls` totals for the club-strength proxy)
    data/processed/<nation>/nt_flags.parquet (national-team flag for cards)
    config/leagues.yaml, config/countries.yaml, config/seasons.yaml,
        config/league_quality.yaml, config/feature_definitions.yaml

Output:
    data/processed/<nation>/goalkeepers.json
    outputs/<nation>/gk_export_age.svg
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src import config
from src.figstyle import CREAM, INK, MUTED, NAVY, OXBLOOD, RULE, use_style
from src.pathways import _age, _dedupe_player_season
from src.utils import normalize_name, read_parquet

LOG = logging.getLogger(__name__)

__all__ = [
    "join_keeper_pool", "per_million", "gk_first_top9_ages", "club_tier", "production_table",
    "production_peer_medians", "home_top9_gks", "attach_nt_flags", "gk_cards",
    "build_goalkeepers", "render_export_age_figure", "main",
]

CLUB_STRENGTH_PROXY = "goals-scored percentile within league"

# Palette now lives in src.figstyle (Task 27A, the single source of figure
# style) -- imported above instead of redefined here.
use_style()


def _opt_float(value: object, digits: int = 2) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def join_keeper_pool(keepers: pd.DataFrame, players_all: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Join `fbref_keepers.parquet` to the GK rows of `fbref_players.parquet`
    on (league, season, team, player_key); the players table's `born`,
    `nation` and `min` are canonical -- that table is the corpus every other
    chapter of the report already trusts, so the keeper page's own copies of
    those same three fields are dropped in favour of it. Every other column
    (the production stats: `ga`, `saves`, `sota`, `save_pct`, `cs`, `mp`;
    `player`, `age`) is kept from the keeper table -- the players table
    doesn't carry any of the production numbers, and `player`/`age` should
    already agree between the two FBref pages for the same person-season.

    Returns `(joined, unjoined)`: `joined` has exactly `fbref_keepers.
    parquet`'s own column set (`COLS` in `src.fetch_keepers`), just with
    `born`/`nation`/`min` swapped for their canonical values; `unjoined` is
    the count of keeper rows with no matching GK row in the players table
    (a team-name mismatch between the two pages, or that keeper not carrying
    `pos == "GK"` in the standard table for that season) -- those rows are
    dropped rather than kept with unverified identity fields, and the count
    is the caller's to log (`main()` both warns and returns it for
    `data_quality.json`'s `gk_unjoined` check).
    """
    key_cols = ["league", "season", "team", "player_key"]
    gk_pool = players_all[players_all.get("pos", pd.Series(dtype=str)) == "GK"]
    canonical = gk_pool[key_cols + ["born", "nation", "min"]].drop_duplicates(key_cols)
    own_cols = [c for c in keepers.columns if c not in ("born", "nation", "min")]
    joined = keepers[own_cols].merge(canonical, on=key_cols, how="inner")
    unjoined = len(keepers) - len(joined)
    return joined[keepers.columns.tolist()], unjoined


def per_million(
    keepers: pd.DataFrame, peers: dict, headline_leagues: list[str], season: str, min_minutes: int,
) -> pd.DataFrame:
    """Distinct goalkeepers (>= min_minutes) per peer country, headline
    leagues, `season`, per million population. Same shape and tie-break
    (ascending population on an equal rate) as
    `src.international_benchmark.per_capita`.
    """
    sub = keepers[
        (keepers.season == season) & keepers.league.isin(headline_leagues)
        & keepers.nation.isin(peers) & (keepers["min"] >= min_minutes)
    ]
    n = sub.groupby("nation")["player_key"].nunique()
    rows = []
    for code, meta in peers.items():
        cnt = int(n.get(code, 0))
        rows.append({
            "country": code, "name": meta["name"], "n_gk": cnt,
            "population_m": meta["population_m"], "per_million": round(cnt / meta["population_m"], 2),
        })
    out = (
        pd.DataFrame(rows)
        .sort_values(["per_million", "population_m"], ascending=[False, True])
        .reset_index(drop=True)
    )
    out["rank"] = range(1, len(out) + 1)
    return out


def _export_ages(
    tables: pd.DataFrame, headline: list[str], home: str, season: str, first_hist: str,
) -> tuple[list[float], int]:
    """Age at first top-9 season, for every home-nation player on the
    `season` top-9 roster in `tables` -- the raw per-player list (not just
    the median `src.pathways.export_route` reports), needed for the
    strip-plot figure, plus how many of them are `censored` (their first
    top-9 season IS `first_hist`, so their true first season could be
    earlier and is unknown -- same rule as `export_route`'s own
    `censored_share`, sharing that function's `first_hist` reference so a
    goalkeeper and an outfield export censored on the same season count the
    same way). Same age convention (`pathways._age`: season-start year minus
    birth year) and mid-season-transfer dedupe (`pathways._dedupe_player_
    season`) as `export_route`, reused directly rather than reimplemented.
    A player with no birth year (`_age` returns NaN) is excluded from the
    returned ages, same as `export_route`'s own median calculation, and from
    `censored` too -- `censored`'s denominator (the caller divides by
    `len(ages)`) is exactly the population the median is computed over.
    """
    t = _dedupe_player_season(tables)
    roster = t[(t.season == season) & t.league.isin(headline) & (t.nation == home)]
    ages, censored = [], 0
    for pid in roster.player_key.unique():
        hist = t[t.player_key == pid].sort_values("season")
        top = hist[hist.league.isin(headline)]
        first = top.iloc[0]
        age = _age(first.born, first.season)
        if pd.isna(age):
            continue
        ages.append(float(age))
        if first.season == first_hist:
            censored += 1
    return ages, censored


def gk_first_top9_ages(
    home_top9: pd.DataFrame, gk_history: pd.DataFrame, headline: list[str], first_hist: str,
) -> list[dict]:
    """Per current-top9-roster home goalkeeper (`home_top9`, from
    `home_top9_gks` -- the same >= min_minutes roster `production`/
    `per_million`/`club_tier` use, so this exhibit's `n` always matches
    theirs): age and season of their own first top-9 appearance, walked over
    `gk_history` (`fbref_players.parquet`'s `pos == "GK"` rows, NOT
    `fbref_keepers.parquet` -- see the module docstring's "export age"
    section on why: the keeper pages don't reach back far enough). A player
    whose first top-9 season IS `first_hist` is `censored` (their true first
    season could be earlier and is unknown -- see `_export_ages`, which this
    mirrors so goalkeepers and outfield exports are censored identically).
    Named counterpart of `_export_ages` (same history-walk logic, duplicated
    rather than shared because this one needs the player names and per-row
    censoring flag the report's roster listing wants, not just the ages).
    """
    hist = _dedupe_player_season(gk_history)
    rows = []
    for pid in home_top9.player_key.unique():
        h = hist[hist.player_key == pid].sort_values("season")
        top = h[h.league.isin(headline)]
        first = top.iloc[0]
        age = _age(first.born, first.season)
        name = home_top9[home_top9.player_key == pid].iloc[0]["player"]
        rows.append({
            "player_key": pid, "player": str(name),
            "first_age": (None if pd.isna(age) else float(age)),
            "first_season": str(first.season),
            "censored": bool(first.season == first_hist),
        })
    return sorted(rows, key=lambda r: (r["first_age"] is None, r["first_age"]))


def club_tier(home_top9: pd.DataFrame, players_all: pd.DataFrame, season: str) -> pd.DataFrame:
    """Home nation's current top-9 goalkeepers (`home_top9`, from
    `home_top9_gks` -- the same >= min_minutes roster `production`/
    `per_million`/the export-age exhibit use, so this table's row count
    always matches theirs): club, league, minutes and the club's
    goals-scored percentile within its league that season -- the exact
    proxy `src.pathways.fare`/`destinations` use (ClubElo is down; rank
    each club within its own league-season by the total `gls` scored by its
    full roster, then take the percentile of that rank).
    """
    all_season = players_all[players_all.season == season]
    club_goals = all_season.groupby(["league", "team"])["gls"].sum().rename("club_goals")
    club_goals_pct = club_goals.groupby(level="league").rank(pct=True).rename("club_goals_pct")

    gk = home_top9.join(club_goals_pct, on=["league", "team"])
    return (
        gk[["player", "player_key", "league", "team", "min", "club_goals_pct"]]
        .sort_values("min", ascending=False)
        .reset_index(drop=True)
    )


def _shrink_series(
    df: pd.DataFrame, count_col: str, rate_col: str, exposure_col: str, k: int, per90: bool,
    group_cols: tuple[str, ...] = ("league", "season"),
) -> pd.Series:
    """Bayesian-shrink `rate_col` (= `count_col` / an exposure) toward its
    cohort median, same phantom-quantity formula as
    `src.features.bayesian_shrink`, generalized to an arbitrary exposure
    column so it can shrink a per-90 rate (`per90=True`, exposure divided by
    90, e.g. GA/90 with exposure `min`) or a rate whose natural exposure is
    a raw count rather than playing time (`per90=False`, e.g. save
    percentage with exposure `sota` -- shots on target against). The cohort
    ("well-observed enough to trust as a prior seed") threshold and the
    fallback ("median of the whole cohort when nobody clears it") both use
    the RAW exposure compared against the raw `k`, exactly as
    `bayesian_shrink` compares raw minutes against `k_minutes`; only the
    shrinkage denominator itself converts to /90 units when `per90=True`.

    A single keeper-season's `sota` (shots on target against) is typically
    a few hundred at most, far below a K of 900 -- so with `per90=False`
    the "well-observed" cohort is usually empty (falls back to the whole
    league-season's median) and the shrinkage denominator (`sota + k`) is
    dominated by `k`: `save_pct_shrunk` compresses hard toward the league
    median for nearly every goalkeeper. That is the correct behaviour of
    this formula given a thin single-season sample relative to K, not a
    defect -- see the module docstring and `ch4.gk.p` in the report.
    """
    raw_exposure = df[exposure_col].astype(float)
    eff_exposure = raw_exposure / 90.0 if per90 else raw_exposure
    k_eff = k / 90.0 if per90 else float(k)
    out = pd.Series(index=df.index, dtype=float)
    cols = [c for c in group_cols if c in df.columns]
    for _, sub in df.groupby(cols):
        well = sub[raw_exposure.loc[sub.index] >= k]
        med = float(well[rate_col].median()) if len(well) else float(sub[rate_col].median())
        out.loc[sub.index] = (sub[count_col] + k_eff * med) / (eff_exposure.loc[sub.index] + k_eff)
    return out


def production_table(
    keepers: pd.DataFrame, season: str, league_quality: dict, min_minutes: int, k: int,
) -> pd.DataFrame:
    """Per-goalkeeper production for every keeper (any nationality) with
    >= min_minutes in `season`: GA/90, saves/90, save %, clean-sheet share,
    shrunk toward the (league, season) cohort median (see `_shrink_series`),
    GA/90 additionally quality-adjusted by the league multiplier
    (`ga90_q = ga90_shrunk / m_L`; `m_ENG = 1` is the baseline, a weaker
    league's GA scales up -- a goal conceded in a stronger league counts
    less). The shrinkage population is every
    qualifying keeper league-wide, not restricted to any one country --
    `main()` filters this down to the home nation's own rows and to each
    peer's rows for `production_peer_medians` afterwards.
    """
    sub = keepers[(keepers.season == season) & (keepers["min"] >= min_minutes)].copy()
    if sub.empty:
        return sub
    sub["ga90"] = sub["ga"] / (sub["min"] / 90.0)
    sub["saves90"] = sub["saves"] / (sub["min"] / 90.0)
    sub["save_rate"] = sub["saves"] / sub["sota"].replace(0, np.nan)
    sub["cs_share"] = sub["cs"] / sub["mp"].replace(0, np.nan)
    sub["ga90_shrunk"] = _shrink_series(sub, "ga", "ga90", "min", k, per90=True)
    sub["saves90_shrunk"] = _shrink_series(sub, "saves", "saves90", "min", k, per90=True)
    sub["save_rate_shrunk"] = _shrink_series(sub, "saves", "save_rate", "sota", k, per90=False)
    sub["save_pct_shrunk"] = sub["save_rate_shrunk"] * 100
    mult = league_quality["multipliers"]
    sub["league_multiplier"] = sub["league"].map(mult).astype(float)
    sub["ga90_q"] = sub["ga90_shrunk"] / sub["league_multiplier"]
    return sub


def production_peer_medians(prod_all: pd.DataFrame, peers: list[str]) -> pd.DataFrame:
    """Per peer country: n and the median of each shrunk/quality-adjusted
    production column, over `production_table`'s full (any-nationality)
    output restricted to that country -- one row per configured peer, even
    when it has zero qualifying goalkeepers that season."""
    rows = []
    for country in peers:
        g = prod_all[prod_all.get("nation", pd.Series(dtype=str)) == country] if not prod_all.empty else prod_all
        rows.append({
            "country": country, "n": int(len(g)),
            "median_ga90_q": _opt_float(g["ga90_q"].median()) if len(g) else None,
            "median_saves90": _opt_float(g["saves90_shrunk"].median()) if len(g) else None,
            "median_save_pct": _opt_float(g["save_pct_shrunk"].median(), 1) if len(g) else None,
            "median_cs_share": _opt_float(g["cs_share"].median(), 3) if len(g) else None,
        })
    return pd.DataFrame(rows)


def home_top9_gks(keepers: pd.DataFrame, home: str, headline: list[str], season: str, min_minutes: int) -> pd.DataFrame:
    """Home nation's goalkeepers with >= min_minutes in a headline league, `season`."""
    return keepers[
        (keepers.season == season) & keepers.league.isin(headline)
        & (keepers.nation == home) & (keepers["min"] >= min_minutes)
    ].copy()


def attach_nt_flags(df: pd.DataFrame, nt: pd.DataFrame) -> pd.DataFrame:
    """nt_flag / nt_events for a frame carrying `player`/`born` columns.

    Mirrors `src.features._attach_flags`'s namesake-safe match
    (`normalize_name(player)` against `nt.player_norm`, additionally
    requiring `born` to match when the matched nt_flags row carries one) --
    reimplemented locally rather than imported since that helper expects the
    features frame's fuller column set.
    """
    out = df.copy().reset_index(drop=True)
    out["player_norm"] = out["player"].map(normalize_name)
    candidates = (
        out[["player_norm", "born"]].reset_index()
        .merge(nt[["player_norm", "born", "event"]], on="player_norm", how="inner", suffixes=("", "_nt"))
    )
    born_ok = candidates["born_nt"].isna() | (candidates["born_nt"] == candidates["born"])
    matched = candidates[born_ok]
    events = matched.groupby("index")["event"].agg(lambda s: " · ".join(sorted(set(s))))
    out["nt_events"] = out.index.map(events).fillna("")
    out["nt_flag"] = out["nt_events"].ne("")
    return out.drop(columns=["player_norm"])


def gk_cards(home_top9: pd.DataFrame, prod_all: pd.DataFrame, tier: pd.DataFrame, nt: pd.DataFrame) -> list[dict]:
    """Two card picks by rule: (a) most top-9 minutes among home
    goalkeepers, (b) youngest home goalkeeper with >= min_minutes top-9
    minutes (`home_top9` is already floored to that minutes rule). Card
    body = the production-table row + the club-tier row + the NT flag.
    Falls through to one card if the two rules pick the same player (a
    single qualifying goalkeeper), same convention as
    `src.historical_analogs.showcase_ids`'s "already chosen" skip.
    """
    if home_top9.empty:
        return []
    prod_by_key = prod_all.set_index("player_key") if not prod_all.empty else prod_all
    tier_by_key = tier.set_index("player_key") if not tier.empty else tier
    flagged = attach_nt_flags(
        home_top9[["player_key", "player", "born"]].drop_duplicates("player_key"), nt
    ).set_index("player_key")

    def _row(key: str, reason: str) -> dict | None:
        if prod_by_key.empty or key not in prod_by_key.index:
            return None
        p = prod_by_key.loc[key]
        t = tier_by_key.loc[key] if (not tier_by_key.empty and key in tier_by_key.index) else None
        n = flagged.loc[key] if key in flagged.index else None
        return {
            "player_key": key, "player": str(p["player"]), "team": str(p["team"]), "league": str(p["league"]),
            "min": int(p["min"]), "reason": reason,
            "stats": {
                "ga90": round(float(p["ga90"]), 2), "saves90": round(float(p["saves90"]), 2),
                "save_pct": _opt_float(p["save_pct_shrunk"], 1), "cs_share": _opt_float(p["cs_share"], 3),
                "ga90_q": round(float(p["ga90_q"]), 2),
            },
            "club_goals_pct": _opt_float(t["club_goals_pct"]) if t is not None else None,
            "nt_flag": bool(n["nt_flag"]) if n is not None else False,
            "nt_events": [e for e in str(n["nt_events"]).split(" · ") if e] if n is not None else [],
        }

    most_key = home_top9.sort_values("min", ascending=False).iloc[0]["player_key"]
    youngest_key = home_top9.sort_values(["age", "min"], ascending=[True, False]).iloc[0]["player_key"]

    cards = []
    a = _row(most_key, "most top-9 minutes among home goalkeepers")
    if a:
        cards.append(a)
    if youngest_key != most_key:
        b = _row(youngest_key, "youngest home goalkeeper with minimum top-9 minutes")
        if b:
            cards.append(b)
    return cards


def build_goalkeepers(
    keepers_raw: pd.DataFrame, players_all: pd.DataFrame, peers_meta: dict, headline: list[str], home: str,
    metrics_season: str, league_quality: dict, nt: pd.DataFrame,
    min_minutes: int, k: int,
) -> tuple[dict, int]:
    """Assemble the full `goalkeepers.json` payload (no disk I/O).

    Every "current top-9 roster" exhibit (`per_million`'s home row,
    `club_tier`, `production`, the cards, the GK side of `export_age`) is
    built off one shared `home_top9` roster (`home_top9_gks` on the
    keeper/pool join) so their counts always agree -- the sentence's n_gk,
    the club-tier table's row count and the export-age median's n are the
    same number by construction, not by coincidence. `metrics_season` is
    used throughout (no separate "current" season parameter: Task 18's
    review round found `gk_first_top9_ages` called with a different season
    than everything else, which desynced that count from the others).

    Returns `(payload, keeper_unjoined)` -- `keeper_unjoined` is
    `join_keeper_pool`'s dropped-row count, for `main()` to log into
    `data_quality.json`.
    """
    keepers, keeper_unjoined = join_keeper_pool(keepers_raw, players_all)
    pm = per_million(keepers, peers_meta, headline, metrics_season, min_minutes)
    home_row = pm[pm.country == home]

    gk_history = players_all[players_all.get("pos", pd.Series(dtype=str)) == "GK"]
    outfield = players_all[players_all.get("pos", pd.Series(dtype=str)) != "GK"]
    # Shared censoring reference (see the module docstring's "export age"
    # section): the whole players table's own earliest season, so a
    # goalkeeper and an outfield export whose first top-9 season is that
    # same season are censored on the same basis.
    first_hist = str(players_all["season"].min())

    home_top9 = home_top9_gks(keepers, home, headline, metrics_season, min_minutes)
    gk_named = gk_first_top9_ages(home_top9, gk_history, headline, first_hist)
    gk_ages = [r["first_age"] for r in gk_named if r["first_age"] is not None]
    # Denominator matches `len(gk_ages)`: a row with no birth year contributes
    # to neither the median nor the censored count, same as `_export_ages`.
    gk_censored = sum(1 for r in gk_named if r["first_age"] is not None and r["censored"])
    outfield_ages, outfield_censored = _export_ages(outfield, headline, home, metrics_season, first_hist)

    tier = club_tier(home_top9, players_all, metrics_season)
    prod_all = production_table(keepers, metrics_season, league_quality, min_minutes, k)
    home_prod = (
        prod_all[prod_all.nation == home] if not prod_all.empty else prod_all
    )
    peer_med = production_peer_medians(prod_all, list(peers_meta))
    cards = gk_cards(home_top9, prod_all, tier, nt)

    home_prod_records = []
    for r in home_prod.itertuples() if not home_prod.empty else []:
        home_prod_records.append({
            "player": r.player, "player_key": r.player_key, "team": r.team, "league": r.league,
            "min": int(r.min), "ga90": round(float(r.ga90), 2), "saves90": round(float(r.saves90), 2),
            "save_pct_shrunk": round(float(r.save_pct_shrunk), 1),
            "cs_share": _opt_float(r.cs_share, 3), "ga90_q": round(float(r.ga90_q), 2),
        })
    payload = {
        "min_minutes": min_minutes, "phantom_minutes": k,
        "per_million": pm.to_dict("records"),
        "home_rank": int(home_row.iloc[0]["rank"]) if not home_row.empty else None,
        "n_peers": int(len(pm)),
        "export_age": {
            "gk_n": len(gk_ages), "gk_median_age": _opt_float(pd.Series(gk_ages).median(), 1) if gk_ages else None,
            "gk_censored": gk_censored,
            "gk_censored_share": round(gk_censored / len(gk_ages), 3) if gk_ages else 0.0,
            "outfield_n": len(outfield_ages),
            "outfield_median_age": _opt_float(pd.Series(outfield_ages).median(), 1) if outfield_ages else None,
            "outfield_censored": outfield_censored,
            "outfield_censored_share": (
                round(outfield_censored / len(outfield_ages), 3) if outfield_ages else 0.0
            ),
            "current_top9_ages": gk_named,
        },
        "club_tier": [
            {**row, "club_goals_pct": _opt_float(row["club_goals_pct"])} for row in tier.to_dict("records")
        ],
        "club_strength_proxy": CLUB_STRENGTH_PROXY,
        "production": {
            "home": home_prod_records,
            "peer_medians": peer_med.to_dict("records"),
        },
        "cards": cards,
    }
    return payload, keeper_unjoined


def render_export_age_figure(
    gk_ages: list[float], outfield_ages: list[float],
    gk_median: float | None, outfield_median: float | None, out_path: Path,
) -> None:
    """Strip plot: age at first top-9 season, goalkeepers vs. outfield
    exports, home nation, one dot per player, median marked per row."""
    fig, ax = plt.subplots(figsize=(8.2, 3.2))
    fig.patch.set_facecolor(CREAM)
    rng = np.random.default_rng(config.RANDOM_SEED)
    rows = ((1, gk_ages, OXBLOOD, gk_median), (0, outfield_ages, NAVY, outfield_median))
    for y, ages, color, median in rows:
        if ages:
            jitter = rng.uniform(-0.12, 0.12, size=len(ages))
            ax.scatter(ages, np.full(len(ages), y) + jitter, s=32, color=color, alpha=0.8,
                      edgecolors=CREAM, linewidths=0.5, zorder=3)
        if median is not None:
            ax.plot([median, median], [y - 0.24, y + 0.24], color=color, lw=2.2, zorder=5)

    ax.set_yticks([0, 1])
    ax.set_yticklabels(["Outfield exports", "Goalkeepers"], fontsize=10, fontfamily="sans-serif", color=INK)
    ax.set_ylim(-0.6, 1.6)
    ax.set_xlabel("Age at first top-9 season", fontsize=9.5, color=MUTED, fontfamily="sans-serif")
    ax.set_title("Age at first top-9 season: goalkeepers vs. outfield exports",
                 fontsize=12, fontfamily="sans-serif", color=INK, pad=12, loc="left")
    ax.tick_params(colors=MUTED, labelsize=9)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(RULE)
    ax.set_facecolor(CREAM)
    plt.tight_layout()
    plt.savefig(out_path, bbox_inches="tight", format="svg", facecolor=CREAM, edgecolor="none")
    plt.close(fig)
    LOG.info("wrote %s", out_path)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    config.ensure_dirs()
    cfg, seasons_raw, league_quality = config.leagues(), config.seasons(), config.league_quality()
    fd = config.features()
    min_minutes, k = fd["min_minutes"], fd["phantom_minutes"]
    headline = list(cfg["headline"])
    home = config.HOME
    metrics_season = seasons_raw["metrics"]

    keepers = read_parquet(config.PROCESSED_DIR / "fbref_keepers.parquet")
    players_all = read_parquet(config.PROCESSED_DIR / "fbref_players.parquet")
    nt = read_parquet(config.PROCESSED_DIR / "nt_flags.parquet")
    peers_meta = config.peers_meta()

    out, unjoined = build_goalkeepers(
        keepers, players_all, peers_meta, headline, home, metrics_season,
        league_quality, nt, min_minutes, k,
    )
    if unjoined:
        LOG.warning("%d of %d keeper rows did not join to a GK row in fbref_players.parquet", unjoined, len(keepers))
    (config.PROCESSED_DIR / "goalkeepers.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
    LOG.info("wrote goalkeepers.json: rank %s of %s, %d GK cards",
             out["home_rank"], out["n_peers"], len(out["cards"]))

    gk_ages = [r["first_age"] for r in out["export_age"]["current_top9_ages"] if r["first_age"] is not None]
    outfield = players_all[players_all.get("pos", pd.Series(dtype=str)) != "GK"]
    first_hist = str(players_all["season"].min())
    outfield_ages, _ = _export_ages(outfield, headline, home, metrics_season, first_hist)
    render_export_age_figure(
        gk_ages, outfield_ages, out["export_age"]["gk_median_age"], out["export_age"]["outfield_median_age"],
        config.OUTPUTS_DIR / "gk_export_age.svg",
    )


if __name__ == "__main__":
    main()
