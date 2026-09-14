"""National-team call-ups (A + U21) from Wikipedia squad tables -> nt_flags.parquet.

Wikipedia squad tables ("wikitable") list one player per row. On current
Wikipedia, each column-of-interest is reachable independent of exact column
order:
  - the player name is the only link inside a `<th scope="row">` cell (the
    position cell, e.g. "GK", is a plain `<td>` with its own link to a
    position article -- it must not be mistaken for the player link);
  - the date-of-birth cell is identified by its text shape, either
    "(1996-04-27)" or "27 April 1996", never by column position, since caps
    and goals columns are also plain integers.

Section headings are matched by their visible text (Wikipedia currently wraps
headings in a `<div class="mw-heading">` with the "[edit]" link as a sibling
`<span>`, not inside the heading element, so `heading.get_text()` is already
clean).
"""
from __future__ import annotations

import logging
import re

import pandas as pd
from bs4 import BeautifulSoup

from src import config
from src.utils import cached_text, normalize_name, write_parquet

LOG = logging.getLogger(__name__)

USER_AGENT = "czefootball-player-pool-atlas/1.0 (barbora@datasimply.eu)"
DOB_RE = re.compile(r"\(\d{4}-\d{2}-\d{2}\)|\d{1,2} \w+ (?:19|20)\d{2}")
YEAR_RE = re.compile(r"(19|20)\d{2}")

__all__ = ["normalize_name", "parse_squad_section", "main"]


def _birth_year(text: str) -> int | None:
    m = YEAR_RE.search(text or "")
    return int(m.group(0)) if m else None


def _fetch_html(url: str, cache_key: str) -> str:
    """Fetch `url`, cached under data/raw/wiki/<cache_key>.html."""
    cache_path = config.RAW_DIR / "wiki" / f"{cache_key}.html"
    return cached_text(url, cache_path, headers={"User-Agent": USER_AGENT})


def parse_squad_section(html: str, section: str) -> pd.DataFrame:
    """Find the heading whose text starts with `section`, take the first wikitable after it."""
    soup = BeautifulSoup(html, "lxml")
    heading = next(
        (h for h in soup.find_all(["h2", "h3", "h4"]) if h.get_text(strip=True).startswith(section)),
        None,
    )
    if heading is None:
        raise ValueError(f"section {section!r} not found")
    table = heading.find_next("table", class_=re.compile("wikitable"))
    if table is None:
        raise ValueError(f"no wikitable found after section {section!r}")

    rows = []
    for tr in table.select("tr"):
        cells = tr.find_all(["td", "th"])
        texts = [c.get_text(" ", strip=True) for c in cells]
        if len(texts) < 4:
            continue
        # Player name lives in the row's <th scope="row"> cell; the position
        # cell (e.g. "GK") is a <td> with its own link and must be skipped.
        name_cell = next((c for c in cells if c.name == "th" and c.find("a")), None)
        dob = next((t for t in texts if DOB_RE.search(t)), None)
        if name_cell is None or dob is None:
            continue
        name = name_cell.find("a").get_text(strip=True)
        rows.append({"player": name, "player_norm": normalize_name(name), "born": _birth_year(dob)})
    return pd.DataFrame(rows, columns=["player", "player_norm", "born"]).drop_duplicates("player_norm")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    frames = []
    for ev in config.load_yaml("squads.yaml")["events"]:
        cache_key = f"wiki_{ev['year']}_{ev['team']}_{normalize_name(ev['event']).replace(' ', '_')}"
        html = _fetch_html(ev["url"], cache_key)
        df = parse_squad_section(html, ev["section"])
        df["team"], df["event"], df["year"] = ev["team"], ev["event"], ev["year"]
        frames.append(df)
        LOG.info("%s %s: %d players", ev["team"], ev["event"], len(df))
    out = pd.concat(frames, ignore_index=True)[
        ["player_norm", "player", "born", "team", "event", "year"]
    ]
    write_parquet(out, config.PROCESSED_DIR / "nt_flags.parquet")

    # Exhibit F (squad_lens): the Czech nt_core_event squad plus its peer
    # squads from the same Wikipedia page (config/squads.yaml::peer_squads).
    cfg = config.load_yaml("squads.yaml")
    core = next(e for e in cfg["events"] if e["event"] == cfg["nt_core_event"])
    cache_key = f"wiki_{core['year']}_{core['team']}_{normalize_name(core['event']).replace(' ', '_')}"
    core_html = _fetch_html(core["url"], cache_key)
    peers = [parse_squad_section(core_html, core["section"]).assign(country="CZE")]
    for p in cfg.get("peer_squads", []):
        try:
            peers.append(parse_squad_section(core_html, p["section"]).assign(country=p["country"]))
        except ValueError:
            # The cached page is read-only here (no refetch); a peer whose
            # squad section isn't on it yet (e.g. not qualified for
            # nt_core_event at cache time) is simply absent from the lens,
            # not an error.
            LOG.warning(
                "%s section %r not found on the %s page (cached, not refetched); skipping",
                p["country"], p["section"], core["event"],
            )
    ps = pd.concat(peers, ignore_index=True).assign(event=core["event"])
    write_parquet(
        ps[["country", "player_norm", "player", "born", "event"]],
        config.PROCESSED_DIR / "peer_squads.parquet",
    )


if __name__ == "__main__":
    main()
