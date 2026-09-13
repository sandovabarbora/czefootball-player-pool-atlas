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
from src.utils import read_parquet

LOG = logging.getLogger(__name__)

SHOWCASE_MIN_MINUTES = 900
CORPUS_MIN_MINUTES = 450


def _age(born: int, season: str) -> int:
    """Season-start age: e.g. born 2002, season '2024-2025' -> 23."""
    return int(season[:4]) + 1 - int(born)


def find_analogs(corpus: pd.DataFrame, target_key: str, k: int = 5) -> pd.DataFrame:
    """Find the k nearest analogs to `target_key`'s most recent corpus season.

    Cohort = every other corpus row at the same season-start age. Distance
    is Euclidean over z-scored (npg_ast_q, min, league_multiplier), z-scored
    against the whole corpus. `followed` lists each analog's own later
    seasons (up to 4), each with season/league/min/npg_ast_q.
    """
    tgt = corpus[corpus.player_key == target_key].sort_values("season").iloc[-1]
    age = _age(tgt.born, tgt.season)
    cand = corpus[corpus.player_key != target_key].copy()
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


def showcase_ids(feats_by_group: dict[str, pd.DataFrame], metrics_season: str) -> list[dict]:
    """Pick up to 2 showcase players per position group (up to 6 total).

    Among Czech-eligible players in `metrics_season` with `min >= 900`:
        (a) highest npg_p90_quality + ast_p90_quality
        (b) youngest nt_flag player (skipped if already chosen)
    """
    showcase: list[dict] = []
    seen: set[str] = set()
    for group, df in feats_by_group.items():
        cz = df[(df.season == metrics_season) & df.czech_eligible & (df["min"] >= SHOWCASE_MIN_MINUTES)].copy()
        if cz.empty:
            continue
        cz["q"] = cz.npg_p90_quality + cz.ast_p90_quality

        top = cz.sort_values("q", ascending=False).iloc[0]
        if top.player_key not in seen:
            showcase.append({
                "player_key": top.player_key,
                "player": top.player,
                "pos_group": group,
                "reason": f"highest quality-adjusted npG+A per 90 among {group}",
            })
            seen.add(top.player_key)

        nt = cz[cz.nt_flag].sort_values("born", ascending=False)
        if len(nt) and nt.iloc[0].player_key not in seen:
            youngest = nt.iloc[0]
            showcase.append({
                "player_key": youngest.player_key,
                "player": youngest.player,
                "pos_group": group,
                "reason": f"youngest national-team call-up among {group}",
            })
            seen.add(youngest.player_key)
    return showcase[:6]


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    cfg = config.features()
    seasons_cfg = config.seasons()

    feats_by_group = {g: read_parquet(config.PROCESSED_DIR / f"features_{g}.parquet") for g in cfg["groups"]}
    for df in feats_by_group.values():
        df["npg_ast_q"] = df["npg_p90_quality"] + df["ast_p90_quality"]

    corpus = pd.concat(feats_by_group.values(), ignore_index=True)
    n_before = len(corpus)
    # A handful of rows carry no birth year (FBref gap); age can't be derived
    # for them, so they can't take part in age-matched analog lookup.
    corpus = corpus[(corpus["min"] >= CORPUS_MIN_MINUTES) & corpus["born"].notna()].reset_index(drop=True)
    LOG.info("analog corpus: %d player-seasons (%d dropped: <%d min or missing born), seasons=%s",
              len(corpus), n_before - len(corpus), CORPUS_MIN_MINUTES, sorted(corpus.season.unique()))

    showcase = showcase_ids(feats_by_group, seasons_cfg["metrics"])

    analogs_out: dict[str, dict] = {}
    for s in showcase:
        key = s["player_key"]
        tgt_rows = corpus[corpus.player_key == key].sort_values("season")
        if tgt_rows.empty:
            LOG.warning("showcase player %s not found in corpus (min floor?)", key)
            continue
        tgt = tgt_rows.iloc[-1]
        result = find_analogs(corpus, key, k=5)
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
