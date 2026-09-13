"""League quality multipliers from ClubElo (api.clubelo.com/<date>), with a
UEFA-coefficient fallback when ClubElo is unreachable.

Primary method (`method: clubelo`):
    multiplier(league) = exp((mean_elo(league) - mean_elo(strongest)) / 400)
    i.e. the Elo win-odds scale, so a 120-point gap ≈ 0.74. Strongest = 1.00.

Fallback method (`method: uefa_coefficient`), used only when the ClubElo
fetch raises an HTTP error (e.g. its CSV backend is down):
    tier-1 multiplier(league) = coef[country] / max(coef over tier-1 countries)
    tier-2 multiplier(league) = 0.6 * tier-1 multiplier of the same country
    (stated assumption -- a typical 2nd-tier league is materially weaker than
    its country's top flight; 0.6 is not derived from data).
`coef` is UEFA's men's association current 5-year coefficient ranking,
scraped from Wikipedia by src.fetch_uefa_coefficients.

src.utils.http_get has no built-in cache, so a small file cache is kept here
via src.utils.cached_text (shared with src/fetch_squads.py and
src/fetch_uefa_coefficients.py) to avoid re-hitting ClubElo on every run.
"""
from __future__ import annotations

import logging
import math
from io import StringIO

import pandas as pd
import requests
import yaml

from src import config, fetch_uefa_coefficients
from src.utils import cached_text

LOG = logging.getLogger(__name__)

TIER2_FACTOR = 0.6

__all__ = ["league_multipliers", "uefa_coefficient_multipliers", "main"]


def league_multipliers(elo: pd.DataFrame, league_map: dict[str, tuple[str, int]]) -> dict[str, float]:
    means = {}
    for key, (country, level) in league_map.items():
        sub = elo[(elo.Country == country) & (elo.Level == level)]
        if sub.empty:
            LOG.warning("no ClubElo rows for %s (%s L%d)", key, country, level)
            continue
        means[key] = float(sub.Elo.mean())
    top = max(means.values())
    return {k: round(math.exp((v - top) / 400), 3) for k, v in means.items()}


def _league_map() -> dict[str, tuple[str, int]]:
    """big5 UNION custom UNION peer_domestic, so every fetched league gets a multiplier.

    peer_domestic includes SVK-Super Liga (comp_id: null -- FBref does not
    track it), but ClubElo does carry Slovak clubs, so it is included here.
    """
    cfg = config.leagues()
    big5 = {"ENG-Premier League": ("ENG", 1), "ITA-Serie A": ("ITA", 1), "ESP-La Liga": ("ESP", 1),
            "GER-Bundesliga": ("GER", 1), "FRA-Ligue 1": ("FRA", 1)}
    custom = {k: (v["country"], v["tier"]) for k, v in cfg["custom"].items()}
    peer_domestic = {k: (v["country"], v["tier"]) for k, v in cfg["peer_domestic"].items()}
    return {**big5, **custom, **peer_domestic}


def uefa_coefficient_multipliers(
    coefs: dict[str, float],
    league_map: dict[str, tuple[str, int]],
    tier2_factor: float = TIER2_FACTOR,
) -> dict[str, float]:
    """Fallback multipliers from UEFA association coefficients (see module docstring).

    Tier-1 leagues scale directly off `coefs`; tier-2 leagues (e.g.
    GER-2. Bundesliga) take `tier2_factor` times their own country's tier-1
    multiplier when that tier-1 league is present in `league_map`, else
    `tier2_factor` times the country's own coef/top ratio.
    """
    tier1 = {k: country for k, (country, tier) in league_map.items() if tier == 1}
    present = {k: coefs[country] for k, country in tier1.items() if country in coefs}
    missing = set(tier1) - set(present)
    for k in missing:
        LOG.warning("no UEFA coefficient for %s (%s), skipping", k, tier1[k])
    top = max(present.values())

    m: dict[str, float] = {k: round(v / top, 3) for k, v in present.items()}

    for k, (country, tier) in league_map.items():
        if tier == 1:
            continue
        tier1_key = next((k2 for k2, c2 in tier1.items() if c2 == country), None)
        if tier1_key is not None and tier1_key in m:
            m[k] = round(tier2_factor * m[tier1_key], 3)
        elif country in coefs:
            m[k] = round(tier2_factor * (coefs[country] / top), 3)
        else:
            LOG.warning("no UEFA coefficient for %s (%s), skipping", k, country)
    return m


def _fetch_csv(date: str) -> str:
    """Fetch the ClubElo CSV for `date`, cached under data/raw/clubelo/<date>.csv."""
    cache_path = config.RAW_DIR / "clubelo" / f"{date}.csv"
    return cached_text(f"http://api.clubelo.com/{date}", cache_path)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    date = config.seasons()["metrics"].split("-")[1] + "-06-01"   # season end
    league_map = _league_map()
    try:
        csv = _fetch_csv(date)
        elo = pd.read_csv(StringIO(csv))
        m = league_multipliers(elo, league_map)
        method = "clubelo"
        source = f"ClubElo {date}, league mean of tier clubs, exp(dElo/400), strongest = 1.00"
    except requests.RequestException as exc:
        LOG.warning("ClubElo fetch failed (%s); falling back to UEFA coefficient ranking", exc)
        coefs, seasons = fetch_uefa_coefficients.fetch_country_coefficients()
        m = uefa_coefficient_multipliers(coefs, league_map)
        method = "uefa_coefficient"
        season_span = f"{seasons[0]}–{seasons[-1]}" if seasons else "current"
        source = (
            f"ClubElo unavailable at run time (HTTP error); fell back to Wikipedia's UEFA "
            f"men's association coefficient, current 5-year ranking ({season_span} seasons). "
            f"tier-1 multiplier = coef[country] / max(coef); tier-2 multiplier = "
            f"{TIER2_FACTOR} * tier-1 multiplier of the same country (stated assumption, "
            f"not derived from data). Strongest tier-1 country = 1.00."
        )
    out = {"source": source, "method": method, "multipliers": m}
    (config.CONFIG_DIR / "league_quality.yaml").write_text(
        yaml.safe_dump(out, sort_keys=False, allow_unicode=True)
    )
    LOG.info("method=%s multipliers: %s", method, m)


if __name__ == "__main__":
    main()
