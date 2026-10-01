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
sys.path.insert(0, str(Path(__file__).resolve().parent))
import takeaways as _take  # noqa: E402


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
n_recent = len((data.get("recent") or {}).get("leagues", {}))
home = "CZE"
home_ed = next((e for e in eds if e["code"] == home), None)
home_dec = ""
if home_ed and home_ed["decomposition"]["contrasts"]:
    parts = []
    for c in home_ed["decomposition"]["contrasts"]:
        top = max(c["channels"], key=lambda ch: ch["contribution"])
        label = {"u21_share": "youth minutes at home", "league_strength": "home-league strength", "export_age": "the age of the first move"}[top["name"]]
        peer = data["countries"].get(c["contrast"], {}).get("name", c["contrast"])
        def sg(x):
            return f"{x:+.2f}".replace("-", "\u2212")
        interval = f" (90 % bootstrap interval {sg(top['lo'])} to {sg(top['hi'])})" if top.get("lo") is not None else ""
        parts.append(f'against {peer} (a gap of {c["gap_total"]:.2f} per million) the largest segment goes with {label}, {sg(top["contribution"])}{interval}')
    home_dec = "; ".join(parts)

_rows = []
for _c, _v in sorted(lr.get("countries", {}).items(), key=lambda kv: kv[1].get("name", kv[0])):
    _d = _v.get("diagnostics")
    if not _d:
        continue
    _rows.append(f'<tr><td>{esc_html(_v.get("name", _c))}</td><td>{_d["rhat_max"]:.3f}</td><td>{_d["ess_bulk_min"]:,}</td>'
                 f'<td>{_d["ess_tail_min"]:,}</td><td>{_d["divergences"]}</td><td>{_d["stage"]}</td>'
                 f'<td>{"passes" if _d["pass"] else "fails: no dated steps"}</td></tr>'.replace(",", "\u2009"))
diag_table = ('<details class="fold ax-fold"><summary>convergence of every country\'s fit</summary><div class="tw"><table class="ax-table">'
              '<thead><tr><th>Country</th><th>max R-hat</th><th>min bulk ESS</th><th>min tail ESS</th><th>divergences</th><th>stage</th><th>rule</th></tr></thead>'
              '<tbody>' + "".join(_rows) + '</tbody></table></div>'
              '<p class="ax-note">Stage 1: target acceptance 0.95; stage 2: 0.99, used only for fits that failed stage 1. Protocol: design/nations-refit-protocol.md in the repository.</p></details>') if _rows else ""

HTML = f'''<!DOCTYPE html>
<html lang="en" data-home="{home}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Nations — Czech Football Atlas</title>
  <meta name="description" content="{len(eds)} national player pools measured the same way — youth minutes, export age, league strength, the national-team squad — with each nation's gap decomposed against its peers and every country's Big-5 presence since {S[0][:4] if S else '1995'}.">
  <link rel="canonical" href="https://football.bsandova.com/nations/">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="../style.css">
  <link rel="stylesheet" href="../modern.css">
  <script defer src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
  <script defer src="../nations.app.js"></script>
</head>
<body id="top" class="ax-page nx-page">
<nav class="topbar" aria-label="Navigation">
  <a class="topbar-brand" href="../">Czech Football <span>Atlas</span></a>
  <div class="topbar-links">
    <a href="../">Summary</a>
    <a href="../methodology/">Methodology</a>
    <a href="../players/">Players</a>
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
    <p class="ax-lead">Each edition — {names} — measures its pool the same way: how many players reach the strongest leagues per million, how many minutes the home league gives its own under-21s, when the first move abroad comes, how strong the home league is, and what the national-team squad is built from. Side by side, the table shows where the editions differ on the same definitions; the decomposition describes how each gap lines up with three measured channels; the long run dates when each country's presence in the Big-5 most probably changed level. The page is exploratory and descriptive, was not pre-registered and identifies no cause.</p>
    <p class="ax-note">Data: each edition's snapshot under data/snapshot/ (FBref tables fetched 14 September 2026) · code: src/nations_compare.py, site/build_nations.py · status: exploratory, not pre-registered</p>
  </header>

  <section class="nx-section nx-takeaways" id="take">
    <p class="ax-kicker">Findings</p>
    <div data-nx-takeaways>{_take.render((data.get("takeaways") or {}).get(home, []))}</div>
    <p class="ax-note">Each finding is generated from the numbers below at build time; all are descriptive, and the evidence and its limits follow in order.</p>
  </section>

  <section class="nx-section" id="side-by-side">
    <p class="ax-kicker">A · side by side</p>
    <h2 class="ax-statement">Six editions on the same pathway measures, last completed season.</h2>
    <div data-nx-table></div>
    <p class="ax-note">How to read it: each edition's own headline numbers, last completed season; the brightest value in a row marks the edition ranked first on that row.</p>
    <details class="fold ax-fold"><summary>what the rows mean</summary>
      <p class="ax-note">Per million counts players with a season in the nine strongest leagues. For a nation whose home league is one of them (England, Germany, Spain) that includes the home league — which is why the rank is against the nation's own peer set, not across editions. Under-21 minutes and regular starters are measured in the home league; the first move abroad is the median age at a player's first season in a headline league; the squad row is the share of the last full national-team squad playing in a top-9 league.</p>
    </details>
  </section>

  <section class="nx-section" id="why">
    <p class="ax-kicker">B · the gap to the peers, split over three measured channels (descriptive)</p>
    <h2 class="ax-statement">{("Czechia " + esc_html(home_dec) + ".") if home_dec else "Each edition splits its gap to its peers over three measured channels."}</h2>
    <div data-nx-decomp></div>
    <details class="fold ax-fold"><summary>how the decomposition works, and what it cannot say</summary>
      <p class="ax-note">Each edition's own decomposition: a ridge regression of players-per-million on youth share, home-league strength and the age of the first move across that edition's eight or nine peers, then a Oaxaca–Blinder-style accounting of the gap to each contrast (<a href="#ref-oaxaca_1973">{in_text(refs["oaxaca_1973"])}</a>; <a href="#ref-blinder_1973">{in_text(refs["blinder_1973"])}</a>). A channel's share is how much of the gap goes with that channel at the fitted coefficients; the channels can sum to more than the gap and the residual takes the rest. A positive league-strength segment can mean a weaker home league for the comparison country: in Czechia's fit the league-strength coefficient is negative. The split describes an association across few, correlated countries; it does not say what would happen if the youth share rose, which would need change over time within a country.</p>
    </details>
    <h3 class="nx-h3">Six seasons at home — the change the cross-section cannot see</h3>
    <div class="ax-chart" data-nx-recent></div>
    <p class="ax-note">How to read it: the share of each home league's minutes played by its own under-21s, every complete season the pipeline covers; the chips choose the countries (they also drive the long-run charts below).</p>
    <div class="ax-chart" data-nx-change></div>
    <p class="ax-note">How to read it: each country's change in that share against its change in Big-5 presence over the same seasons — the within-country picture, one point per country, {n_recent} countries and six seasons: a direction, not an estimate.</p>
    <h3 class="nx-h3">The cross-section behind it</h3>
    <div class="ax-chart" data-nx-scatter></div>
    <p class="ax-note">How to read it: one point per country ({len(data.get("panel", []))}), last completed season; pick the measure on the x-axis. The dashed line is a plain fit for the direction only; the three measures move together across countries, so the line describes an association.</p>
  </section>

  <section class="nx-section" id="long-run">
    <p class="ax-kicker">C · the long run, {span}</p>
    <h2 class="ax-statement">Who fell, who rose, and when — every country's presence in the Big-5, with two dated steps each.</h2>
    <div class="ax-chart" data-nx-long></div>
    <p class="ax-note">How to read it: players with {lr.get("min_minutes", 450)}+ minutes in a Big-5 league that season, per million; a diamond is a dated step (hover for size and certainty); a dashed rule is a documented reform — a date, not a cause. Every fit was checked against a convergence rule written down on 30 September 2026, before the refit (four chains, 2000 tuning steps and 2000 draws, a stricter step size only where needed; max R-hat ≤ 1.01, bulk and tail effective sample size ≥ 400, no divergent transitions); a country whose fit fails has no dated steps here. The diagnostics are in the table below.</p>
    {diag_table}
    <details class="fold ax-fold"><summary>how we know, and the two reform dates</summary>
      <p class="ax-note">FBref's season tables for the Premier League, Serie A, La Liga, Bundesliga and Ligue 1, from the first season all five are covered. Each country gets the report's two-step change-point model (<a href="#ref-adams_mackay_2007">{in_text(refs["adams_mackay_2007"])}</a>, in a batch, two-break setting). For a Big-5 nation the count includes its own league, so its series is mostly about how international that league became. Reform markers: {reform_lines}. A marker cannot tell whether a series moved because of a reform; it shows the timing, beside countries without such a reform.</p>
    </details>
    <div data-nx-analogies></div>
    <details class="fold ax-fold"><summary>every country's steps as a table</summary><div data-nx-breaks></div>
      <p class="ax-note">"Shape vs CZE" is the correlation of the per-million series with Czechia's — the countries whose long run is shaped most like Czechia's, whatever their level. Each step comes with its posterior and interval in the table; a step whose interval includes no change is not distinguishable from none.</p></details>
    <h3 class="nx-h3">When a country's players arrive, and how young</h3>
    <div class="ax-chart" data-nx-debut></div>
    <p class="ax-note">How to read it: the same countries as above; age at a player's first Big-5 season of {lr.get("min_minutes", 450)}+ minutes (three-season median, because a small nation sends two or three a year), or the under-23 share of the nation's Big-5 minutes, or the count of first seasons; the chart shows whether a rise came with younger arrivals and how the age of Czechia's arrivals moved around its fall.</p>
    <h3 class="nx-h3">Youth minutes in the Big-5 leagues themselves</h3>
    <div class="ax-chart" data-nx-youth></div>
    <p class="ax-note">How to read it: the share of each Big-5 league's minutes played by its own under-21s (age at 1 July), season by season — the one youth series the data carries back this far.</p>
  </section>

  <section class="nx-section" id="limits">
    <p class="ax-kicker">D · what this can and cannot say</p>
    <ul class="nx-limits">
      <li><strong>Can:</strong> put {len(eds)} nations on one ruler; describe how a gap lines up with measured channels; date when a country's Big-5 presence changed level; show whether a reform preceded a change.</li>
      <li><strong>Cannot:</strong> attribute a change to a reform (no counterfactual, no randomisation); separate channels that move together; see youth minutes in the small leagues before FBref covers them.</li>
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
