"""Pre-registered predictions and their scoreboard (Task 32).

`config/predictions.yaml` is an append-only ledger: what was predicted, on
which day, from which data cut and model-output commit, how it is scored,
and when it can be resolved. This module reads the ledger for the current
nation, compares each open entry with what the live model says today, and
scores each resolved one.

The comparison is the point. A page that quoted the live forecast would let
a refit quietly move the number; a page that quotes the ledger and shows
the live forecast beside it when they differ cannot. `drift` is therefore
not an error -- refitting is legitimate -- but it is always visible.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from src import config


def load_ledger(nation: str | None = None) -> list[dict[str, Any]]:
    """Entries for `nation` (default: the run's home nation), in file order."""
    nation = nation or config.HOME
    entries = config.load_yaml("predictions.yaml").get("predictions", [])
    return [e for e in entries if e.get("nation") == nation]


def score(entry: dict[str, Any]) -> dict[str, Any] | None:
    """Outcome of a resolved entry under its own pre-registered rule:
    whether the interval covered the observed count, and the model's
    absolute error against the naive baseline's. None while unresolved."""
    obs = entry.get("outcome")
    if obs is None:
        return None
    err_model = abs(entry["point"] - obs)
    err_naive = abs(entry["naive"] - obs)
    return {
        "observed": obs,
        "hit": entry["lo"] <= obs <= entry["hi"],
        "err_model": err_model,
        "err_naive": err_naive,
        "beat_naive": err_model < err_naive,
        "tied_naive": err_model == err_naive,
    }


def compare_with_live(entry: dict[str, Any], live: dict[str, Any] | None) -> dict[str, Any] | None:
    """The live model's forecast for the same target, and whether it has
    moved from the registered numbers. None when the live model has no
    forecast for that season."""
    if not live or live.get("season") != entry["target_season"]:
        return None
    moved = (live["median"], live["lo"], live["hi"]) != (entry["point"], entry["lo"], entry["hi"])
    return {"point": live["median"], "lo": live["lo"], "hi": live["hi"], "moved": moved}


def build(live_forecast: dict[str, Any] | None, today: dt.date | None = None,
          nation: str | None = None) -> list[dict[str, Any]]:
    """Ledger entries for the page, each with its score (if resolved), the
    live comparison, and whether it is due for resolution."""
    today = today or dt.date.today()
    out = []
    for e in load_ledger(nation):
        resolve_after = e["resolve_after"]
        if isinstance(resolve_after, str):
            resolve_after = dt.date.fromisoformat(resolve_after)
        out.append(e | {
            "score": score(e),
            "live": compare_with_live(e, live_forecast),
            "due": today > resolve_after and e.get("outcome") is None,
            "resolve_after": resolve_after.isoformat(),
            "registered_on": (e["registered_on"].isoformat() if isinstance(e["registered_on"], dt.date)
                              else str(e["registered_on"])),
        })
    return out
