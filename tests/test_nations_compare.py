"""src.nations_compare: the cross-nation export (unit-level, no fitting)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.nations_compare import long_run


def _big5():
    rng = np.random.default_rng(0)
    rows = []
    leagues = ["ENG-Premier League", "ITA-Serie A", "ESP-La Liga", "GER-Bundesliga", "FRA-Ligue 1"]
    for y in range(1993, 2000):
        season = f"{y}-{y + 1}"
        for lg in leagues:
            if lg == "FRA-Ligue 1" and y < 1995:      # FBref's Ligue 1 starts 1995/96
                continue
            for i in range(30):
                nation = "CZE" if i < 3 else lg[:3]
                born = y - (19 + i % 14)
                rows.append({"league": lg, "season": season, "team": f"T{i % 10}", "player": f"p{nation}{i}",
                             "player_key": f"p{nation}{i}|{born}", "nation": nation, "pos": "MF", "born": born,
                             "age": y - born, "mp": 20, "min": int(rng.integers(300, 2500)), "gls": 1, "ast": 1, "pk": 0, "crdy": 0, "crdr": 0})
    return pd.DataFrame(rows)


def test_long_run_starts_where_all_five_leagues_are_covered_and_carries_the_mechanisms():
    out = long_run(_big5(), {"CZE": {"name": "Czechia", "population_m": 10.9}, "ENG": {"name": "England", "population_m": 57.7}}, fit_breaks=False)
    assert out["seasons"][0] == "1995-1996" and len(out["seasons"]) == 5
    cze = out["countries"]["CZE"]
    assert len(cze["n"]) == 5 and all(0 <= v <= 15 for v in cze["n"])
    assert cze["per_million"][0] == round(cze["n"][0] / 10.9, 2)
    assert len(cze["debut_age"]) == 5 and len(cze["u23_share"]) == 5 and "breaks" not in cze
    # the first covered season has no debutants by construction... unless it is the first season at all
    assert set(out["youth"]) == {"ENG", "ITA", "ESP", "GER", "FRA"}
    assert all(0 <= v <= 1 for v in out["youth"]["ENG"]["own_u21_share"] if v is not None)
