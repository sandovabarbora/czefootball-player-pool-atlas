"""Tests for src/predictions.py -- the pre-registered forecast ledger (Task 32)."""

from __future__ import annotations

import datetime as dt
import json

from src import config
from src.predictions import build, compare_with_live, load_ledger, score


def test_every_ledger_entry_is_complete_and_scorable():
    required = {"id", "nation", "registered_on", "registered_commit", "data_cut", "target_season",
                "quantity", "model", "point", "lo", "hi", "interval", "naive", "scoring", "resolve_after"}
    entries = config.load_yaml("predictions.yaml")["predictions"]
    assert entries
    for e in entries:
        assert required <= set(e), sorted(required - set(e))
        assert e["lo"] <= e["point"] <= e["hi"]
        # resolved entries carry a date; open ones carry neither
        assert (e.get("outcome") is None) == (e.get("resolved_on") is None)


def test_open_entries_match_the_snapshot_model_or_drift_is_declared():
    """While an entry is open, the committed model output should still say
    what the ledger says -- otherwise the page will show a drift line, and
    that is something to decide on, not to discover from a screenshot."""
    for e in load_ledger():
        if e.get("outcome") is not None:
            continue
        sm = json.loads((config.SNAPSHOT_DIR / "series_model.json").read_text())
        live = sm["forecast"].get(config.HOME)
        cmp = compare_with_live(e, live)
        assert cmp is not None, "the snapshot model has no forecast for the ledger's target season"
        assert not cmp["moved"], f"live forecast {cmp} differs from the registered {e['point']} ({e['lo']}-{e['hi']})"


def test_score_applies_the_registered_rule():
    e = {"point": 11, "lo": 5, "hi": 18, "naive": 10, "outcome": 14}
    s = score(e)
    assert s["hit"] and s["err_model"] == 3 and s["err_naive"] == 4 and s["beat_naive"]
    e["outcome"] = 4
    s = score(e)
    assert not s["hit"] and s["err_model"] == 7 and s["err_naive"] == 6 and not s["beat_naive"]
    assert score({"point": 1, "lo": 0, "hi": 2, "naive": 1, "outcome": None}) is None


def test_build_marks_due_only_after_the_resolution_date():
    live = {"season": "2026-2027", "median": 11, "lo": 5, "hi": 18}
    before = build(live, today=dt.date(2027, 6, 1))
    after = build(live, today=dt.date(2027, 7, 1))
    open_before = [e for e in before if e["outcome"] is None]
    if open_before:
        assert not any(e["due"] for e in open_before)
        assert all(e["due"] for e in after if e["outcome"] is None)
