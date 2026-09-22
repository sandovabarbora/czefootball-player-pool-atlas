"""The player atlas page: <site>/atlas/index.html + the careers data it reads.

Standalone like enrich_index.py (no src.* imports; NATION from the env,
config/nations/<NATION>.yaml read directly) so `site/build.sh` can run it
for any nation from any cwd. It writes the page's shell -- top bar in the
report's own markup, the controls, an empty list and detail pane -- which
docs/atlas.app.js fills from charts/careers.json; and it decorates that
JSON (src/careers_export.py) with each player's portrait from
site/players.<nation>.json, preferring the cut-out when site/cutouts.py made
one, so the page needs no second manifest.

usage: build_atlas.py <site dir>          (the dir that holds index.html)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

D = Path(sys.argv[1]).resolve()
NATION = os.environ.get("NATION", "cze").lower()
HOME_CODE = NATION.upper()
ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
nation_yaml = ROOT / "config" / "nations" / f"{NATION}.yaml"
if nation_yaml.exists():
    import yaml
    ADJ = yaml.safe_load(nation_yaml.read_text(encoding="utf-8"))["adjective"]
else:
    ADJ = "Czech"
SITE = "https://football.bsandova.com/"
ATLAS_ROOTS = {"cze": "/", "eng": "/eng/", "ger": "/ger/", "den": "/den/", "nor": "/nor/", "esp": "/esp/"}
# only editions that are actually built are offered in the switch (a nation
# whose docs/<nation>/index.html does not exist yet would be a dead link)
_DOCS_ROOT = Path(__file__).resolve().parents[1] / "docs"
ATLAS_ROOTS = {c: r for c, r in ATLAS_ROOTS.items() if c == NATION or (_DOCS_ROOT / r.strip("/") / "index.html").exists()}

# ---------------------------------------------------------------- portraits into the careers data
careers_path = D / "charts" / "careers.json"
if not careers_path.exists():
    sys.exit(f"no {careers_path} -- run `uv run python -m src.careers_export` first")
players_path = Path(__file__).with_name(f"players.{NATION}.json")
manifest = json.load(open(players_path, encoding="utf-8")) if players_path.exists() else {}
by_key = {v["player_key"]: v for v in manifest.values()}
data = json.loads(careers_path.read_text(encoding="utf-8"))
n_photo = 0
for p in data["players"]:
    m = by_key.get(p["key"])
    p.pop("photo", None)
    p.pop("cut", None)
    if not m:
        continue
    img = m["image"]
    # cut-outs live next to the portrait in docs/img/players/, built once
    # by site/cutouts.py for the published site (the source of truth for
    # every site dir, temp builds included)
    cut = img.replace(".jpg", "-cut.png")
    p["photo"] = img
    if (DOCS / cut).exists():
        p["cut"] = cut
    n_photo += 1
careers_path.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")

# ---------------------------------------------------------------- the page
NAV = [("../#summary", "Summary"), ("../#pathways", "Pathways"), ("../#q9", "Cards"), ("../#methodology", "Methodology")]
links = "\n".join(f'    <a href="{href}">{label}</a>' for href, label in NAV)
atlas_switch = " · ".join(
    f'<span aria-current="page">{code.upper()}</span>' if code == NATION else f'<a href="{root}atlas/">{code.upper()}</a>'
    for code, root in ATLAS_ROOTS.items()
)
n = len(data["players"])
seasons = data["seasons_covered"]
span = f"{seasons[0][2:4]}/{seasons[0][7:9]}–{seasons[-1][2:4]}/{seasons[-1][7:9]}"
metrics = data.get("metrics_season") or seasons[-1]
metrics_short = f"{metrics[2:4]}/{metrics[7:9]}"
page_url = SITE + ("" if NATION == "cze" else f"{NATION}/") + "atlas/"
# the Big-5 history (charts/eras.json, charts/careers_history.json) exists
# for a nation once src.fetch_big5_history and src.careers_export ran
eras_path = D / "charts" / "eras.json"
has_eras = eras_path.exists() and (D / "charts" / "careers_history.json").exists()
if has_eras:
    eras = json.loads(eras_path.read_text(encoding="utf-8"))["seasons"]
    first_era = f"{eras[0]['season'][2:4]}/{eras[0]['season'][7:9]}"
    n_past = len(json.loads((D / "charts" / "careers_history.json").read_text(encoding="utf-8"))["players"])
    eras_kicker = f" · the Big-5 since {first_era}"
    eras_lead = f" A second view follows the nation in the five biggest leagues season by season since {first_era}, and {n_past} past players can be pulled into the list."
    tabs = ('<div class="ax-tabs" role="tablist" data-ax-tabs>'
            '<button type="button" role="tab" class="ax-tab" data-ax-view="players" aria-selected="true">Players</button>'
            f'<button type="button" role="tab" class="ax-tab" data-ax-view="eras" aria-selected="false">The nation in the Big-5, {first_era}–</button>'
            '<button type="button" role="tab" class="ax-tab" data-ax-view="gen" aria-selected="false">Generations</button></div>')
    past_control = f'<label class="pool-control ax-check"><input type="checkbox" data-ax-past> include past players ({n_past}, Big-5 since {first_era})</label>'
else:
    eras_kicker = eras_lead = tabs = past_control = ""

HTML = f'''<!DOCTYPE html>
<html lang="en" data-home="{HOME_CODE}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Player atlas — {ADJ} Football Atlas</title>
  <meta name="description" content="Every player in the {ADJ} pool, season by season: minutes by league rung, goals and assists per 90 league-adjusted, national-team call-ups; compare up to three.">
  <link rel="canonical" href="{page_url}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=JetBrains+Mono:wght@400;500;700&family=Fraunces:ital,opsz,wght@0,9..144,300..700;1,9..144,300..700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="../style.css">
  <link rel="stylesheet" href="../modern.css">
  <script defer src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
  <script defer src="../atlas.app.js"></script>
</head>
<body id="top" class="ax-page">
<nav class="topbar" aria-label="Navigation">
  <a class="topbar-brand" href="../">{ADJ} Football <span>Atlas</span></a>
  <div class="topbar-links">
{links}
    <a href="./" aria-current="page">Players</a>
    <a href="/nations/">Nations</a>
  </div>
  <div class="atlas-switch" aria-label="Atlas">
    {atlas_switch}
  </div>
</nav>
<main class="ax container" data-atlas-app data-home-name="{ADJ}">
  <header class="ax-head">
    <p class="ax-kicker">Player atlas · <span data-ax-n>{n}</span> players · <span data-ax-span>{span}</span>{eras_kicker}</p>
    <h1 class="ax-title">Every player in the pool, season by season.</h1>
    <p class="ax-lead">The <a href="../">report</a> says what the pool does. This is where you check any one player in it: his seasons in the covered leagues — minutes by the rung of the league, goals and assists per 90 adjusted for that league, national-team call-ups — and up to three players on the same axes.{eras_lead}</p>
    {tabs}
  </header>
  <section class="ax-eras" data-ax-view-eras hidden aria-label="The nation in the Big-5"></section>
  <section class="ax-eras" data-ax-view-gen hidden aria-label="Generations"></section>
  <div class="ax-body" data-ax-view-players>
    <aside class="ax-side" aria-label="Players">
      <div class="ax-controls">
        <label class="pool-control pool-control-search">Search <input type="search" data-ax-search autocomplete="off" placeholder="name, club or league"></label>
        <label class="pool-control">Position <select data-ax-pos><option value="">all</option><option value="FW">forwards</option><option value="MF">midfielders</option><option value="DF">defenders</option><option value="GK">goalkeepers</option></select></label>
        <label class="pool-control">League {metrics_short} <select data-ax-tier><option value="">all</option><option value="domestic">home league</option><option value="stepping_stone">stepping stone</option><option value="top9">top-9 league</option><option value="other">other league</option></select></label>
        <label class="pool-control">Sort by <select data-ax-sort><option value="name">name</option><option value="min">minutes {metrics_short}</option><option value="rank">rank in position group</option><option value="ga">G+A / 90 adj.</option><option value="age">age</option><option value="trend">change in minutes this season</option><option value="climb">rungs climbed since {seasons[0][2:4]}/{seasons[0][7:9]}</option><option value="calls">national-team call-ups</option></select></label>
        <label class="pool-control ax-check"><input type="checkbox" data-ax-nt> national team only</label>
        {past_control}
      </div>
      <p class="ax-browse-label">or start from a question</p>
      <div class="chart-row ax-browse" data-ax-browse></div>
      <p class="ax-count"><span data-ax-count>{n} of {n}</span> · click a row to open, up to three at once</p>
      <ol class="ax-list" data-ax-list aria-label="players"></ol>
      <p class="chart-empty" data-ax-empty hidden>no player matches</p>
    </aside>
    <section class="ax-detail" data-ax-detail data-n="0" aria-live="polite"></section>
  </div>
  <footer class="ax-foot">
    <p>Season lines are FBref standard tables for the leagues the pipeline covers (nine headline leagues, the home league, its peers and the stepping-stone leagues), {span}; a season elsewhere is absent, not zero. G+A / 90 adj. is non-penalty goals plus assists per 90 minutes, times the league multiplier from the report's <a href="../#league-strength">league-strength model</a>; it is the raw rate, not the shrunk one the report ranks on. National-team call-ups come from the squad lists the report uses. Portraits: Chance Liga official portraits, Wikimedia Commons where none exists — credits on the <a href="../#photo-credits">report page</a>.</p>
  </footer>
</main>
</body>
</html>
'''
out = D / "atlas" / "index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(HTML, encoding="utf-8")
print(f"built {out} ({n} players, {n_photo} with a portrait, seasons {span})")
