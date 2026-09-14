import pandas as pd

from src.features import _attach_flags, _fill_missing_age, add_quality, bayesian_shrink, per90


def _toy():
    return pd.DataFrame({
        "player_key": ["a", "b", "c"], "league": ["L", "L", "L"], "team": ["T", "T", "U"],
        "min": [2700, 90, 1800], "mp": [30, 1, 20], "gls": [10, 1, 4], "pk": [2, 0, 0],
        "ast": [5, 0, 6], "crdy": [3, 0, 8], "crdr": [0, 0, 1], "team_matches": [34, 34, 34]})


def test_per90_and_min_share():
    out = per90(_toy())
    a = out[out.player_key == "a"].iloc[0]
    assert abs(a.npg_p90 - (8 / 30)) < 1e-9
    assert abs(a.min_share - 2700 / (34 * 90)) < 1e-9
    assert abs(out[out.player_key == "c"].iloc[0].cards_p90 - (10 / 20)) < 1e-9


def test_shrink_pulls_small_sample_to_league_median():
    out = bayesian_shrink(per90(_toy()), k_minutes=900)
    b = out[out.player_key == "b"].iloc[0]          # 1 goal in 90 min: raw 1.0 p90
    assert b.npg_p90_shrunk < 0.5
    a = out[out.player_key == "a"].iloc[0]
    assert abs(a.npg_p90_shrunk - a.npg_p90) < 0.05  # 2700 min barely moves


def test_quality_multiplies_by_league(monkeypatch):
    from src import config
    monkeypatch.setattr(config, "league_quality", lambda: {"multipliers": {"L": 0.5}})
    out = add_quality(bayesian_shrink(per90(_toy())))
    a = out[out.player_key == "a"].iloc[0]
    assert abs(a.npg_p90_quality - a.npg_p90_shrunk * 0.5) < 1e-9


def _toy_two_seasons():
    # League L, two seasons with very different scoring levels. If shrinkage
    # pooled across seasons, player "d" (season 2) would get pulled toward
    # season-1's much higher median instead of season-2's own (low) median.
    return pd.DataFrame({
        "player_key": ["s1a", "s1b", "s2a", "s2b"],
        "league": ["L", "L", "L", "L"],
        "season": ["2023-2024", "2023-2024", "2024-2025", "2024-2025"],
        "team": ["T", "T", "T", "T"],
        "min": [2700, 2700, 90, 2700],
        "mp": [30, 30, 1, 30],
        "gls": [30, 30, 1, 3],   # season 1 median npg_p90 = 1.0; season 2 median (well-sampled) = 0.1
        "pk": [0, 0, 0, 0],
        "ast": [0, 0, 0, 0],
        "crdy": [0, 0, 0, 0],
        "crdr": [0, 0, 0, 0],
        "team_matches": [34, 34, 34, 34],
    })


def test_shrink_groups_by_league_and_season():
    out = bayesian_shrink(per90(_toy_two_seasons()), k_minutes=900)
    s2a = out[out.player_key == "s2a"].iloc[0]
    # If pooled across seasons, the well-sampled prior would be dominated by
    # season 1's median (1.0) and s2a would shrink up toward ~1.0. Grouped by
    # (league, season), it should shrink toward season 2's own median (0.1),
    # staying well below 0.5.
    assert s2a.npg_p90_shrunk < 0.5


def test_shrink_falls_back_to_league_only_when_season_absent():
    # Toy fixture from the brief has no season column: should not raise and
    # should behave like the single-league grouping.
    out = bayesian_shrink(per90(_toy()), k_minutes=900)
    assert "npg_p90_shrunk" in out.columns


def test_fill_missing_age_derives_from_season_and_born():
    df = pd.DataFrame({
        "age": pd.array([pd.NA, 30], dtype="Int64"),
        "season": ["2024-2025", "2023-2024"],
        "born": pd.array([2000, 1994], dtype="Int64"),
    })
    out = _fill_missing_age(df)
    assert out.age.iloc[0] == 25
    assert out.age.iloc[1] == 30


def test_attach_flags_matches_by_player_key_and_guards_namesakes(tmp_path, monkeypatch):
    from src import config

    pool = pd.DataFrame({
        "player_key": ["foreign player|2000"],
        "fbref_id": ["ffffffff"],
        "player": ["Foreign Player"],
        "born": pd.array([2000], dtype="Int64"),
        "pos_group": ["FW"],
        "club_current": ["Some Club"],
        "in_fbref_tables": [True],
    })
    nt = pd.DataFrame({
        "player_norm": ["jan novak", "jan novak", "petr silny"],
        "player": ["Jan Novak", "Jan Novak", "Petr Silny"],
        "born": [1990, 1985, 1988],
        "team": ["A", "A", "A"],
        "event": ["UEFA Euro 2024", "UEFA Euro 2020", "UEFA Euro 2024"],
        "year": [2024, 2020, 2024],
    })
    pool.to_parquet(tmp_path / "pool.parquet", index=False)
    nt.to_parquet(tmp_path / "nt_flags.parquet", index=False)
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)

    df = pd.DataFrame({
        "player_key": ["jan kuchta|1997", "foreign player|2000", "jan novak|1990", "jan novak|1975"],
        "player": ["Jan Kuchta", "Foreign Player", "Jan Novak", "Jan Novak"],
        "born": pd.array([1997, 2000, 1990, 1975], dtype="Int64"),
        "nation": ["CZE", "ENG", "CZE", "CZE"],
    })
    out = _attach_flags(df).set_index("player_key")

    assert out.loc["jan kuchta|1997", "home_eligible"] == True  # noqa: E712 (nation)
    assert out.loc["foreign player|2000", "home_eligible"] == True  # noqa: E712 (pool match)
    assert out.loc["jan novak|1990", "nt_flag"] == True  # noqa: E712
    assert out.loc["jan novak|1990", "nt_events"] == "UEFA Euro 2024"
    # Namesake with a different birth year must NOT be flagged.
    assert out.loc["jan novak|1975", "nt_flag"] == False  # noqa: E712
    assert out.loc["jan novak|1975", "nt_events"] == ""
