"""Age at export (M1 proper): does leaving later go with anything? PyMC 5.

Football question (Task 23, spec §2 M1): "Do we sell our best 21-year-olds
too late?" Analytical question: league-adjusted production in a player's
first two top-{topn} seasons as a function of their age at the first such
season, given origin-league strength and position, with a country effect --
the caveat that selection (better players tend to leave earlier) is not
separated from development is part of the finding, not a footnote to it.

Corpus (`build_corpus`): every player of every peer nationality (home nation
included -- `config.PEER_COUNTRIES` already carries it first, same set
`src.pathways`/`src.youth_panel` use) whose first top-9-league season with
>= 450 minutes (`config.features()["min_minutes"]`, the same floor already
baked into `features_{FW,MF,DF}.parquet` -- see that module) lies inside the
fetched window and is not censored. "Censored" reuses `src.pathways.
export_route`'s own rule (not exposed there as a standalone helper, so
duplicated here, same as `src.youth_panel.domestic_league_by_country`
duplicates that module's tier-1-by-country construction): a player whose
first qualifying season IS the earliest season in the fetched roster tables
(`fbref_players.parquet`) has no visible history before it, so their true
origin is unknown, not "not covered" -- dropped, not guessed at. A player
with a qualifying first season that isn't censored but who nonetheless has
no earlier row at all in the roster tables (a genuine professional debut,
not a data-coverage artifact) is dropped for the same practical reason --
no origin league to price -- documented here rather than reported as a
third, spurious "origin unknown" category.

For every surviving player: `age_export` = the `age` column of that first
qualifying row (the report's own "age at the season's start" feature,
already computed by `src.features.per90`, not recomputed here under a
different convention); `origin_strength` = the transfer-graph model's (M2,
`src.league_strength`) `m_L` for the league of the season immediately before
the first qualifying one, or -- where M2 has no fitted estimate for that
league -- the UEFA-coefficient multiplier (`config.league_quality()`);
`origin_source` records which of the two was used, per row; `y` = the mean
of `npg_p90_quality + ast_p90_quality` (the report's own league-adjusted
production feature) over the player's first one or two qualifying top-9
seasons (`n_seasons` flags which); `pos_group` and `nation` carry through
from the first qualifying row.

Model (`fit_model`), PyMC 5, non-centred throughout:

    y ~ Normal(mu, sigma)
    mu = alpha + f(age) + beta*origin_strength + gamma_pos + u_nation

`f(age)` is a natural cubic spline with knots at 19, 21, 23, 25
(`natural_cubic_spline_basis`, the standard truncated-power-basis
construction -- ESL section 5.2.1 -- since `patsy`/`formulaic` are not
dependencies here), or a plain quadratic in centred age when the corpus is
small (`n < SPLINE_MIN_N = 150`; which branch was used is recorded in the
output). `u_nation ~ Normal(0, sigma_n)` is a non-centred partial-pooling
country random intercept, the same construction as `src.league_strength`'s
`b_league`/`src.youth_panel`'s `u_country`.

Standardised-priors lesson (`src.youth_panel`'s own review-round-2 fix,
explicitly reused here): the spline design columns are `(age - knot)_+^3`
differences, tens to low thousands in raw units over this corpus's age
range -- a raw-scale "weakly informative" prior on their coefficients would
in fact be wildly informative, the exact failure mode `youth_panel`'s
docstring documents for its own beta. Every design column (the spline/
quadratic age columns, `origin_strength`) AND the outcome `y` are therefore
z-scored before fitting, with `Normal(0, 2.5)`/`HalfNormal(1)` priors on the
standardised parameters (`build_design`); every summary function converts
back to raw (npG+A/90, m_L) units before reporting, exactly mirroring
`src.youth_panel._between_raw_beta_alpha`'s pattern.

4 chains x 1000 draws after 1000 tune, target_accept 0.9, `random_seed =
config.RANDOM_SEED`, PyMC (Abril-Pla et al., 2023), NUTS (Hoffman and
Gelman, 2014), diagnosed with ArviZ. The same model refit without
`origin_strength` (`use_strength=False`) shows what the league term
absorbs: if origin strength carries some of what otherwise reads as a
nation effect, `sigma_n` should widen once it is dropped.

Validation:
  1. Posterior predictive check (`ppc_summary`): observed vs. replicated `y`
     -- mean, sd, 10th/90th percentile (Gelman et al., 2013).
  2. Leave-one-nation-out (`run_lono`): refit excluding the home nation's
     own rows (lighter budget, same non-centred model) -- does the age
     curve move? Reported as the shift in the age-21-vs-24 difference and
     in beta between the full and the LONO fit.
  3. Diagnostics: R-hat, ESS, divergence count (`diagnostics_summary`).

Selection caveat (stated, not fixed): the corpus is not a random sample of
players who could have left later -- players who leave earlier tend to be
the ones judged ready earliest, a selection effect the age curve cannot
distinguish from a genuine development effect of arriving young. The curve
describes what age-at-export goes with; it does not identify what delaying
export would do to a given player.

Output: `data/processed/<nation>/export_age_model.json` and figure
`outputs/<nation>/export_age_model.svg` (the fitted curve with its 90% band,
the home nation's own exports as points, a rug of every corpus player's
age).
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import arviz as az
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pymc as pm

from src import config
from src.international_benchmark import CREAM, INK, MUTED, NAVY, OXBLOOD, RULE
from src.logging_setup import setup as logging_setup
from src.utils import collapse_player_seasons, read_parquet

LOG = logging.getLogger(__name__)

AGE_KNOTS: tuple[float, ...] = (19.0, 21.0, 23.0, 25.0)
SPLINE_MIN_N = 150
EVAL_AGES: tuple[int, ...] = (19, 21, 23, 25, 27)

DRAWS, TUNE, CHAINS, TARGET_ACCEPT = 1000, 1000, 4, 0.9
LONO_DRAWS, LONO_TUNE, LONO_CHAINS = 500, 500, 2


# =============================================================================
# Data
# =============================================================================


def _dedupe_player_season(df: pd.DataFrame, key_cols: tuple[str, ...] = ("player_key", "season")) -> pd.DataFrame:
    """Collapse (player_key, season) duplicates from mid-season transfers to
    one row (most-minutes club decides league/team for the season).

    Duplicates `src.pathways._dedupe_player_season` (that module's own
    private helper, not exposed as a standalone function) -- fit to
    `fbref_players.parquet`'s raw shape, which is all this module needs `t`
    for: finding the league of the season immediately before a player's
    first qualifying top-9 season.
    """
    key_cols = list(key_cols)
    sizes = df.groupby(key_cols)["min"].transform("size")
    singles, dup_rows = df[sizes == 1], df[sizes > 1]
    if dup_rows.empty:
        return df
    collapsed = []
    for _, g in dup_rows.groupby(key_cols):
        lead = g.loc[g["min"].idxmax()].to_dict()
        lead["min"] = int(g["min"].sum())
        collapsed.append(lead)
    out = pd.concat([singles, pd.DataFrame(collapsed)], ignore_index=True)
    return out[df.columns.tolist()]


def build_first_seasons(feats: pd.DataFrame) -> pd.DataFrame:
    """One row per (nation, player_key): the player's first top-9-league,
    >= 450-minute season and `y`.

    `feats` is already restricted by the caller to peer nationalities and
    headline leagues (`build_corpus`); the >= 450-minute floor is inherited
    from `features_{FW,MF,DF}.parquet` itself (`src.features.main`), not
    reapplied here. Rows are first collapsed with `collapse_player_seasons`
    for the rare case of a mid-season transfer between two headline clubs
    in the same season (two rows would otherwise both count as "first").

    `y` is the mean of `npg_p90_quality + ast_p90_quality` over the
    player's first one or two qualifying seasons in `feats` (sorted by
    season); `n_seasons` records which (1 or 2) -- most players will have
    only one qualifying row for the metrics season closest to their debut,
    since seasons before/after a debut with < 450 minutes are excluded from
    `feats` entirely, same as everywhere else in this report.
    """
    feats = collapse_player_seasons(feats, rate_cols=["npg_p90_quality", "ast_p90_quality"])
    rows = []
    for (nation, key), g in feats.sort_values("season").groupby(["nation", "player_key"]):
        g = g.reset_index(drop=True)
        first = g.iloc[0]
        two = g.head(2)
        y = float((two["npg_p90_quality"] + two["ast_p90_quality"]).mean())
        rows.append({
            "nation": nation, "player_key": key, "player": first["player"],
            "pos_group": first["pos_group"], "first_season": first["season"],
            "age_export": float(first["age"]), "y": y, "n_seasons": int(len(two)),
        })
    cols = ["nation", "player_key", "player", "pos_group", "first_season", "age_export", "y", "n_seasons"]
    return pd.DataFrame(rows, columns=cols)


def attach_origin(
    rows: pd.DataFrame, tables: pd.DataFrame, m_l_map: dict[str, float], uefa_multipliers: dict[str, float],
) -> pd.DataFrame:
    """Attach `origin_league`/`origin_strength`/`origin_source`, dropping
    censored rows and rows with no priceable origin (see module docstring).

    `tables` is the raw `fbref_players.parquet` frame (every season, every
    league, no minute floor), deduped to one row per (player_key, season).
    For each `rows` entry: censored (`first_season` == the whole table's
    earliest fetched season -- `pathways.export_route`'s own rule) is
    dropped; otherwise the league of the immediately preceding season row
    (any league, any minutes) is the origin; a row with no preceding season
    at all is dropped (nothing to price); `origin_strength` prefers M2's
    `m_L` (`m_l_map`) and falls back to the UEFA multiplier
    (`uefa_multipliers`), recording which in `origin_source`; a league with
    neither on file drops the row (rare, no strength estimate at all).
    """
    t = _dedupe_player_season(tables)
    first_hist = t["season"].min()
    hist_by_key = {k: g.sort_values("season") for k, g in t.groupby("player_key")}

    out = []
    for r in rows.to_dict("records"):
        if r["first_season"] == first_hist:
            continue
        hist = hist_by_key.get(r["player_key"])
        if hist is None:
            continue
        before = hist[hist["season"] < r["first_season"]]
        if before.empty:
            continue
        origin_league = before.iloc[-1]["league"]
        m, source = m_l_map.get(origin_league), "m_L"
        if m is None:
            m, source = uefa_multipliers.get(origin_league), "uefa"
        if m is None:
            continue
        out.append({**r, "origin_league": origin_league, "origin_strength": float(m), "origin_source": source})

    cols = ["nation", "player_key", "player", "pos_group", "first_season", "age_export", "y", "n_seasons",
            "origin_league", "origin_strength", "origin_source"]
    return pd.DataFrame(out, columns=cols)


# =============================================================================
# Age design: natural cubic spline (or quadratic fallback)
# =============================================================================


def natural_cubic_spline_basis(x: np.ndarray, knots: tuple[float, ...]) -> np.ndarray:
    """Natural cubic spline basis, the truncated-power-basis construction
    (Hastie, Tibshirani and Friedman, *The Elements of Statistical
    Learning*, 2nd edn, eqs 5.4-5.5) -- written out directly since
    `patsy`/`formulaic` are not dependencies here.

    For K knots xi_1 < ... < xi_K (`knots`, sorted), returns a `(len(x),
    K-1)` array: column 0 is the plain linear term `x`; columns 1..K-2 are
    `d_k(x) - d_{K-1}(x)` for `k = 1, ..., K-2` (1-indexed), where
    `d_k(x) = ((x-xi_k)_+^3 - (x-xi_K)_+^3) / (xi_K - xi_k)`. The constant
    term (`N_1 = 1` in the ESL numbering) is left to the caller's own model
    intercept, not included here.

    A natural spline is linear outside the boundary knots by construction:
    for `x <= xi_1` every `d_k(x)` is 0 (both truncated cubes vanish), so
    every nonlinear column is exactly 0 there and only the linear term
    survives -- the property `test_natural_cubic_spline_basis_shape_and_
    linear_below_first_knot` checks directly.
    """
    knots = tuple(sorted(knots))
    K = len(knots)
    x = np.asarray(x, dtype=float)
    x_last = knots[-1]

    def _pos_cube(z: np.ndarray) -> np.ndarray:
        return np.clip(z, 0.0, None) ** 3

    def _d(k: int) -> np.ndarray:
        return (_pos_cube(x - knots[k]) - _pos_cube(x - x_last)) / (x_last - knots[k])

    d_ref = _d(K - 2)  # d_{K-1}, 1-indexed -- the (K-1)th knot, 0-indexed K-2
    cols = [x] + [_d(k) - d_ref for k in range(K - 2)]
    return np.column_stack(cols)


def age_design(age: np.ndarray, n: int, knots: tuple[float, ...] = AGE_KNOTS) -> tuple[np.ndarray, list[str], bool]:
    """`(raw_design, column_names, use_spline)` for the age term.

    Natural cubic spline (`natural_cubic_spline_basis`) when the corpus is
    at least `SPLINE_MIN_N` rows, else a quadratic in age centred on the
    corpus's own mean age (brief: "a quadratic if n < 150 -- decide from n
    and state it"). `n` is passed explicitly (not `len(age)`) so a caller
    evaluating the SAME design on a different set of ages (the report
    curve, LONO) uses the branch the ORIGINAL fit chose, not one decided by
    however many evaluation points happen to be passed in.
    """
    age = np.asarray(age, dtype=float)
    use_spline = n >= SPLINE_MIN_N
    if use_spline:
        return natural_cubic_spline_basis(age, knots), ["age_ns1", "age_ns2", "age_ns3"], True
    age_c = (age - 23.0) / 5.0
    return np.column_stack([age_c, age_c**2]), ["age_c", "age_c2"], False


def build_corpus(
    features_by_group: dict[str, pd.DataFrame], tables: pd.DataFrame, peers: list[str], headline: list[str],
    m_l_map: dict[str, float], uefa_multipliers: dict[str, float],
) -> pd.DataFrame:
    """Assemble the full corpus (see module docstring): peer-nationality,
    headline-league rows from `features_{FW,MF,DF}.parquet` reduced to one
    row per player (`build_first_seasons`), then priced with an origin
    league and filtered for censoring (`attach_origin`)."""
    headline_set = set(headline)
    frames = []
    for g, df in features_by_group.items():
        sub = df[df["nation"].isin(peers) & df["league"].isin(headline_set)].copy()
        if "pos_group" not in sub.columns:
            sub["pos_group"] = g
        frames.append(sub)
    feats = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    first = build_first_seasons(feats)
    corpus = attach_origin(first, tables, m_l_map, uefa_multipliers)
    return corpus.reset_index(drop=True)
