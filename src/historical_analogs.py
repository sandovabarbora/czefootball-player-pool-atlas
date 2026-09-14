"""Historical analogs on the football corpus.

For a showcase Czech-eligible player at age X (metrics season), find the
k-nearest analogs (any nationality, any era in the corpus) whose stats AT
AGE X most resemble the target's, and show how those analogs' careers
continued in their following seasons (up to 4).

This is descriptive analog lookup, not a prediction and not a selection
recommendation: it shows how similarly-profiled players developed, the
reader draws their own conclusions about the range of outcomes.

Corpus: every features_{FW,MF,DF}.parquet row (all nationalities, all
seasons the pipeline has fetched -- metrics/previous/current plus the
2020-2021..2022-2023 history seasons fetched for the nine headline leagues),
filtered to `min >= 450` (the feature pipeline's own inclusion floor, so
this is a no-op filter kept here for clarity/robustness).

Before building the corpus, `main()` runs `utils.collapse_player_seasons`
on each position group's frame: `fbref_players.parquet` has one row per
player-TEAM-season, so a player transferred mid-season has two rows for
the same player_key/season/pos_group. Left as-is, that duplication would
let one transferred player occupy two of the k analog slots in
`find_analogs`, and would double-list them as their own "later season" in
`followed`. The collapse sums `min` and takes a minutes-weighted mean of
the rate/quality columns across the duplicate rows (see
`collapse_player_seasons`'s docstring for the exact rule); everything
downstream (corpus, showcase_ids, find_analogs) then sees one row per
player-season.

`find_analogs` also restricts candidates to the target's own `pos_group`:
comparing e.g. a forward's npG+A per 90 against a defender's is not a
meaningful "historical analog" even at the same age, and the two score on
different scales for this metric.

Output:
    data/processed/showcase.json  -- up to 6 showcase players (2 per
        position group): highest quality-adjusted npG+A per 90, and the
        youngest national-team-flagged player, among Czech-eligible players
        with >= 900 minutes in the metrics season.
    data/processed/analogs.json   -- keyed by showcase player_key, each
        value has `target` (name/age/league/season/min/npg_ast_q) and
        `analogs` (the find_analogs() rows, `followed` included).
"""

from __future__ import annotations

import json
import logging

import pandas as pd

from src import config
from src.utils import collapse_player_seasons, read_parquet

LOG = logging.getLogger(__name__)

SHOWCASE_MIN_MINUTES = 900
CORPUS_MIN_MINUTES = 450


def _age(born: int, season: str) -> int:
    """Season-start age: e.g. born 2002, season '2024-2025' -> 23."""
    return int(season[:4]) + 1 - int(born)


def _target_row(corpus: pd.DataFrame, target_key: str, target_season: str | None) -> pd.Series:
    """The target's metrics-season row when present, else the latest season."""
    season = config.seasons()["metrics"] if target_season is None else target_season
    rows = corpus[corpus.player_key == target_key].sort_values("season")
    in_season = rows[rows.season == season]
    return (in_season if len(in_season) else rows).iloc[-1]


def find_analogs(corpus: pd.DataFrame, target_key: str, k: int = 5,
                 target_season: str | None = None) -> pd.DataFrame:
    """Find the k nearest analogs to `target_key`'s `target_season` row.

    `target_season` defaults to `config.seasons()["metrics"]`; when the
    player has no corpus row in that season the latest season is used, so
    every showcase target is compared at the same (metrics) season.
    Cohort = every other corpus row in the same position group at the same
    season-start age. Distance is Euclidean over z-scored (npg_ast_q, min,
    league_multiplier), z-scored against the whole corpus. `followed` lists
    each analog's own later seasons (up to 4), each with
    season/league/min/npg_ast_q.
    """
    tgt = _target_row(corpus, target_key, target_season)
    age = _age(tgt.born, tgt.season)
    cand = corpus[(corpus.player_key != target_key) & (corpus.pos_group == tgt.pos_group)].copy()
    cand["age"] = [_age(b, s) for b, s in zip(cand.born, cand.season, strict=True)]
    cand = cand[cand.age == age]

    feats = ["npg_ast_q", "min", "league_multiplier"]
    mu, sd = corpus[feats].mean(), corpus[feats].std().replace(0, 1)
    z = (cand[feats] - mu) / sd
    zt = (tgt[feats].astype(float) - mu) / sd
    cand["distance"] = ((z - zt) ** 2).sum(axis=1) ** 0.5

    best = cand.sort_values("distance").head(k).reset_index(drop=True)
    best["rank"] = best.index + 1

    followed = []
    for r in best.itertuples():
        later = (corpus[(corpus.player_key == r.player_key) & (corpus.season > r.season)]
                 .sort_values("season").head(4))
        followed.append([
            {"season": s, "league": lg, "min": int(m), "npg_ast_q": round(float(q), 2)}
            for s, lg, m, q in zip(later.season, later.league, later["min"], later.npg_ast_q, strict=True)
        ])
    best["followed"] = followed
    return best[["rank", "player_key", "player", "nation", "league", "season",
                 "min", "npg_ast_q", "distance", "followed"]]


def showcase_ids(
    feats_by_group: dict[str, pd.DataFrame],
    metrics_season: str,
    headline_leagues: list[str] | None = None,
    domestic_league: str | None = None,
    nt_core_event: str | None = None,
) -> list[dict]:
    """Pick up to 5 showcase players per position group (up to 15 total).

    Among Czech-eligible players in `metrics_season` with `min >= 900`:
        (a) highest npg_p90_quality + ast_p90_quality
        (b) youngest nt_flag player (skipped if already chosen)
        (e) when `nt_core_event` is given: most top-9-league minutes among
            players whose `nt_events` lists that event (the national-team
            core for it) — already-chosen players are skipped and the rule
            falls through to the next player by minutes. Runs before (c) so
            the WC-squad core is not routinely pre-empted by the broader
            top-9-minutes rule below.
        (c) most minutes in the headline (top-9) leagues — the "established
            export"; players already chosen by (a), (b) or (e) are skipped
            and the rule falls through to the next player by minutes.
        (d) under 23 in the metrics season (season start year - born < 23),
            most minutes in the domestic league, and no season in any
            headline league anywhere in the fetched history (across all
            position groups); already chosen players are skipped.
    Rules, not picks: the reason string is descriptive.
    """
    headline = list(config.HEADLINE_LEAGUES if headline_leagues is None else headline_leagues)
    domestic = config.DOMESTIC_LEAGUE if domestic_league is None else domestic_league
    season_start = int(metrics_season[:4])
    ever_abroad: set[str] = set()
    for df in feats_by_group.values():
        if "league" in df.columns:
            ever_abroad.update(df.loc[df.league.isin(headline), "player_key"].unique())
    showcase: list[dict] = []
    seen: set[str] = set()

    def _add(row: pd.Series, group: str, reason: str) -> None:
        showcase.append({
            "player_key": row.player_key,
            "player": row.player,
            "pos_group": group,
            "reason": reason,
        })
        seen.add(row.player_key)

    for group, df in feats_by_group.items():
        cz = df[(df.season == metrics_season) & df.czech_eligible & (df["min"] >= SHOWCASE_MIN_MINUTES)].copy()
        if cz.empty:
            continue
        cz["q"] = cz.npg_p90_quality + cz.ast_p90_quality

        top = cz.sort_values("q", ascending=False).iloc[0]
        if top.player_key not in seen:
            _add(top, group, f"highest quality-adjusted npG+A per 90 among {group}")

        nt = cz[cz.nt_flag].sort_values("born", ascending=False)
        if len(nt) and nt.iloc[0].player_key not in seen:
            _add(nt.iloc[0], group, f"youngest national-team call-up among {group}")

        # Rule (e) runs before the general top-9-minutes rule (c) so the WC-squad
        # core is not systematically pre-empted by (c) whenever the pool's overall
        # top9-minutes leader is also in that squad (the common case).
        if nt_core_event and "nt_events" in cz.columns and "league" in cz.columns:
            core = cz[cz.nt_events.fillna("").str.contains(nt_core_event, regex=False) & cz.league.isin(headline)]
            core_min = core.groupby("player_key")["min"].sum().sort_values(ascending=False)
            for key in core_min.index:
                if key in seen:
                    continue
                row = core[core.player_key == key].iloc[0]
                _add(row, group, f"most top-9 minutes among {nt_core_event} squad {group}")
                break

        if "league" in cz.columns:
            abroad = cz[cz.league.isin(headline)]
            # minutes summed per player across headline-league rows (a mid-season
            # move between two top-9 clubs would otherwise split them)
            top9_min = abroad.groupby("player_key")["min"].sum().sort_values(ascending=False)
            for key in top9_min.index:
                if key in seen:
                    continue
                row = abroad[abroad.player_key == key].iloc[0]
                _add(row, group, f"most top-9 league minutes among {group}")
                break

            home = cz[(cz.league == domestic) & ((season_start - cz.born) < 23)
                      & ~cz.player_key.isin(ever_abroad)]
            home_min = home.groupby("player_key")["min"].sum().sort_values(ascending=False)
            for key in home_min.index:
                if key in seen:
                    continue
                row = home[home.player_key == key].iloc[0]
                _add(row, group,
                     f"most domestic-league minutes among under-23 {group} without a top-9 season")
                break
    return showcase[:15]


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    cfg = config.features()
    seasons_cfg = config.seasons()
    squads_cfg = config.load_yaml("squads.yaml")
    nt_core_event = squads_cfg.get("nt_core_event")
    assert nt_core_event in {e["event"] for e in squads_cfg["events"]}, (
        f"squads.yaml nt_core_event {nt_core_event!r} is not one of the configured events")

    feats_by_group = {g: read_parquet(config.PROCESSED_DIR / f"features_{g}.parquet") for g in cfg["groups"]}
    for g, df in feats_by_group.items():
        df["npg_ast_q"] = df["npg_p90_quality"] + df["ast_p90_quality"]
        n_before = len(df)
        df = collapse_player_seasons(df, rate_cols=["npg_p90_quality", "ast_p90_quality", "npg_ast_q"])
        if len(df) != n_before:
            LOG.info("%s: collapsed %d mid-season-transfer duplicate rows", g, n_before - len(df))
        feats_by_group[g] = df

    corpus = pd.concat(feats_by_group.values(), ignore_index=True)
    n_before = len(corpus)
    # A handful of rows carry no birth year (FBref gap); age can't be derived
    # for them, so they can't take part in age-matched analog lookup.
    corpus = corpus[(corpus["min"] >= CORPUS_MIN_MINUTES) & corpus["born"].notna()].reset_index(drop=True)
    LOG.info("analog corpus: %d player-seasons (%d dropped: <%d min or missing born), seasons=%s",
              len(corpus), n_before - len(corpus), CORPUS_MIN_MINUTES, sorted(corpus.season.unique()))

    showcase = showcase_ids(feats_by_group, seasons_cfg["metrics"], nt_core_event=nt_core_event)

    analogs_out: dict[str, dict] = {}
    for s in showcase:
        key = s["player_key"]
        if corpus[corpus.player_key == key].empty:
            LOG.warning("showcase player %s not found in corpus (min floor?)", key)
            continue
        tgt = _target_row(corpus, key, seasons_cfg["metrics"])
        result = find_analogs(corpus, key, k=5, target_season=seasons_cfg["metrics"])
        analogs_out[key] = {
            "target": {
                "name": tgt.player,
                "age": _age(tgt.born, tgt.season),
                "league": tgt.league,
                "season": tgt.season,
                "min": int(tgt["min"]),
                "npg_ast_q": round(float(tgt.npg_ast_q), 2),
            },
            "analogs": result.to_dict("records"),
        }
        LOG.info("%s (%s, %s): %d analogs", tgt.player, s["pos_group"], s["reason"], len(result))

    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    (config.PROCESSED_DIR / "showcase.json").write_text(
        json.dumps(showcase, ensure_ascii=False, indent=1), encoding="utf-8")
    (config.PROCESSED_DIR / "analogs.json").write_text(
        json.dumps(analogs_out, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    LOG.info("wrote showcase.json (%d players) and analogs.json", len(showcase))


if __name__ == "__main__":
    main()
