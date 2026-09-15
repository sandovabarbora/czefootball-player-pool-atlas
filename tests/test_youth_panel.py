"""Tests for src/youth_panel.py -- the cross-country youth-minutes panel (M3).

Task 20 review fix: the headline number is now the between-country fit on
country means (`fit_between_model`/`between_summary`), not the
country-random-intercept fit on the full two-season panel (kept as
`fit_within_model`/`within_summary`, a chapter-IV-only check)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.youth_panel import (
    assemble_output,
    between_summary,
    bootstrap_ols_slope,
    build_panel,
    country_means,
    diagnostics_summary,
    domestic_league_by_country,
    fit_between_model,
    fit_within_model,
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
    assert row["y"] > 0


def test_build_panel_x_increases_with_youth_share():
    tables = _toy_tables()
    panel = build_panel(tables, PEERS_META, ["AAA-Top", "BBB-Top"], LEAGUE_BY_COUNTRY, SEASONS)
    aaa = panel[panel.country == "AAA"].sort_values("season")
    assert aaa.iloc[1]["x"] > aaa.iloc[0]["x"]  # youth share rises season over season


def test_country_means_averages_the_two_seasons():
    panel = pd.DataFrame({
        "country": ["AAA", "AAA", "BBB", "BBB"], "season": ["s1", "s2", "s1", "s2"],
        "season_key": ["previous", "metrics", "previous", "metrics"],
        "x": [0.10, 0.20, 0.05, 0.15], "y": [2.0, 4.0, 1.0, 3.0],
    })
    means = country_means(panel)
    assert set(means["country"]) == {"AAA", "BBB"}
    aaa = means[means.country == "AAA"].iloc[0]
    assert abs(aaa["x"] - 0.15) < 1e-9
    assert abs(aaa["y"] - 3.0) < 1e-9
    bbb = means[means.country == "BBB"].iloc[0]
    assert abs(bbb["x"] - 0.10) < 1e-9
    assert abs(bbb["y"] - 2.0) < 1e-9


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


def _toy_means(n_countries: int = 8, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    countries = [f"C{i}" for i in range(n_countries)]
    x = rng.uniform(0.05, 0.2, size=n_countries)
    y = 2.0 + 15.0 * x + rng.normal(0, 0.3, size=n_countries)
    return pd.DataFrame({"country": countries, "x": x, "y": y})


def test_fit_between_model_smoke_and_recovers_positive_slope():
    means = _toy_means()
    idata = fit_between_model(means, draws=300, tune=300, chains=2, seed=42, cores=2)
    assert "beta_std" in idata.posterior
    assert "u_country" not in idata.posterior  # no country structure in the between fit

    between = between_summary(idata, means)
    assert between["beta_per_10pp"]["lo"] <= between["beta_per_10pp"]["median"] <= between["beta_per_10pp"]["hi"]
    # constructed with a clear positive population slope (15.0) -- the
    # between-country fit on 8 countries should recover a positive sign.
    assert between["beta_per_10pp"]["median"] > 0
    assert -1.0 <= between["r2"] <= 1.0 + 1e-9

    diag = diagnostics_summary(idata, var_names=("alpha_std", "beta_std", "sigma_std"))
    assert diag["max_rhat"] > 0
    assert diag["n_divergences"] >= 0
    assert "sigma_country_median" not in diag


def test_between_model_median_within_25pct_of_ols_on_known_slope():
    """Task 20 review round 2: a raw-scale Normal(0, 20) prior on beta was
    shrinking the posterior median toward zero by an order of magnitude
    relative to OLS on the same 8 country means (x a 0.03-0.15 share, a
    true slope of ~75-80 per unit x sitting ~4 prior SDs out). Fitting on
    standardised x/y with priors scaled to that space (see
    `fit_between_model`'s docstring) should recover a posterior median
    within 25% of the OLS slope on the same synthetic points, wide
    interval notwithstanding."""
    rng = np.random.default_rng(7)
    n = 8
    x = rng.uniform(0.03, 0.15, size=n)  # same raw scale as the real panel (a 0-1 share)
    true_slope = 75.0  # per unit x -- matches the real panel's OLS order of magnitude
    y = 2.0 + true_slope * x + rng.normal(0, 1.5, size=n)
    means = pd.DataFrame({"country": [f"C{i}" for i in range(n)], "x": x, "y": y})

    idata = fit_between_model(means, draws=1000, tune=1000, chains=4, seed=7, cores=2)
    between = between_summary(idata, means)
    ols_slope, _ = ols_fit(x, y)

    beta_median_per_unit = between["beta_per_10pp"]["median"] / 0.10
    ratio = beta_median_per_unit / ols_slope
    assert 0.75 <= ratio <= 1.25, (
        f"posterior median {beta_median_per_unit} vs OLS {ols_slope} (ratio {ratio}) -- "
        "should be within +/-25% for a proper weakly-informative prior"
    )


def test_fit_within_model_smoke_has_country_dim():
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
    idata = fit_within_model(panel, draws=200, tune=200, chains=2, seed=42, cores=2)
    assert "beta" in idata.posterior
    assert "u_country" in idata.posterior
    assert idata.posterior["u_country"].sizes["country"] == 4

    diag = diagnostics_summary(idata)  # default var_names includes sigma_country
    assert diag["max_rhat"] > 0
    assert "sigma_country_median" in diag


def test_assemble_output_shape_has_between_within_ols():
    panel = pd.DataFrame({
        "country": ["AAA", "AAA", "BBB", "BBB"], "season": ["s1", "s2", "s1", "s2"],
        "x": [0.1, 0.2, 0.05, 0.15], "y": [2.0, 4.0, 1.0, 3.0],
    })
    means = country_means(panel.assign(season_key=["previous", "metrics", "previous", "metrics"]))
    between = {"beta_per_10pp": {"median": 1.0, "lo": 0.0, "hi": 2.0}, "alpha": 1.0, "r2": 0.9}
    within = {"beta_per_10pp": {"median": -0.1, "lo": -1.0, "hi": 0.8}, "alpha": 1.0, "r2": 0.5}
    ols = {"slope_per_10pp": {"point": 1.1, "lo": 0.2, "hi": 2.0}, "intercept": 0.5, "n_boot": 1000}
    ols_means = {"slope_per_10pp": {"point": 1.05, "lo": 0.1, "hi": 2.1}, "intercept": 0.4, "n_boot": 1000}
    out = assemble_output(panel, means, between, within, ols, ols_means, {"max_rhat": 1.0}, {"max_rhat": 1.0},
                          ["s1", "s2"])
    assert out["n"] == 4
    assert out["n_countries"] == 2
    assert out["between"]["n"] == 2  # one row per country
    assert out["within"]["n"] == 4  # full panel
    assert out["between"]["beta_per_10pp"]["median"] == 1.0
    assert out["within"]["beta_per_10pp"]["median"] == -0.1
    assert out["ols"]["slope_per_10pp"]["point"] == 1.1
    assert out["ols_means"]["slope_per_10pp"]["point"] == 1.05
    assert len(out["means"]) == 2
    assert len(out["panel"]) == 4
