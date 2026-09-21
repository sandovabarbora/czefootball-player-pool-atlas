"""What tracking data would add: one match from SkillCorner's open data.

The atlas is built from season tables -- goals, assists, minutes, starts,
crosses -- because that is what exists for every league in the benchmark.
Tracking data (every player's position ten times a second) exists for none
of them publicly. This module takes one match from SkillCorner's open-data
release (A-League 2024/25, MIT licence) and prepares its off-ball runs for
an interactive pitch figure in the methodology chapter, so the report can
show concretely what the next layer of data looks like and what it would
answer that season tables cannot.

Nothing here enters any number the atlas reports; the figure is a
demonstration on a different league, labelled as such on the page.

Data: `data/matches/<id>/<id>_dynamic_events.csv` and `<id>_match.json` from
https://github.com/SkillCorner/opendata (fetched once, cached under
data/raw/skillcorner/). Runs are normalised so both teams attack left to
right by the source itself; pitch 105 x 68 m, origin at the centre spot.

Output: outputs/<nation>/charts/tracking_runs.json
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

from src import config
from src.utils import http_get

LOG = logging.getLogger(__name__)

REPO_RAW = "https://raw.githubusercontent.com/SkillCorner/opendata/master/data/matches"
MATCH_ID = 2017461   # Melbourne Victory v Auckland FC, 17 May 2025 -- the last match in the release
CACHE = config.RAW_DIR / "skillcorner"

RUN_FIELDS = ("event_subtype", "player_name", "player_position", "team_shortname", "attacking_side",
              "minute_start", "duration", "distance_covered", "speed_avg", "speed_avg_band",
              "x_start", "y_start", "x_end", "y_end", "targeted", "received", "dangerous",
              "lead_to_shot", "lead_to_goal", "xthreat")


def _fetch(name: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / name
    if not path.exists():
        LOG.info("fetching %s", name)
        path.write_bytes(http_get(f"{REPO_RAW}/{MATCH_ID}/{name}").content)
    return path


def _num(v: str) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _flag(v: str) -> bool:
    return str(v).strip().lower() in ("true", "1", "yes")


def runs_from_events(rows: list[dict]) -> list[dict]:
    """Off-ball runs; the source's frame already has both teams attacking
    toward positive x."""
    out = []
    for r in rows:
        if r.get("event_type") != "off_ball_run":
            continue
        x0, y0, x1, y1 = (_num(r.get(k)) for k in ("x_start", "y_start", "x_end", "y_end"))
        if None in (x0, y0, x1, y1):
            continue
        # SkillCorner's dynamic-event coordinates are already in the attacking
        # team's frame (positive x toward the goal being attacked) in both
        # halves -- checked on this match: runs "in behind" average +19 m and
        # +15 m in x for left_to_right and right_to_left alike. No flip.
        out.append({
            "sub": r.get("event_subtype") or "other",
            "p": r.get("player_name") or "", "pos": r.get("player_position") or "",
            "team": r.get("team_shortname") or "",
            "min": int(float(r.get("minute_start") or 0)),
            "dur": _num(r.get("duration")), "dist": _num(r.get("distance_covered")),
            "speed": _num(r.get("speed_avg")), "band": r.get("speed_avg_band") or "",
            "x0": round(x0, 2), "y0": round(y0, 2), "x1": round(x1, 2), "y1": round(y1, 2),
            "targeted": _flag(r.get("targeted")), "received": _flag(r.get("received")),
            "dangerous": _flag(r.get("dangerous")), "shot": _flag(r.get("lead_to_shot")),
            "goal": _flag(r.get("lead_to_goal")), "xt": _num(r.get("xthreat")),
        })
    return out


def build(match: dict, rows: list[dict]) -> dict:
    runs = runs_from_events(rows)
    teams = [match["home_team"]["short_name"], match["away_team"]["short_name"]]
    by_type: dict[str, dict[str, int]] = {}
    for r in runs:
        by_type.setdefault(r["sub"], {t: 0 for t in teams})
        by_type[r["sub"]][r["team"]] = by_type[r["sub"]].get(r["team"], 0) + 1
    return {
        "source": "SkillCorner open data (A-League 2024/25, MIT)",
        "match": {
            "id": match["id"], "date": match["date_time"][:10],
            "home": match["home_team"]["short_name"], "away": match["away_team"]["short_name"],
            "score": f'{match["home_team_score"]}–{match["away_team_score"]}',
            "competition": match["competition_edition"]["name"],
            "pitch": [match.get("pitch_length", 105), match.get("pitch_width", 68)],
        },
        "teams": teams,
        "n_runs": len(runs),
        "by_type": by_type,
        "runs": runs,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    match = json.loads(_fetch(f"{MATCH_ID}_match.json").read_text(encoding="utf-8"))
    with _fetch(f"{MATCH_ID}_dynamic_events.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    payload = build(match, rows)
    out = config.OUTPUTS_DIR / "charts"
    out.mkdir(parents=True, exist_ok=True)
    (out / "tracking_runs.json").write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
    LOG.info("%d off-ball runs from %s v %s", payload["n_runs"], payload["match"]["home"], payload["match"]["away"])


if __name__ == "__main__":
    main()
