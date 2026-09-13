"""Pathways and differences: youth exposure at home, export route, how
exports fare, profile by tier.

Four independent exhibits, all restricted to the peer countries
(`config.PEER_COUNTRIES`, CZE included):

    youth_exposure: for each headline-league country's own domestic league
        (in practice this module is called with the CZE-First-League +
        peer-domestic mapping), the share of that league's total minutes
        played by the league's own young nationals (u21 / u23). Answers
        "how much room does a country's own domestic league give its own
        kids".

    export_route: for peer-country players currently rostered in a UEFA
        top-9 headline league, the age at which they first appeared in a
        headline league and the league they came from immediately before
        (their own domestic league / one of five stepping-stone leagues /
        another top-9 league / not covered by our data). Answers "how old
        when they left, and by which door".

    fare: for the same current-headline-league peer players, minutes share
        at their new club and a club-strength proxy. ClubElo is down (see
        Task 5's `src.international_benchmark` / `src.fetch_elo` fallback
        path), so club strength here is NOT an Elo percentile. It is a
        goals-scored proxy computed entirely from this repo's own data:
        rank every club within its own league-season by the total `gls`
        scored by its own roster that season, then take that club's
        percentile within the league (1.0 = the league's highest-scoring
        club that season). Reported as `club_goals_pct`. Answers "are they
        playing regular minutes, and for a club near the top of its table".

    profile: for the metrics season, quality-adjusted production
        (npg_p90_quality + ast_p90_quality) by peer country x pathway tier
        x position group. Tiers are the player's OWN season's league,
        classified as `top9` (a headline league), `stepping_stone` (one of
        the five stepping-stone leagues), `domestic` (the player's own
        country's domestic league), or `other` (any other league — e.g. a
        Czech player in the Austrian league, which is AUT's domestic league
        but not CZE's). Answers "does production differ by tier, for a
        given country".

This module makes no player-selection recommendation; it reports counts,
shares, ages and medians.

Age convention (this module only): age at the season's Jul 1 =
int(season[:4]) - born. E.g. season "2024-2025", born 2004 -> age 20. This
is NOT the +1-cohort convention used in `src.international_benchmark`
(int(season[:4]) + 1 - born); the two chapters were specified independently
and each documents its own choice.

Inputs:
    data/processed/fbref_players.parquet (all seasons; headline leagues
        2020-2021 onward, domestic/peer/2.Bundesliga 2023-2024 onward)
    data/processed/features_{FW,MF,DF}.parquet (metrics-season quality
        features, for `profile`)
    config/leagues.yaml, config/countries.yaml, config/seasons.yaml

Output:
    data/processed/pathways.json with keys `youth_exposure`, `export_route`,
    `fare`, `profile`.
"""

from __future__ import annotations

import json
import logging

import pandas as pd

from src import config
from src.utils import read_parquet

LOG = logging.getLogger(__name__)

__all__ = ["youth_exposure", "export_route", "fare", "profile", "main"]

ORIGIN_LABELS = ("domestic", "stepping_stone", "other_top9", "not_covered")


def _age(born, season: str) -> float:
    """Age at the season's Jul 1: season-start year minus birth year.

    This module's own convention (see module docstring) — not the
    +1-cohort convention used by `src.international_benchmark.assign_cohort`.
    Returns NaN when `born` is missing (a handful of fbref_players.parquet
    rows have no birth year) rather than raising, so a missing birth year
    silently drops that row from age-gated comparisons (`age <= 21` is
    False for NaN) without excluding it from minutes totals.
    """
    if born is None or pd.isna(born):
        return float("nan")
    return int(season[:4]) - int(born)


def _dedupe_player_season(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse (player_key, season) duplicates from mid-season transfers.

    `fbref_players.parquet` has one row per player-team-season; a player
    transferred mid-season (~6% of player-seasons in this data, some within
    the same league, some across leagues) gets two or more rows for the
    same season. `src.utils.collapse_player_seasons` expects the
    features-frame shape (a `pos_group` column, already-computed per-90
    rate columns) that the raw roster table doesn't carry, so this is a
    small local version fit to `fbref_players`' own columns: keep the row
    with the most minutes (that club/league is where most of the season
    was spent, so it decides league/team/nation/born/etc for the season)
    and sum `min` across the group. Groups of size 1 pass through
    unchanged, so it is safe to call on any (player_key, season) subset.
    """
    key_cols = ["player_key", "season"]
    sizes = df.groupby(key_cols)["min"].transform("size")
    singles, dup_rows = df[sizes == 1], df[sizes > 1]
    if dup_rows.empty:
        return df
    collapsed = []
    for _, g in dup_rows.groupby(key_cols):
        lead = g.loc[g["min"].idxmax()].to_dict()
        lead["min"] = int(g["min"].sum())
        collapsed.append(lead)
    out = pd.concat([singles, pd.DataFrame(collapsed)], ignore_index=True)
    return out[df.columns.tolist()]


def youth_exposure(tables: pd.DataFrame, season: str, league_country: dict[str, str]) -> pd.DataFrame:
    """Share of a domestic league's minutes played by its own young nationals.

    For each `league: country` pair, restrict to that league+season's rows
    (row-per-player-team, not deduped — a mid-season transfer's minutes at
    each club still belong to that league-season's total either way) and
    report the share of total minutes played by nationals of `country` aged
    <=21 / <=23.
    """
    rows = []
    for league, country in league_country.items():
        t = tables[(tables.league == league) & (tables.season == season)]
        if t.empty:
            continue
        age = t["born"].map(lambda b: _age(b, season))
        own = t.nation == country
        total = float(t["min"].sum())
        rows.append({
            "league": league,
            "country": country,
            "minutes_total": total,
            "share_u21": float(t.loc[own & (age <= 21), "min"].sum()) / total,
            "share_u23": float(t.loc[own & (age <= 23), "min"].sum()) / total,
        })
    return pd.DataFrame(rows)


def export_route(
    tables: pd.DataFrame,
    headline: list[str],
    stepping: list[str],
    peer_domestic: dict[str, str],
    peers: list[str],
    current: str | None = None,
) -> pd.DataFrame:
    """Age and origin of peer-country players currently in a headline league.

    `current` defaults to `tables.season.max()`; `main()` passes
    `config.seasons()["current"]` explicitly.

    For each peer country's headline-league roster in `current`, walks each
    player's full history (deduped to one row per season) to find their
    FIRST headline-league season, then classifies the league they were in
    immediately before that as `domestic` (own country's domestic league),
    `stepping_stone`, `other_top9` (a different headline league), or
    `not_covered` (no earlier row in our data at all).

    `censored_share`: our roster data for the headline leagues starts at
    the table's own earliest season (2020-2021 in the live run). A player
    whose first headline appearance IS that earliest season has an unknown
    true origin — we cannot see what came before our data starts — and is
    counted as censored, separate from the `origin_shares` breakdown (whose
    `not_covered` bucket instead means "no earlier row for this player at
    all, though the table itself is not at its floor").
    """
    t = _dedupe_player_season(tables)
    current = current if current is not None else t.season.max()
    first_hist = t.season.min()
    rows = []
    for country in peers:
        on_roster = t[(t.season == current) & t.league.isin(headline) & (t.nation == country)]
        ages, origins, censored = [], [], 0
        for pid in on_roster.player_key.unique():
            hist = t[t.player_key == pid].sort_values("season")
            top = hist[hist.league.isin(headline)]
            first = top.iloc[0]
            if first.season == first_hist:
                censored += 1
            ages.append(_age(first.born, first.season))
            before = hist[hist.season < first.season]
            if before.empty:
                origins.append("not_covered")
            else:
                lg = before.iloc[-1].league
                origins.append(
                    "domestic" if peer_domestic.get(lg) == country else
                    "stepping_stone" if lg in stepping else
                    "other_top9" if lg in headline else
                    "not_covered"
                )
        n = len(ages)
        shares = {k: (origins.count(k) / n if n else 0.0) for k in ORIGIN_LABELS}
        rows.append({
            "country": country,
            "n": n,
            "median_export_age": float(pd.Series(ages).median()) if n else None,
            "origin_shares": shares,
            "censored_share": censored / n if n else 0.0,
        })
    return pd.DataFrame(rows)


def fare(tables: pd.DataFrame, headline: list[str], peers: list[str], season: str) -> pd.DataFrame:
    """How peer-country exports fare at their headline-league clubs.

    Two measures, both for peer-nation players in headline leagues in
    `season`:
        median_min_share: minutes / (club matches played * 90), median over
            the country's players (deduped to one row per player-season).
        median_club_goals_pct: club-strength proxy. ClubElo is down (Task
            5), so this uses the league-table proxy available in this
            repo's own data instead of an Elo percentile: rank each club
            within its own league-season by the total `gls` scored by its
            full roster that season (all rows for that club-season, not
            deduped — a mid-season arrival's goals for that club still
            count toward the club's total), then take the percentile of
            that rank within the league (1.0 = the league's top-scoring
            club that season). Median taken over the country's players.
    """
    all_season = tables[tables.season == season]
    team_matches = all_season.groupby(["league", "team"])["mp"].max().rename("team_matches")
    club_goals = all_season.groupby(["league", "team"])["gls"].sum().rename("club_goals")
    club_goals_pct = club_goals.groupby(level="league").rank(pct=True).rename("club_goals_pct")

    peer_rows = _dedupe_player_season(
        all_season[all_season.league.isin(headline) & all_season.nation.isin(peers)]
    )
    t = peer_rows.join(team_matches, on=["league", "team"]).join(club_goals_pct, on=["league", "team"])
    t["min_share"] = t["min"] / (t["team_matches"] * 90)

    out = (
        t.groupby("nation")
        .agg(n=("player_key", "nunique"),
             median_min_share=("min_share", "median"),
             median_club_goals_pct=("club_goals_pct", "median"))
        .reset_index()
        .rename(columns={"nation": "country"})
    )
    LOG.info("fare: %d peer headline-league player-seasons, %d with a club_goals_pct match",
              len(t), int(t["club_goals_pct"].notna().sum()))
    return out


def profile(
    feats: pd.DataFrame,
    peer_domestic: dict[str, str],
    headline: list[str],
    stepping: list[str],
    peers: list[str],
    season: str,
) -> pd.DataFrame:
    """Quality-adjusted production by peer country x pathway tier x position.

    Tier is the player's OWN season's league, classified as `top9` (a
    headline league), `stepping_stone`, `domestic` (the player's own
    country's domestic league, per `peer_domestic` — includes the
    CZE-First-League mapping), or `other` (any other league — e.g. a Czech
    player in the Austrian league is `other`, since AUT-Bundesliga is AUT's
    domestic league, not CZE's).
    """
    f = feats[(feats.season == season) & feats.nation.isin(peers)].copy()

    def _tier(row) -> str:
        if row.league in headline:
            return "top9"
        if row.league in stepping:
            return "stepping_stone"
        if peer_domestic.get(row.league) == row.nation:
            return "domestic"
        return "other"

    f["tier"] = f.apply(_tier, axis=1)
    f["q"] = f["npg_p90_quality"] + f["ast_p90_quality"]
    out = (
        f.groupby(["nation", "tier", "pos_group"])
        .agg(n=("player_key", "nunique"), median_npg_ast_q=("q", "median"))
        .reset_index()
        .rename(columns={"nation": "country"})
    )
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    cfg, seasons, peers = config.leagues(), config.seasons(), config.PEER_COUNTRIES
    tables = read_parquet(config.PROCESSED_DIR / "fbref_players.parquet")
    peer_domestic = {k: v["country"] for k, v in cfg["peer_domestic"].items()} | {cfg["domestic"]: "CZE"}

    out = {
        "youth_exposure": youth_exposure(tables, seasons["metrics"], peer_domestic).to_dict("records"),
        "export_route": export_route(
            tables, cfg["headline"], cfg["stepping_stone"], peer_domestic, peers, seasons["current"]
        ).to_dict("records"),
        "fare": {
            "club_strength_proxy": "goals-scored percentile within league",
            "rows": fare(tables, cfg["headline"], peers, seasons["metrics"]).to_dict("records"),
        },
    }

    feats = pd.concat(
        [read_parquet(config.PROCESSED_DIR / f"features_{g}.parquet") for g in config.features()["groups"]]
    )
    out["profile"] = profile(
        feats, peer_domestic, cfg["headline"], cfg["stepping_stone"], peers, seasons["metrics"]
    ).to_dict("records")

    (config.PROCESSED_DIR / "pathways.json").write_text(json.dumps(out, indent=1, default=float))
    LOG.info("pathways written")


if __name__ == "__main__":
    main()
