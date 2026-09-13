import pandas as pd

from src.fetch_elo import league_multipliers, uefa_coefficient_multipliers


def test_multipliers_scale_strongest_to_one():
    # NOTE: the brief's original fixture (Elo [1900, 1800, 1500, 1400]) gives a
    # 400-point mean gap, which under the documented formula
    # exp(dElo/400) computes to 0.368 -- outside the brief's own asserted
    # 0.5-0.9 bounds. The formula itself is anchored by the module docstring
    # ("120-point gap ~= 0.74") and by the live-run sanity check (ENG=1.0,
    # CZE~=0.55-0.7 with real, full-league Elo averages), so the fixture's
    # gap was adjusted here to be internally consistent instead. See
    # task-5-report.md "Deviations".
    elo = pd.DataFrame({
        "Club": ["A", "B", "C", "D"], "Country": ["ENG", "ENG", "CZE", "CZE"],
        "Level": [1, 1, 1, 1], "Elo": [1900, 1800, 1650, 1550]})
    m = league_multipliers(elo, {"ENG-Premier League": ("ENG", 1), "CZE-First League": ("CZE", 1)})
    assert m["ENG-Premier League"] == 1.0
    assert 0.5 < m["CZE-First League"] < 0.9


def test_uefa_coefficient_multipliers_tier1_and_tier2():
    coefs = {"ENG": 100.0, "GER": 80.0, "CZE": 40.0}
    league_map = {
        "ENG-Premier League": ("ENG", 1),
        "GER-Bundesliga": ("GER", 1),
        "GER-2. Bundesliga": ("GER", 2),
        "CZE-First League": ("CZE", 1),
    }
    m = uefa_coefficient_multipliers(coefs, league_map)
    assert m["ENG-Premier League"] == 1.0
    assert m["GER-Bundesliga"] == 0.8
    assert m["CZE-First League"] == 0.4
    # tier-2 = 0.6 * tier-1 multiplier of the same country
    assert m["GER-2. Bundesliga"] == round(0.6 * 0.8, 3)


def test_uefa_coefficient_multipliers_missing_country_is_skipped():
    coefs = {"ENG": 100.0}
    league_map = {"ENG-Premier League": ("ENG", 1), "XXX-Nowhere League": ("XXX", 1)}
    m = uefa_coefficient_multipliers(coefs, league_map)
    assert m == {"ENG-Premier League": 1.0}
