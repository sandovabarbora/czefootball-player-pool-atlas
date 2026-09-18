"""Three small computed facts for the "why the train left" funnel (Task 26B).

The funnel (`section.why-funnel`, built in `src.render`) needs two numbers
that no earlier module computes: how many clubs, not just how many minutes,
give young players real game time, and what the domestic league's own age
structure looks like. A third fact -- the age at a player's first season
abroad, at ANY destination, not just a headline league -- generalises
`src.pathways.export_route`'s "first top-9 season" to the funnel's plainer
question ("when did the first move abroad happen at all").

None of this changes a model; every number here is a count, a share or a
median over rows already fetched into `fbref_players.parquet` by earlier
tasks.

    club_breadth: for each country's own domestic league (in the metrics
        season), the number of clubs whose players aged 21 or under (any
        nationality -- this is about the LEAGUE's own habit of playing
        young players, not about the country's national-team pool) take
        more than a tenth of that club's total minutes, out of every club
        with any minutes in the league that season. Answers "is playing
        kids a leaguewide habit or a handful of clubs".

    age_structure: for each country's own domestic league (metrics season),
        the minutes-weighted mean age of a minute played, and the share of
        minutes played by players aged 22 or under and by players aged 30
        or over (any nationality, same reasoning as club_breadth). Answers
        "does the league run on old legs".

    first_move_abroad: for each country's players CURRENTLY (the table's
        latest season) rostered abroad with at least 450 minutes, in ANY
        league other than the country's own domestic one -- not restricted
        to a headline league, unlike `export_route`'s "first top-9 season"
        -- the age at the first such qualifying season over the player's
        full history. Mirrors `export_route`'s own "who is on the roster
        now, then walk their history" construction, just without the
        headline-league restriction on either end. Same censoring rule as
        `export_route`: a player whose first qualifying season is the
        table's own earliest season is censored (there may have been an
        earlier one we cannot see). Answers "how old is a player, on
        average, the first time he leaves for good minutes elsewhere".

Age convention: identical to `src.pathways._age` (age at the season's Jul 1
= season-start year minus birth year), reused directly rather than
recomputed.

Inputs:
    data/processed/<nation>/fbref_players.parquet
    config/leagues.yaml, config/countries.yaml, config/seasons.yaml

Output:
    data/processed/<nation>/pipeline_facts.json with keys `breadth`,
    `age_structure`, `first_move_abroad` (see `build_pipeline_facts`).
"""

from __future__ import annotations

import json
import logging

import pandas as pd

from src import config
from src.pathways import _age, _dedupe_player_season
from src.utils import read_parquet
from src.youth_panel import domestic_league_by_country

LOG = logging.getLogger(__name__)

__all__ = [
    "club_breadth",
    "age_structure",
    "first_move_abroad",
    "build_pipeline_facts",
    "main",
]

BREADTH_THRESHOLD = 0.10
"""A club counts toward `club_breadth`'s numerator when its own players
aged 21 or under take MORE than this share of the club's total minutes
(strict `>`, matching the brief's "more than a tenth")."""

MIN_MINUTES_FIRST_MOVE = 450
"""Same inclusion floor `src.pathways.destinations` uses for "a real
season", reused here so `first_move_abroad` isn't triggered by a single
substitute cameo abroad."""


def club_breadth(tables: pd.DataFrame, season: str, league_by_country: dict[str, str]) -> pd.DataFrame:
    """Per country's own domestic league: how many of its clubs give
    players aged 21 or under more than a tenth of the club's minutes.

    One row per `league_by_country` entry, even when that league has no
    data for `season` (mirrors `src.pathways.youth_exposure`'s own
    "always emit a row" rule) -- `n_clubs: 0`, `n_clubs_above: 0`,
    `share_clubs_above: None`.
    """
    rows = []
    for country, league in league_by_country.items():
        t = tables[(tables.league == league) & (tables.season == season)]
        if t.empty:
            rows.append({
                "country": country, "league": league,
                "n_clubs": 0, "n_clubs_above": 0, "share_clubs_above": None,
            })
            continue
        age = t["born"].map(lambda b: _age(b, season))
        young_min = t["min"].where(age <= 21, 0)
        by_club = pd.DataFrame({"team": t["team"], "min": t["min"], "young_min": young_min}).groupby("team").sum()
        share = by_club["young_min"] / by_club["min"]
        n_clubs = int(len(by_club))
        n_above = int((share > BREADTH_THRESHOLD).sum())
        rows.append({
            "country": country, "league": league,
            "n_clubs": n_clubs, "n_clubs_above": n_above,
            "share_clubs_above": n_above / n_clubs if n_clubs else None,
        })
    return pd.DataFrame(rows, dtype=object)


def age_structure(tables: pd.DataFrame, season: str, league_by_country: dict[str, str]) -> pd.DataFrame:
    """Per country's own domestic league: minutes-weighted mean age of a
    minute played, and the share of minutes played by players aged 22 or
    under / 30 or over (any nationality).

    A row with no `born` year is excluded from the mean (its age is
    unknown) but its minutes still count in the two shares' denominator
    (mirrors `youth_exposure`'s own total, which is every minute in the
    league regardless of whether the player's age is known). One row per
    `league_by_country` entry; a league absent for `season` gets
    `minutes_total: 0` and every other field `None`.
    """
    rows = []
    for country, league in league_by_country.items():
        t = tables[(tables.league == league) & (tables.season == season)]
        if t.empty:
            rows.append({
                "country": country, "league": league, "minutes_total": 0,
                "weighted_mean_age": None, "share_le22": None, "share_ge30": None,
            })
            continue
        age = t["born"].map(lambda b: _age(b, season))
        has_age = age.notna()
        total = float(t["min"].sum())
        age_min_total = float(t.loc[has_age, "min"].sum())
        mean_age = (
            float((age[has_age] * t.loc[has_age, "min"]).sum() / age_min_total) if age_min_total else None
        )
        rows.append({
            "country": country, "league": league, "minutes_total": total,
            "weighted_mean_age": mean_age,
            "share_le22": float(t.loc[has_age & (age <= 22), "min"].sum()) / total if total else None,
            "share_ge30": float(t.loc[has_age & (age >= 30), "min"].sum()) / total if total else None,
        })
    return pd.DataFrame(rows, dtype=object)


def first_move_abroad(
    tables: pd.DataFrame, league_by_country: dict[str, str], countries: list[str],
    current: str | None = None, min_minutes: int = MIN_MINUTES_FIRST_MOVE,
) -> pd.DataFrame:
    """Per country: age at a player's first season (>= `min_minutes`) in
    any league other than that country's own domestic one, restricted to
    players currently (`current`, defaulting to `tables.season.max()`)
    rostered abroad with at least `min_minutes` -- the same "who is on the
    roster now, then walk their own history" construction
    `src.pathways.export_route` uses, minus its headline-league
    restriction on either end. Deduped to one row per (player_key, season)
    via `_dedupe_player_season`, same as every other exhibit in
    `src.pathways`.

    A country with no configured domestic league (`league_by_country` has
    no entry) or with zero players currently qualifying gets `n: 0`,
    `median_age: None`, `censored_share: 0.0`, not a dropped row.
    `censored_share`: the same rule as `src.pathways.export_route` -- a
    player whose qualifying first-abroad season is the table's own
    earliest season is censored (an earlier one may exist outside our
    fetched window).
    """
    t = _dedupe_player_season(tables)
    current = current if current is not None else t.season.max()
    first_hist = t.season.min()
    rows = []
    for country in countries:
        domestic = league_by_country.get(country)
        if domestic is None:
            rows.append({"country": country, "n": 0, "median_age": None, "censored_share": 0.0})
            continue
        on_roster = t[
            (t.season == current) & (t.league != domestic) & (t.nation == country) & (t["min"] >= min_minutes)
        ]
        ages, censored = [], 0
        for pid in on_roster.player_key.unique():
            hist = t[t.player_key == pid].sort_values("season")
            abroad = hist[(hist.league != domestic) & (hist["min"] >= min_minutes)]
            first = abroad.iloc[0]  # non-empty: pid itself qualifies via on_roster
            ages.append(_age(first.born, first.season))
            if first.season == first_hist:
                censored += 1
        n = len(ages)
        rows.append({
            "country": country, "n": n,
            "median_age": float(pd.Series(ages).median()) if n else None,
            "censored_share": censored / n if n else 0.0,
        })
    return pd.DataFrame(rows)


def build_pipeline_facts(tables: pd.DataFrame, cfg: dict, seasons: dict[str, str], peers: list[str]) -> dict:
    """Assemble the full `pipeline_facts.json` payload (no disk I/O)."""
    league_by_country = domestic_league_by_country(cfg, peers)
    return {
        "breadth": club_breadth(tables, seasons["metrics"], league_by_country).to_dict("records"),
        "age_structure": age_structure(tables, seasons["metrics"], league_by_country).to_dict("records"),
        # the metrics season, not the current one: the current season is a
        # few rounds old, so its 450-minute floor leaves a handful of players
        # per country (CZE n=6) — far too thin for a median the funnel quotes
        "first_move_abroad": first_move_abroad(
            tables, league_by_country, peers, seasons["metrics"]
        ).to_dict("records"),
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    cfg, seasons, peers = config.leagues(), config.seasons(), config.PEER_COUNTRIES
    tables = read_parquet(config.PROCESSED_DIR / "fbref_players.parquet")
    out = build_pipeline_facts(tables, cfg, seasons, peers)
    (config.PROCESSED_DIR / "pipeline_facts.json").write_text(json.dumps(out, indent=1, default=float))
    LOG.info("pipeline_facts written")


if __name__ == "__main__":
    main()
