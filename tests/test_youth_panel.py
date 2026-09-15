"""Tests for src/youth_panel.py -- the cross-country youth-minutes panel (M3)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.youth_panel import (
    bayes_summary,
    bootstrap_ols_slope,
    build_panel,
    diagnostics_summary,
    domestic_league_by_country,
    fit_model,
    ols_fit,
)


def _toy_tables() -> pd.DataFrame:
    """Two seasons, three countries (AAA home + BBB + CCC), one league each,
    own-nation young/old players so `youth_exposure` and `per_capita` both
    have something to chew on."""
    rows = []
    for season, aaa_young_min, bbb_young_min in (("2023-2024", 900, 1800), ("2024-2025", 1800, 2700)):
        rows += [
            {"league": "AAA-Top", "season": season, "player_key": "a-young", "nation": "AAA",
             "born": 2004, "min": aaa_young_min},
            {"league": "AAA-Top", "season": season, "player_key": "a-old", "nation": "AAA",
             "born": 1990, "min": 2700},
            {"league": "BBB-Top", "season": season, "player_key": "b-young", "nation": "BBB",
             "born": 2004, "min": bbb_young_min},
            {"league": "BBB-Top", "season": season, "player_key": "b-old", "nation": "BBB",
             "born": 1990, "min": 2700},
            # CCC's own top flight has no data at all (like SVK-Super Liga) --
            # its players show up abroad only, so per_capita still counts them.
            {"league": "AAA-Top", "season": season, "player_key": "c-abroad", "nation": "CCC",
             "born": 1998, "min": 2000},
        ]
    return pd.DataFrame(rows)


PEERS_META = {
    "AAA": {"name": "Aland", "population_m": 2.0},
    "BBB": {"name": "Borea", "population_m": 4.0},
    "CCC": {"name": "Ceti", "population_m": 1.0},
}
LEAGUE_BY_COUNTRY = {"AAA": "AAA-Top", "BBB": "BBB-Top", "CCC": "CCC-Top"}
SEASONS = {"previous": "2023-2024", "metrics": "2024-2025", "current": "2025-2026"}


def test_domestic_league_by_country_headline_fallback():
    cfg = {
        "domestic": "XXX-First",
        "headline": ["YYY-League One", "ZZZ-League Two"],
        "peer_domestic": {"WWW-Top": {"country": "WWW", "tier": 1}},
        "custom": {},
    }
    out = domestic_league_by_country(cfg, ["WWW", "YYY", "ZZZ"])
    assert out["WWW"] == "WWW-Top"
    assert out["YYY"] == "YYY-League One"
    assert out["ZZZ"] == "ZZZ-League Two"


def test_build_panel_two_seasons_three_countries_drops_missing_x():
    tables = _toy_tables()
    panel = build_panel(tables, PEERS_META, ["AAA-Top", "BBB-Top"], LEAGUE_BY_COUNTRY, SEASONS)
    # CCC has no data for its own top flight (CCC-Top never appears in
    # `tables`) -- youth_exposure returns share_u21=None for it, so it is
    # dropped from every season's rows, leaving 2 countries x 2 seasons = 4.
    assert len(panel) == 4
    assert set(panel["country"]) == {"AAA", "BBB"}
    assert set(panel["season"]) == {"2023-2024", "2024-2025"}

    row = panel[(panel.country == "AAA") & (panel.season == "2023-2024")].iloc[0]
    # AAA-Top's total minutes include c-abroad's (CCC plays in AAA-Top too):
    # 900 (a-young) + 2700 (a-old) + 2000 (c-abroad) = 5600.
    assert abs(row["x"] - 900 / 5600) < 1e-9
    # AAA has 1 top-9-league player (itself, since AAA-Top is headline) per
    # 2.0 M population... but AAA-Top/BBB-Top aren't literally headline in
    # config terms here; per_capita just counts distinct nationals in the
    # given headline_leagues list, which is ["AAA-Top", "BBB-Top"] above --
    # AAA has 2 own nationals in AAA-Top plus none elsewhere.
    assert row["y"] > 0


def test_build_panel_x_increases_with_youth_share():
    tables = _toy_tables()
    panel = build_panel(tables, PEERS_META, ["AAA-Top", "BBB-Top"], LEAGUE_BY_COUNTRY, SEASONS)
    aaa = panel[panel.country == "AAA"].sort_values("season")
    assert aaa.iloc[1]["x"] > aaa.iloc[0]["x"]  # youth share rises season over season


def test_ols_fit_recovers_known_slope():
    x = np.array([0.0, 0.1, 0.2, 0.3, 0.4])
    y = 2.0 + 30.0 * x  # exact line, slope 30 per unit x = 3.0 per 10pp
    slope, intercept = ols_fit(x, y)
    assert abs(slope - 30.0) < 1e-6
    assert abs(intercept - 2.0) < 1e-6


def test_bootstrap_ols_slope_interval_contains_point():
    rng = np.random.default_rng(0)
    x = np.linspace(0.0, 0.5, 20)
    y = 1.0 + 10.0 * x + rng.normal(0, 0.2, size=20)
    panel = pd.DataFrame({"country": ["Z"] * 20, "season": ["s"] * 20, "season_key": ["metrics"] * 20,
                          "x": x, "y": y})
    out = bootstrap_ols_slope(panel, n_boot=200, seed=1)
    lo, hi = out["slope_per_10pp"]["lo"], out["slope_per_10pp"]["hi"]
    point = out["slope_per_10pp"]["point"]
    assert lo <= point <= hi


def test_fit_model_smoke():
    rng = np.random.default_rng(0)
    countries = ["AAA", "BBB", "CCC", "DDD"] * 2
    x = rng.uniform(0.05, 0.2, size=8)
    y = 2.0 + 15.0 * x + rng.normal(0, 0.3, size=8)
    panel = pd.DataFrame({
        "country": countries,
        "season": ["s1", "s1", "s1", "s1", "s2", "s2", "s2", "s2"],
        "season_key": ["previous"] * 4 + ["metrics"] * 4,
        "x": x, "y": y,
    })
    idata = fit_model(panel, draws=200, tune=200, chains=2, seed=42, cores=2)
    assert "beta" in idata.posterior
    assert "u_country" in idata.posterior
    assert idata.posterior["u_country"].sizes["country"] == 4

    bayes = bayes_summary(idata, panel)
    assert bayes["beta_per_10pp"]["lo"] <= bayes["beta_per_10pp"]["median"] <= bayes["beta_per_10pp"]["hi"]
    assert -1.0 <= bayes["r2"] <= 1.0 + 1e-9

    diag = diagnostics_summary(idata)
    assert diag["max_rhat"] > 0
    assert diag["n_divergences"] >= 0
