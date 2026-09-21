"""The cross-nation page: <site>/nations/index.html, reading charts/nations.json.

Built once, into the root site (the page compares editions; it is not an
edition). The shell carries the prose -- what the page can and cannot say
about causes -- and the Harvard references it cites from config/refs.yaml
via src.references, so no citation is hand-formatted here.

usage: build_nations.py <site dir>    (the root site dir holding index.html)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.references import format_harvard, in_text, load_refs, refs_by_key  # noqa: E402


def esc_html(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


D = Path(sys.argv[1]).resolve()
src = ROOT / "outputs" / "nations" / "nations.json"
if not src.exists():
    sys.exit(f"no {src} -- run `uv run python -m src.nations_compare` first")
(D / "charts").mkdir(parents=True, exist_ok=True)
(D / "charts" / "nations.json").write_bytes(src.read_bytes())
data = json.loads(src.read_text(encoding="utf-8"))
eds = data["editions"]
refs = refs_by_key(load_refs())
cited = ["oaxaca_1973", "blinder_1973", "adams_mackay_2007"] + [r["ref"] for r in data.get("reforms", [])]
cited = [k for k in dict.fromkeys(cited) if k in refs]
ref_list = "\n".join(f'      <li id="ref-{k}">{format_harvard(refs[k])}</li>' for k in sorted(cited, key=lambda k: refs[k]["authors"][0].lower()))
reform_lines = "; ".join(
    f'{data["countries"].get(r["country"], {}).get("name", r["country"])} {r["season"][2:4]}/{r["season"][7:9]}, {r["label"]} '
    f'<a href="#ref-{r["ref"]}">{in_text(refs[r["ref"]])}</a>'
    for r in data.get("reforms", []) if r["ref"] in refs)
names = ", ".join(e["name"] for e in eds[:-1]) + (" and " + eds[-1]["name"] if len(eds) > 1 else "")
lr = data.get("long_run") or {}
S = lr.get("seasons") or []
span = f"{S[0][2:4]}/{S[0][7:9]}–{S[-1][2:4]}/{S[-1][7:9]}" if S else ""
n_countries = len(lr.get("countries", {}))
home = "CZE"
home_ed = next((e for e in eds if e["code"] == home), None)
home_dec = ""
if home_ed and home_ed["decomposition"]["contrasts"]:
    parts = []
    for c in home_ed["decomposition"]["contrasts"]:
        top = max(c["channels"], key=lambda ch: ch["contribution"])
        label = {"u21_share": "youth minutes at home", "league_strength": "home-league strength", "export_age": "the age of the first move"}[top["name"]]
        peer = data["countries"].get(c["contrast"], {}).get("name", c["contrast"])
        parts.append(f'against {peer}, {label} carries {round(top["share"] * 100)} % of a {abs(c["gap_total"]):.1f}-per-million gap')
    home_dec = "; ".join(parts)

HTML = f'''<!DOCTYPE html>
<html lang="en" data-home="{home}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Nations — Czech Football Atlas</title>
  <meta name="description" content="{len(eds)} national player pools measured the same way — youth minutes, export age, league strength, the national-team squad — with each nation's gap decomposed against its peers and every country's Big-5 presence since {S[0][:4] if S else '1995'}.">
  <link rel="canonical" href="https://football.datasimply.eu/nations/">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=JetBrains+Mono:wght@400;500;700&family=Fraunces:ital,opsz,wght@0,9..144,300..700;1,9..144,300..700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="../style.css">
  <link rel="stylesheet" href="../modern.css">
  <script defer src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
  <script defer src="../nations.app.js"></script>
</head>
<body id="top" class="ax-page nx-page">
<nav class="topbar" aria-label="Navigation">
  <a class="topbar-brand" href="../">Czech Football <span>Atlas</span></a>
  <div class="topbar-links">
    <a href="../#summary">Summary</a>
    <a href="../#pathways">Pathways</a>
    <a href="../#q9">Cards</a>
    <a href="../atlas/">Players</a>
    <a href="./" aria-current="page">Nations</a>
  </div>
  <div class="atlas-switch" aria-label="Atlas">
    {" · ".join(f'<a href="{"/" if e["nation"] == "cze" else "/" + e["nation"] + "/"}">{e["code"]}</a>' for e in eds)}
  </div>
</nav>
<main class="ax container" data-nations-app>
  <header class="ax-head">
    <p class="ax-kicker">Nations · {len(eds)} editions · {n_countries} countries in the long run · {span}</p>
    <h1 class="ax-title">The same five questions, asked of {len(eds)} nations.</h1>
    <p class="ax-lead">Each edition — {names} — measures its pool the same way: how many players reach the strongest leagues per million, how many minutes the home league gives its own under-21s, when the first move abroad comes, how strong the home league is, and what the national-team squad is built from. Side by side, the numbers say where a nation is out of line. The decomposition says which mechanism carries most of a gap. The long run says when each country's presence in the Big-5 changed level. None of it proves a cause; the page says where that line is.</p>
  </header>

  <section class="nx-section" id="side-by-side">
    <p class="ax-kicker">A · side by side</p>
    <h2 class="ax-statement">Where Czechia is out of line, in the numbers every edition shares.</h2>
    <div data-nx-table></div>
    <p class="ax-note">How to read it: each edition's own headline numbers, last completed season; the brightest value in a row is the best of the editions.</p>
    <details class="fold ax-fold"><summary>what the rows mean</summary>
      <p class="ax-note">Per million counts players with a season in the nine strongest leagues. For a nation whose home league is one of them (England, Germany, Spain) that includes the home league — which is why the rank is against the nation's own peer set, not across editions. Under-21 minutes and regular starters are measured in the home league; the first move abroad is the median age at a player's first season in a headline league; the squad row is the share of the last full national-team squad playing in a top-9 league.</p>
    </details>
  </section>

  <section class="nx-section" id="why">
    <p class="ax-kicker">B · why a nation lags — youth, or something else</p>
    <h2 class="ax-statement">{("Czechia " + esc_html(home_dec) + ".") if home_dec else "Each edition decomposes its gap against its peers into three mechanisms."}</h2>
    <div data-nx-decomp></div>
    <details class="fold ax-fold"><summary>how the decomposition works, and what it cannot say</summary>
      <p class="ax-note">Each edition's own decomposition: a ridge regression of players-per-million on youth share, home-league strength and the age of the first move across that edition's eight or nine peers, then a Oaxaca–Blinder-style accounting of the gap to each contrast (<a href="#ref-oaxaca_1973">{in_text(refs["oaxaca_1973"])}</a>; <a href="#ref-blinder_1973">{in_text(refs["blinder_1973"])}</a>). A channel's share is how much of the gap that mechanism accounts for at the fitted coefficients; the channels can sum to more than the gap and the residual takes the rest. It says which measured mechanism carries a gap. It does not say what would happen if the youth share rose — that needs change over time within a country.</p>
    </details>
    <h3 class="nx-h3">The cross-section behind it</h3>
    <div class="ax-chart" data-nx-scatter></div>
    <p class="ax-note">How to read it: one point per country ({len(data.get("panel", []))}), last completed season; pick the mechanism on the x-axis. The dashed line is a plain fit for the direction only — the three mechanisms move together, so a stronger league keeps more of its young players and exports them later.</p>
  </section>

  <section class="nx-section" id="long-run">
    <p class="ax-kicker">C · the long run, {span}</p>
    <h2 class="ax-statement">Who fell, who rose, and when — every country's presence in the Big-5, with two dated steps each.</h2>
    <div class="ax-chart" data-nx-long></div>
    <p class="ax-note">How to read it: players with {lr.get("min_minutes", 450)}+ minutes in a Big-5 league that season, per million; a diamond is a dated step (hover for size and certainty); a dashed rule is a documented reform — a date, not a cause.</p>
    <details class="fold ax-fold"><summary>how we know, and the two reform dates</summary>
      <p class="ax-note">FBref's season tables for the Premier League, Serie A, La Liga, Bundesliga and Ligue 1, from the first season all five are covered. Each country gets the report's two-step change-point model (<a href="#ref-adams_mackay_2007">{in_text(refs["adams_mackay_2007"])}</a>, in a batch, two-break setting). For a Big-5 nation the count includes its own league, so its series is mostly about how international that league became. Reform markers: {reform_lines}. Whether a series moved <em>because</em> of a reform is not something a marker can tell; the honest reading is the timing, against countries that did nothing.</p>
    </details>
    <details class="fold ax-fold"><summary>every country's steps as a table</summary><div data-nx-breaks></div>
      <p class="ax-note">"Shape vs CZE" is the correlation of the per-million series with Czechia's — the countries whose long run looks most like Czechia's are the analogies worth reading, whatever their level. A second step that is a rise is a recovery after a plateau; Czechia's second step is the one fall among the small nations.</p></details>
    <h3 class="nx-h3">When a country's players arrive, and how young</h3>
    <div class="ax-chart" data-nx-debut></div>
    <p class="ax-note">How to read it: the same countries as above; age at a player's first Big-5 season of {lr.get("min_minutes", 450)}+ minutes (three-season median, because a small nation sends two or three a year), or the under-23 share of the nation's Big-5 minutes, or the count of first seasons. Did a recovery come with younger arrivals? Did Czechia's arrivals get older around its fall?</p>
    <h3 class="nx-h3">Youth minutes in the Big-5 leagues themselves</h3>
    <div class="ax-chart" data-nx-youth></div>
    <p class="ax-note">How to read it: the share of each Big-5 league's minutes played by its own under-21s (age at 1 July), season by season — the one youth series the data carries back this far. Germany after 2001/02 is the case to read first.</p>
  </section>

  <section class="nx-section" id="limits">
    <p class="ax-kicker">D · what this can and cannot say</p>
    <ul class="nx-limits">
      <li><strong>Can:</strong> put {len(eds)} nations on one ruler; say which measured mechanism carries most of a gap; date when a country's Big-5 presence changed level; show whether a reform preceded a change.</li>
      <li><strong>Cannot:</strong> attribute a change to a reform (no counterfactual, no randomisation); separate mechanisms that move together; see youth minutes in the small leagues before FBref covers them.</li>
      <li><strong>Next:</strong> the same decomposition within a country over time, and a synthetic-control read of the two dated reforms against the countries that did nothing — both need more seasons than the small leagues have yet.</li>
    </ul>
  </section>

  <footer class="ax-foot">
    <h3 class="nx-h3">References</h3>
    <ol class="nx-refs">
{ref_list}
    </ol>
  </footer>
</main>
</body>
</html>
'''
out = D / "nations" / "index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(HTML, encoding="utf-8")
print(f"built {out} ({len(eds)} editions, {n_countries} countries, {len(cited)} references)")
