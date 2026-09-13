"""League quality multipliers from ClubElo (api.clubelo.com/<date>).

multiplier(league) = exp((mean_elo(league) - mean_elo(strongest)) / 400)
i.e. the Elo win-odds scale, so a 120-point gap ≈ 0.74. Strongest = 1.00.

src.utils.http_get has no built-in cache, so a small file cache is kept here
(mirroring src/fetch_squads.py's _fetch_html) to avoid re-hitting ClubElo on
every run.
"""
from __future__ import annotations

import logging
import math
from io import StringIO

import pandas as pd
import yaml

from src import config
from src.utils import http_get

LOG = logging.getLogger(__name__)

__all__ = ["league_multipliers", "main"]


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


def _fetch_csv(date: str) -> str:
    """Fetch the ClubElo CSV for `date`, cached under data/raw/clubelo/<date>.csv."""
    cache_dir = config.RAW_DIR / "clubelo"
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{date}.csv"
    if path.exists():
        return path.read_text(encoding="utf-8")
    resp = http_get(f"http://api.clubelo.com/{date}")
    path.write_text(resp.text, encoding="utf-8")
    return resp.text


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    date = config.seasons()["metrics"].split("-")[1] + "-06-01"   # season end
    csv = _fetch_csv(date)
    elo = pd.read_csv(StringIO(csv))
    m = league_multipliers(elo, _league_map())
    out = {"source": f"ClubElo {date}, league mean of tier clubs, exp(dElo/400), strongest = 1.00",
           "multipliers": m}
    (config.CONFIG_DIR / "league_quality.yaml").write_text(
        yaml.safe_dump(out, sort_keys=False, allow_unicode=True)
    )
    LOG.info("multipliers: %s", m)


if __name__ == "__main__":
    main()
