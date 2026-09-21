"""src/tracking_showcase.py: the SkillCorner open-data match behind the
methodology's tracking figure. Coordinates are kept as the source gives
them: already in the attacking frame for both halves."""

from src.tracking_showcase import build, runs_from_events


def _ev(**kw):
    base = {"event_type": "off_ball_run", "event_subtype": "behind", "player_name": "A", "player_position": "CF",
            "team_shortname": "Home", "attacking_side": "right_to_left", "minute_start": "12", "duration": "2.1",
            "distance_covered": "18", "speed_avg": "22.5", "speed_avg_band": "hsr",
            "x_start": "10", "y_start": "5", "x_end": "28", "y_end": "6",
            "targeted": "True", "received": "False", "dangerous": "True", "lead_to_shot": "False", "lead_to_goal": "False", "xthreat": "0.04"}
    return base | kw


def test_runs_keep_the_source_frame_and_flags():
    runs = runs_from_events([_ev(), _ev(event_type="passing_option"), _ev(x_end="")])
    assert len(runs) == 1
    r = runs[0]
    assert (r["x0"], r["x1"]) == (10.0, 28.0)          # not mirrored for right_to_left
    assert r["targeted"] and r["dangerous"] and not r["received"]
    assert r["speed"] == 22.5 and r["min"] == 12


def test_build_counts_runs_by_type_and_team():
    match = {"id": 1, "date_time": "2025-05-17T09:35:00Z", "home_team": {"short_name": "Home"},
             "away_team": {"short_name": "Away"}, "home_team_score": 0, "away_team_score": 1,
             "competition_edition": {"name": "AUS - A-League - 2024/2025"}, "pitch_length": 105, "pitch_width": 68}
    out = build(match, [_ev(), _ev(team_shortname="Away"), _ev(event_subtype="overlap")])
    assert out["n_runs"] == 3 and out["teams"] == ["Home", "Away"]
    assert out["by_type"]["behind"] == {"Home": 1, "Away": 1}
    assert out["by_type"]["overlap"] == {"Home": 1, "Away": 0}
    assert out["match"]["score"] == "0–1"
