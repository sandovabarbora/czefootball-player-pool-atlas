"""What changed in the pool between the previous season and the metrics one.

The trajectory tables (`src.trajectory`) already say, player by player, whose
quality-adjusted production rose or fell. This module answers the coarser
question a federation reader asks first: did the pool as a whole move
somewhere -- up a tier, down one, out of the covered leagues, into them --
and how did its minutes move with it. Both seasons are read from the
feature tables, the same rows every other exhibit uses, and a player counts
as present in a season when he cleared the report's own inclusion floor
(`min_minutes`, five full matches) in it.

Per home-eligible player, the lead league of each season (most minutes) is
placed on the pathway's tier ladder -- domestic, other covered league,
stepping stone, top-9, in that order -- and the move between the two
seasons is one of:

    up        a higher rung than last season
    down      a lower rung
    lateral   the same rung, a different league
    stayed    the same league (a change of club within it is still "stayed")
    entered   no qualifying season last year, one this year
    left      a qualifying season last year, none this year -- which means
              retired, injured, or in a league this report does not cover;
              the data cannot tell those apart and the copy must not guess

Minutes are summed per tier for each season, so the panel can also say
where the pool's playing time went, not only where its players did.

Output: data/processed/<nation>/season_changes.json
"""

from __future__ import annotations

import json
import logging

import pandas as pd

from src import config
from src.pool_table import _tier
from src.utils import read_parquet

LOG = logging.getLogger(__name__)

GROUPS = ("FW", "MF", "DF")
TIER_RANK = {"domestic": 0, "other": 1, "stepping_stone": 2, "top9": 3}
MOVES = ("up", "down", "lateral", "stayed", "entered", "left")
NAMES_PER_MOVE = 6
"""Names listed under each move, most minutes this season first (last
season's minutes for `left`): enough to make the count concrete, few
enough to stay a panel rather than a table."""


def _lead(frame: pd.DataFrame) -> pd.DataFrame:
    """One row per player and season: the league where he played most."""
    per = frame.groupby(["player_key", "season", "league"], as_index=False).agg(
        min=("min", "sum"), player=("player", "first"), team=("team", "first"))
    return per.sort_values("min", ascending=False).drop_duplicates(["player_key", "season"])


def classify(
    feats: pd.DataFrame,
    previous: str,
    metrics: str,
    min_minutes: int,
    headline: list[str],
    stepping: list[str],
    domestic: str,
) -> pd.DataFrame:
    """One row per home-eligible player present in either season, with his
    lead league and tier in each and the move between them."""
    f = feats[feats.home_eligible & feats.season.isin([previous, metrics])]
    lead = _lead(f)
    lead = lead[lead["min"] >= min_minutes]
    prev = lead[lead.season == previous].set_index("player_key")
    curr = lead[lead.season == metrics].set_index("player_key")
    keys = sorted(set(prev.index) | set(curr.index))
    rows = []
    for k in keys:
        p = prev.loc[k] if k in prev.index else None
        c = curr.loc[k] if k in curr.index else None
        row = {
            "player_key": k,
            "player": (c if c is not None else p)["player"],
            "league_prev": None if p is None else p["league"],
            "league_curr": None if c is None else c["league"],
            "team_curr": None if c is None else c["team"],
            "min_prev": 0 if p is None else int(p["min"]),
            "min_curr": 0 if c is None else int(c["min"]),
        }
        row["tier_prev"] = None if p is None else _tier(p["league"], headline, stepping, domestic)
        row["tier_curr"] = None if c is None else _tier(c["league"], headline, stepping, domestic)
        if p is None:
            row["move"] = "entered"
        elif c is None:
            row["move"] = "left"
        elif TIER_RANK[row["tier_curr"]] > TIER_RANK[row["tier_prev"]]:
            row["move"] = "up"
        elif TIER_RANK[row["tier_curr"]] < TIER_RANK[row["tier_prev"]]:
            row["move"] = "down"
        elif row["league_curr"] != row["league_prev"]:
            row["move"] = "lateral"
        else:
            row["move"] = "stayed"
        rows.append(row)
    return pd.DataFrame(rows)


def summarise(moves: pd.DataFrame, names_per_move: int = NAMES_PER_MOVE) -> dict:
    """Counts per move with a few names each, and the pool's minutes by tier
    in both seasons."""
    out = {"moves": {}, "minutes_by_tier": {}}
    for m in MOVES:
        sub = moves[moves.move == m]
        order = "min_prev" if m == "left" else "min_curr"
        top = sub.sort_values(order, ascending=False).head(names_per_move)
        out["moves"][m] = {
            "n": int(len(sub)),
            "names": [{"player": r.player, "player_key": r.player_key,
                       "league_prev": r.league_prev, "league_curr": r.league_curr,
                       "tier_prev": r.tier_prev, "tier_curr": r.tier_curr,
                       "min_prev": int(r.min_prev), "min_curr": int(r.min_curr)}
                      for r in top.itertuples()],
        }
    for tier in TIER_RANK:
        out["minutes_by_tier"][tier] = {
            "prev": int(moves.loc[moves.tier_prev == tier, "min_prev"].sum()),
            "curr": int(moves.loc[moves.tier_curr == tier, "min_curr"].sum()),
            "players_prev": int((moves.tier_prev == tier).sum()),
            "players_curr": int((moves.tier_curr == tier).sum()),
        }
    out["n_prev"] = int(moves.tier_prev.notna().sum())
    out["n_curr"] = int(moves.tier_curr.notna().sum())
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    p, cfg, seasons = config.PROCESSED_DIR, config.leagues(), config.seasons()
    feats = pd.concat([read_parquet(p / f"features_{g}.parquet") for g in GROUPS], ignore_index=True)
    moves = classify(feats, seasons["previous"], seasons["metrics"], config.features()["min_minutes"],
                     cfg["headline"], cfg["stepping_stone"], config.DOMESTIC_LEAGUE)
    payload = {"previous": seasons["previous"], "metrics": seasons["metrics"],
               "min_minutes": config.features()["min_minutes"]} | summarise(moves)
    (p / "season_changes.json").write_text(json.dumps(payload, indent=1, default=float))
    LOG.info("season_changes written: %s", {m: v["n"] for m, v in payload["moves"].items()})


if __name__ == "__main__":
    main()
