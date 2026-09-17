"""Report strings: English defaults here, Czech in config/i18n/cs.yaml.

The template calls `t(key, **params)`; the render builders call `term(s)`
for English labels that come from data or config (cluster labels, tier
names, country names, showcase reasons ...). Both fail loudly for a Czech
render when an entry is missing, so a new string in the template or a new
label in the config cannot silently ship untranslated.

Two sections in the yaml:
  strings: key -> Czech text (same `{placeholders}` as the English entry)
  terms:   English label -> Czech label (exact match)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml
from markupsafe import Markup, escape

from src import config

ROOT_DIR = Path(__file__).resolve().parent.parent
CS_PATH = ROOT_DIR / "config" / "i18n" / "cs.yaml"
LANGS = ("en", "cs")
log = logging.getLogger(__name__)

# Names auto-injected into every t()/raw() call from config.nation() (Task
# 14b) -- a nation word or number that appears in the report's copy without
# the template or a render builder having to name it explicitly. `nation`,
# `adj`, `Adj`, `code`, `home_league` are the English forms; every `cs_*`
# name comes from the home nation's `cs:` block (config/nations/<NATION>.yaml)
# -- one entry per key there, plus a capitalised variant (`cs_Adj_m`, ...)
# for sentence-initial use. Allowed anywhere by `check_placeholders` (a
# string can use or drop any of these regardless of what the other language's
# entry does) since they are not part of the translator's own contract.
_AUTO_NAMES = {"nation", "adj", "Adj", "code", "home_league", "leagues_note"}

# Showcase-reason patterns (from src.historical_analogs.showcase_ids, with the
# position code replaced by "{pos}") whose display text swaps the raw jargon
# for a plain metric label -- see Translator.reason (Task 22 item 9).
_REASON_DISPLAY = {
    "highest quality-adjusted npG+A per 90 among {pos}": "ch3.reason.top_metric",
}


def _capitalize(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def _auto_params() -> dict[str, str]:
    """Nation-word placeholders available in every string, from `config.nation()`."""
    n = config.nation()
    out = {
        "nation": n["name"],
        "adj": n["adjective"],
        "Adj": n["adjective"],  # English nationality adjectives are always capitalised
        "code": n["code"],
        "home_league": n["home_league"],
        "leagues_note": n.get("leagues_note", ""),
    }
    for key, val in n.get("cs", {}).items():
        out[f"cs_{key}"] = val
        out[f"cs_{_capitalize(key)}"] = _capitalize(val)
    return out

# fmt: off
EN: dict[str, str] = {
    # ---- head / chrome
    "meta.title": "{adj} football · Player pool atlas",
    "meta.description": "Structural benchmark of the {adj} professional football player pool against {n} peer countries: per-capita density in Europe's strongest leagues, cohort gaps, PCA atlases by position group, pathways abroad. Descriptive, reproducible, public data only.",
    "skip": "Skip to content",
    "toc.aria": "Report contents",
    "toc.hide": "Hide contents",
    "toc.show": "Show contents",
    "toc.heading": "Contents",
    "toc.q1": "Is the pool thin?",
    "toc.q2": "Where is it thin?",
    "toc.q3": "Youth minutes at home",
    "toc.q4": "Where they go",
    "toc.q4b": "Leaving later",
    "toc.q5": "How they fare",
    "toc.q6": "World Cup squad",
    "toc.q7": "When the train left",
    "toc.q8": "{a} and {b}",
    "toc.q8b": "Goalkeepers",
    "toc.q8c": "What the gap is made of",
    "toc.q9": "Who the players are",
    "toc.explore": "Explore the data",
    "toc.benchmark": "Benchmark vs peer countries",
    "toc.clusters": "Cluster archetypes",
    "toc.trajectories": "Trajectories",
    "toc.pathways": "Why does the train leave?",
    "toc.analogs": "Historical analogs",
    "toc.players": "Player index",
    "toc.methodology": "How it is built, validated and where it stops",
    "toc.multipliers": "League multipliers",
    "toc.strength": "League strength",
    "toc.compare": "Three models, one task, five seasons",
    "toc.series": "Dating the break and one forecast",
    "toc.panel": "Cross-country youth-minutes panel",
    "toc.gap": "What the gap is made of",
    "toc.shrinkage": "Bayesian shrinkage",
    "toc.pca": "PCA loadings",
    "toc.sensitivity": "Sensitivity analysis",
    "toc.data_quality": "Data-quality log",
    "toc.limitations": "Limitations",
    "toc.validation": "Validation & robustness",
    "toc.reproducibility": "Reproducibility",
    "toc.related_methods": "Related methods",
    "toc.references": "References",
    "toc.how_built": "How this was built",
    "toc.short.benchmark": "Benchmark",
    "toc.short.multipliers": "Multipliers",
    "toc.short.strength": "Strength",
    "toc.short.compare": "Model comparison",
    "toc.short.series": "Break & forecast",
    "toc.short.panel": "Youth panel",
    "toc.short.gap": "Gap decomposition",
    "toc.short.export_age": "Age at export",
    "toc.short.shrinkage": "Shrinkage",
    "toc.short.pca": "PCA",
    "toc.short.sensitivity": "Sensitivity",
    "toc.short.limitations": "Limitations",
    "toc.short.related_methods": "Related methods",
    "toc.short.references": "References",

    # ---- masthead (first screen: same pitch as the hero kicker/lead below it)
    "mast.kicker": "National player-pool intelligence &middot; public data &middot; reproducible",
    "mast.title": "Atlas of the <em>player pool</em>",
    "mast.subtitle": "A federation-grade view of one country's professional pool: how it compares with peers per head, where the pathway abroad leaks, how the tournament squad is sourced, and each player's season against a European corpus.",
    "mast.pool": "Pool",
    "mast.pool_value": "<strong>{n}</strong> players",
    "mast.with_metrics": "With {season} metrics",
    "mast.nt": "NT call-up {nt_years}",
    "mast.facts": "{n_leagues} leagues · {n_seasons} seasons · {n_tests} tests · every number computed from the run · rulings logged · no predictions, no selection recommendations",

    # ---- hero
    "hero.stamp.report": "Report",
    "hero.stamp.atlas": "Atlas · {season}",
    "hero.stamp.edition": "first edition · MIT",
    "hero.stamp.aria": "Document identification",
    "hero.kicker": "National player-pool intelligence · public data · reproducible",
    "hero.h2": "How deep is a national player pool — and why",
    "hero.unit": "players in Europe's {topn} strongest leagues per million inhabitants, {season} rosters",
    "hero.lead": "A federation-grade view of one country's professional pool: how it compares with peers per head, where the pathway abroad leaks, how the tournament squad is sourced, and each player's season against a European corpus.",
    "hero.sublead.gap": "The largest cohort gap is in <strong>{group} aged {cohort}</strong>: {cze_n} {adj} player{s} in the top-{topn} leagues against a peer median of {peer}.",
    "hero.sublead.export": "A recent {adj} export first reached a top-{topn} roster at a median age of {cze}; one from {b} at {den}.",
    "hero.sublead.close": "Built from FBref, Wikipedia and Wikidata. {nation} is the worked example; the pipeline takes a nationality code and a peer set. Football people recognise these numbers player by player; there is no place where they are aggregated.",
    "hero.footnote": "* {n} players with FBref nationality {code} and ≥ {min} minutes on {season} rosters of the UEFA top-{topn} leagues ÷ {pop} M inhabitants (Eurostat 2024); peer countries computed the same way. <a href=\"#methodology\">Methodology</a>.",

    # ---- quickread (Task 25a): the 60-second opener, four tiles between the
    # hero and the slides — each tile's figure is typed in the template, its
    # line comes from here; the closing note points at the eleven slides below
    "quickread.1": "per million inhabitants — {rank} of {n} peer countries",
    "quickread.2": "largest cohort gap: {group} aged {cohort} vs peer median {peer}",
    "quickread.3": "of the {event} squad in the top-{topn} leagues (peer best {best_pct} %)",
    "quickread.4": "the season Big-5 presence broke ({break_prob} posterior)",
    "quickread.note": "Everything below is the evidence for those four numbers, in eleven questions.",

    # ---- slides (Task 13b): nine questions between the hero and "for a
    # federation", each q (h2) / a (one sentence, headline number in
    # <strong>) / proof (one exhibit, markup in the template) / how (mono
    # sourcing line, shared "How we know" label below)
    "slide.how_label": "How we know",
    "slide.1.q": "Is the {adj} pool thin?",
    "slide.1.aq": "In numbers: distinct players with ≥ {min} minutes on {season} rosters of the {topn} strongest leagues, per million inhabitants, against {n} peers.",
    "slide.1.a": "{nation} ranks <strong>{rank} of {n}</strong> countries at {pm} per million; {top} leads at {top_pm}.",
    "slide.1.how": "Distinct players with ≥ {min} minutes on {season} rosters of the {topn} strongest leagues ÷ population (Eurostat 2024); every country counted the same way.",
    "slide.2.q": "Where exactly is it thin?",
    "slide.2.aq": "In numbers: {adj} player count against the peer-country median, by age cohort and position group, ≥ {min} minutes, {season} season.",
    "slide.2.a": "The largest cohort gap: <strong>{group} aged {cohort}</strong>, {cze} {adj} players vs a peer median of {peer}.",
    "slide.2.how": "Age at season start; cohorts U22 / 23–25 / 26–29 / 30+; ≥ {min} minutes.",
    "slide.3.q": "Do young players get minutes at home?",
    "slide.3.aq": "In numbers: share of domestic-league minutes played by players aged ≤ 21 at season start, {season}, by country's top flight.",
    "slide.3.a": "U21 share of domestic-league minutes <strong>{cze_pct} %</strong> vs {best_name} {best_pct} % (best peer).",
    "slide.3.how": "Share of all league minutes played by players aged ≤ 21 at season start, {season}, per domestic top flight.",
    "slide.3.panel": " Across the {n_countries} countries (country averages over both seasons), 10 points more U21 share go with {beta} more top-{topn} players per million ({lo}–{hi}).",
    "slide.3.panel.summary": "Across countries",
    "slide.3.panel.alt": "Scatter of U21 share of domestic-league minutes against top-9 players per million, {n_countries} countries, two seasons each connected by a line, {nation} highlighted, with the fitted line and its 90 % band.",
    "slide.4.q": "Where do {adj} players go when they leave?",
    "slide.4.aq": "In numbers: destination-league tier of every {adj}-eligible player's {season} row, split into top-{topn}, sideways and other abroad moves.",
    "slide.4.a": "<strong>{abroad} of {total}</strong> play abroad; {top9_pct} % in the {topn} strongest leagues, {sideways_pct} % moved sideways (to a league no stronger than the {adj} one).",
    "slide.4.how": "Destination league of every {adj}-eligible player's {season} row; sideways = destination multiplier ≤ {adj} league multiplier (<a href=\"#league-strength\">league strength: two estimates, § Methodology</a>).{home_note}",
    "slide.4b.q": "Does leaving later cost anything?",
    "slide.4b.zero_note": ", an interval that includes zero: no detectable difference at n = {n}",
    "slide.4b.aq": "In numbers: mean league-adjusted goals + assists per 90 over the first two top-{topn} seasons, as a function of age at the first one, given origin-league strength and position, {n} peer-nationality exports.",
    "slide.4b.a": "Players who arrive in the top-{topn} at 21 produce {y21} ({lo}–{hi}) league-adjusted G+A per 90 over their first two seasons; those arriving at 24, {y24} ({lo24}–{hi24}) — a difference of <strong>{diff}</strong> ({dlo}–{dhi}){zero_note}. {Adj} exports arrive at a median age of {age_home}.",
    "slide.4b.how": "Age curve ({branch}) on league-adjusted production, given origin-league strength (<a href=\"#league-strength\">§ Methodology</a>), position and a country effect, {n} peer-nationality exports {cite}; better players tend to leave earlier, so the curve mixes selection with development and this report does not separate them.",
    "slide.4b.alt": "Line chart: the fitted age-at-export curve with its 90 % band, {adj} exports as points against every other peer export, and a rug of every export's age along the axis.",
    "slide.5.q": "How do they fare there?",
    "slide.5.aq": "In numbers: median share of a club's {season} minutes kept by players abroad, by country of origin.",
    "slide.5.a": "{Adj} exports keep <strong>{cze} %</strong> of their club's minutes ({rank} of {n}).",
    "slide.5.a2": "A {home_league} season converts to {m_l} of a Premier League one by the transfer-graph model ({lo}–{hi}), against {uefa} by UEFA coefficient.",
    "slide.5.how": "Median share of club minutes for players abroad, per country of origin (<a href=\"#league-strength\">league strength: two estimates, § Methodology</a>).{home_note}",
    "slide.5.alt": "Dot plot: each country's median share of club minutes for players abroad, with a thin line spanning the other countries' values; {nation} highlighted.",
    "slide.5.table_summary": "Country-by-country figures",
    "ch2.headline_note": "Not informative for this nation: {home_league} and every peer's own league are themselves top-{topn} leagues, so the domestic / top-{topn} split has no content here; the exhibit is kept for comparability with other nations.",
    "slide.home_note": " {home_league} is itself one of Europe's top-{topn} leagues; here 'abroad' means the other {topn_minus_1}.",
    "slide.6.q": "What is the World Cup squad built from?",
    "slide.6.aq": "In numbers: league tier of every {event} squad member's most-minutes {season} row, matched by name and birth year, per country.",
    "slide.6.a": "<strong>{cze_pct} %</strong> of the {event} squad plays in the {topn} strongest leagues; {best_name} {best_pct} %.",
    "slide.6.how": "Wikipedia squad lists matched to {season} league rows; tier = league of the most-minutes row.",
    "slide.7.q": "When did the train leave?",
    "slide.7.aq": "In numbers: {adj} players with ≥ {min} minutes in the Big-5 leagues each season since {history_start}, with one dated change point.",
    "slide.7.a": "{Adj} players with ≥ {min} minutes in the Big-5 leagues peaked at <strong>{peak_n}</strong> in {peak_season}, fell to {low_n} in {low_season}, {last_n} in {last_season}; the break is dated to {break_season} ({break_prob} posterior), a level change of ×{delta} ({lo}–{hi}).",
    "slide.7.how": "FBref Big-5 player tables {first_season} → {last_season}; peers on the same rule; the names are the most-minutes {adj} players of each peak season, goalkeepers included — a lineup of presence, not a quality ranking: {golden}. The break date comes from a Bayesian local-level model with one change point {cite_cp}; detail in <a href=\"#series-model\">§ Methodology</a>.",
    "slide.7.alt": "Line chart: {adj} players with at least {min} minutes in the Big-5 leagues, {start} to {end}, against eight peer countries; a lower panel shows per-million rates for {nation}, {a} and {b}.",
    "slide.8.q": "How do {a} and {b} do it?",
    "slide.8.aq": "In numbers: {a} and {b} against {nation} on the same six {topn}-strongest-league pathway definitions, same seasons.",
    "slide.8.a": "On the same six numbers {a} gives U21 players <strong>{nor_u21} %</strong> of domestic minutes against {cze_u21} % and sends {nor_top9} % of its squad to the {topn} strongest leagues against {cze_top9} %.",
    "slide.8.how": "Same definitions, same seasons; a comparison, not a causal claim. Each metric is rescaled 0-1 across the three countries for the chart above, direction chosen so 1.0 is always the more open pathway (more players per million, more U21 minutes, an earlier export age, fewer sideways moves, a bigger minutes share abroad, more of the squad in the top-9); the table below keeps the raw numbers.",
    "slide.8.alt": "Slope chart: {a}, {b} and {nation} on six pathway metrics, each rescaled 0 (worst of the three) to 1 (best of the three), one line per country.",
    "slide.8.table_summary": "The six numbers, unscaled",
    "slide.8b.q": "Do goalkeepers follow a different path?",
    "slide.8b.aq": "In numbers: {adj} goalkeepers with ≥ {min} minutes in the top-{topn} leagues, per million inhabitants, against outfield export age.",
    "slide.8b.a": "{n_gk} {adj} goalkeepers play ≥ {min} minutes in the top-{topn} leagues ({pm} per million, rank <strong>{rank} of {n}</strong>); they first appeared there at a median age of {gk_age}, against {out_age} for outfield exports — {earlier_or_later} than outfield exports.",
    "slide.8b.earlier": "earlier",
    "slide.8b.later": "later",
    "slide.8b.same_age": "at the same age",
    "slide.8b.alt": "Strip plot of age at first top-9-league appearance, {adj} goalkeepers against outfield exports, one dot per player, medians marked.",
    "slide.8b.how": "{min}-minute floor, {season} rosters, same K = {phantom} shrinkage as the rest of the report; first season in a fetched top-{topn} table; players already there in {history_start} are censored — {censored_pct} % of the goalkeepers, {censored_out_pct} % of the outfield exports; a comparison of two pathways inside one nation, not a causal claim.{home_note}",
    "slide.8b.home_note": " First top-{topn} season needs no move for a {home_league} keeper.",
    "slide.8c.q": "What is the gap made of?",
    "slide.8c.aq": "In numbers: a linear split of the per-capita gap into U21 minutes, league strength and export age across {n} peer countries.",
    "slide.8c.a": "Of the {gap} players per million between {contrast} and {nation}, U21 minutes go with {c1}, league strength with {c2}, export age with {c3}; {resid} is not carried by the three channels.",
    "slide.8c.alt": "One horizontal stacked bar per contrast country: the contribution of U21 minutes, league strength and export age to its per-capita gap with {nation}, plus the residual; whiskers show each channel's bootstrap interval.",
    "slide.8c.how": "Ridge-regression linear split, Blinder-Oaxaca-style {cite_ob}, fit on the {n} peer countries with data on all three channels; bootstrap 90 % intervals, {n_boot} resamples; a decomposition of a correlation, not a causal accounting.",
    "slide.9.q": "Who are the players?",
    "slide.9.aq": "In numbers: {n} showcase cards chosen from the {season} pool by six selection rules, one per position group per rule.",
    "slide.9.a": "<strong>{n} cards</strong> chosen by six rules.",
    "slide.9.how": "{season} FBref, Wikipedia and Wikidata rows joined by name and birth year; six selection rules, applied in order — see below.",

    # ---- slide 2 proof: compact cohort-gap table (top 5 rows)
    "cohortgap.th.group": "Group",
    "cohortgap.th.cohort": "Cohort",
    "cohortgap.th.cze": "{code}",
    "cohortgap.th.peer": "Peer median",

    # ---- slide 8 proof: table.peer-compare (CZE / NOR / DEN, six numbers + Big-5 count now)
    "peer_compare.aria": "{nation}, {a} and {b} on six same-definition pathway numbers",
    "peer_compare.th.metric": "Metric",
    "peer_compare.per_million": "Players per million",
    "peer_compare.u21_share": "U21 share of domestic minutes",
    "peer_compare.export_age": "Export age (recent)",
    "peer_compare.sideways": "Sideways moves",
    "peer_compare.minutes_share": "Exports' club-minutes share",
    "peer_compare.wc_top9": "World Cup squad in the top-9 leagues",
    "peer_compare.big5_now": "Big-5 players now",

    # ---- explore the data (folded; today's chapters I-III material)
    "explore.h2": "Explore the data",

    # ---- for a federation (what transfers, right after the slides)
    "fed.h3": "For a federation",
    "fed.benchmark.title": "Benchmark",
    "fed.benchmark.body": "Top-league players per million against a chosen peer set, by position and age cohort.",
    "fed.benchmark.used_by": "Used by: performance and insights staff.",
    "fed.pathways.title": "Pathways",
    "fed.pathways.body": "Youth minutes at home, export age and route, how exports fare, where they land — six exhibits.",
    "fed.pathways.used_by": "Used by: development staff.",
    "fed.squad.title": "Tournament squad lens",
    "fed.squad.body": "A named squad by league tier, minutes and age, next to the peers at the same tournament.",
    "fed.squad.used_by": "Used by: selection staff, for context.",
    "fed.models.title": "Models, validated",
    "fed.models.body": "Shrinkage, league multipliers with a sensitivity table, cluster archetypes, analogs — every number recomputed each run; data-quality log and review ledger in the repo.",
    "fed.models.used_by": "Used by: the analyst running this pipeline.",

    # ---- plain-language metric labels (used everywhere outside chapter IV;
    # chapter IV keeps "npG+A/90 q" and explains it once)
    "metric.prod": "goals + assists per 90, league-adjusted",
    "metric.prod.short": "G+A / 90 adj.",

    # ---- chapter I
    "ch1.benchmark.h3": "Structural benchmark vs peer countries",
    "ch1.benchmark.p": "Football intuition recognises the {adj} pool player by player. <strong>Its structural position among the peer countries needs an aggregation nobody holds in one place.</strong> Three numbers below that are usually not collected together.",
    "ch1.capita.aria": "Per-capita density of top-league players by country",
    "ch1.heatmap.alt": "Heatmap of the international cohort benchmark: {n} countries by position group and age cohort, {season} season; the {adj} row is outlined.",
    "ch1.heatmap.caption": "Median non-penalty goals + assists per 90 by country, position group and age cohort, {season}; the outlined row is {nation}.",
    "ch1.heatmap.note": "Each cell: player count and the median value; rows ordered by per-capita rank, {nation} highlighted.",
    "ch1.cohorts.h4": "Cohort gaps — {group}",
    "ch1.cohorts.th": "Cohort",
    "ch1.cohorts.none": "no player",
    "ch1.cohorts.note": "* Count and median npG+A per 90 of players with the country's nationality in a top-{topn} league, {season}, at least {min} minutes; cohort by age at the season's calendar turn (start year + 1 − birth year). {shown} of the {n} countries are shown; the heatmap above carries all of them. Largest {adj} shortfalls against the peer median count: {gaps}.",
    "ch1.cohorts.gap_item": "{group} {cohort} ({cze} vs {peer})",
    "ch1.atlas.alt": "Two-panel atlas of {group} {season} in PCA projection. Left panel: style map without league multipliers; right panel: quality-adjusted map. Grey points are the whole corpus of {corpus} players; coloured points are the {czech} {adj}-eligible players by cluster; oxblood rings mark the {nt} with a national-team call-up {nt_years}.",
    "ch1.atlas.caption": "Atlas of {group} {season} in both projections: {czech} {adj}-eligible players in colour against a corpus of {corpus}. Oxblood rings mark the national-team pool (call-up {nt_years}, {nt} players).",
    "ch1.observations.h3": "Observations",
    "ch1.clusters.h3": "Cluster archetypes (style projection)",
    "ch1.clusters.p": "Clusters are fitted on the whole corpus of {season} player-seasons and read here through their {adj} members, K chosen by silhouette score {cite_rousseeuw} with scikit-learn {cite_pedregosa}. The label describes the cluster's median footprint; the count is {adj} members of the corpus cluster; names are the {adj} members with the most minutes.",
    "ch1.clusters.meta": "{n} {adj} of {corpus} · NT pool {nt} · median born {born}",
    "ch1.clusters.medians": "Corpus medians: {npg} non-penalty goals and {ast} assists per 90, {share} of the club's minutes, age {age}, {cards} cards per 90.",
    "ch1.clusters.tactical": "Tactical read",
    "ch1.traj.h3": "Trajectories {previous} → {metrics} ({adj}-eligible, ≥ {min} minutes in both seasons)",
    "ch1.traj.p": "Season-over-season change in goals + assists per 90, league-adjusted. A move counts as up or down beyond ± {band}; everything inside that band is stable and not listed.",
    "ch1.traj.h4": "{group} — {n} players: {up} up, {stable} stable, {down} down",
    "ch1.traj.up": "Moving up &middot; {metric}",
    "ch1.traj.down": "Moving down &middot; {metric}",
    "ch1.traj.th.player": "Player",
    "ch1.traj.th.league": "League",
    "ch1.traj.th.min": "Min {previous} / {metrics}",
    "ch1.traj.th.delta": "Change",
    "ch1.traj.none_up": "No {adj} player moved up beyond the band.",
    "ch1.traj.none_down": "No {adj} player moved down beyond the band.",

    # ---- chapter II
    "ch2.framing": "Four exhibits comparing {nation} with {n} peer countries: youth exposure at home, export route, how exports fare, and who made it.",
    "ch2.a.h3": "Exhibit A — youth exposure at home",
    "ch2.a.p": "Share of a domestic league's total minutes played by its own nationals aged 21 or under, {season}.",
    "ch2.a.aria": "Share of domestic-league minutes played by own under-21 nationals",
    "ch2.a.nodata": "league not on FBref",
    "ch2.a.note": "* Σ minutes of players with the league country's nationality and age ≤ 21 at the season's start ÷ Σ minutes of all players in the league, {season}. Under-23 shares: {u23}. A league without a bar is not covered by FBref.",
    "ch2.b.h3": "Exhibit B — export route",
    "ch2.b.p": "For every peer-country player on a {current} top-{topn} roster: the age at the first top-{topn} season (full roster, and recent entrants only) and, for recent entrants, the league of the season before it.",
    "ch2.b.cze": "{Adj} exports: {n} players, median export age {age} (recent entrants {n_recent}, median {age_recent}), {domestic} of the recent ones straight from the {home_league}*.",
    "ch2.b.th.country": "Country",
    "ch2.b.th.recent": "Recent",
    "ch2.b.th.age_all": "Export age (all)",
    "ch2.b.th.age_recent": "Export age (recent)",
    "ch2.b.th.domestic": "Domestic",
    "ch2.b.th.stepping": "Stepping stone",
    "ch2.b.th.other": "Other top-{topn}",
    "ch2.b.th.not_covered": "Not covered",
    "ch2.b.th.censored": "Censored",
    "ch2.b.note": "* Export age = age at the first season in any headline league, history back to {start}; a first appearance already in {start} is censored. Recent entrants: first top-{topn} season {metrics} or {current}, the only ones whose previous season lies inside the fetched window ({coverage} onwards for peer domestic leagues). Stepping-stone leagues: {stepping}. Not covered: no earlier row in the data.",
    "ch2.c.h3": "Exhibit C — how the exports fare",
    "ch2.c.p": "Peer-country players at a top-{topn} club in {season}: median share of the club's minutes, and the club's strength within its league.",
    "ch2.c.aria.min": "Median minutes share of exports at their club, by country",
    "ch2.c.aria.goals": "Median club goals-scored percentile of exports' clubs, by country",
    "ch2.c.note": "* Minutes share = player minutes ÷ (club matches × 90), {season}, one row per player-season. Club strength proxy: {proxy} — clubs ranked by the goals their own roster scored that season (ClubElo was unreachable at run time). Both are medians over the country's exports; n per country in the bars.",
    "ch2.d.h3": "Exhibit D — profile of those who made it",
    "ch2.d.p": "Goals + assists per 90, league-adjusted, in {season} by the tier of the player's own league: domestic, stepping stone, top-{topn}, or another covered league. {Adj} count and median against the median of the peer countries' values.",
    "ch2.d.summary": "Profile table by tier and position group",
    "ch2.d.th.tier": "Tier",
    "ch2.d.th.group": "Group",
    "ch2.d.th.cze_n": "{code} n",
    "ch2.d.th.cze_median": "{code} median",
    "ch2.d.th.peer_n": "Peer median n",
    "ch2.d.th.peer_median": "Peer median",
    "ch2.d.note": "* Tier = the league of the player's own {season} season. Peer median n and peer median are medians across the peer countries present in that tier and group; a tier a country has no player in is absent, not zero.",
    "ch2.e.h3": "Exhibit E — where {adj} exports go",
    "ch2.e.p": "Of the {total} mapped {adj} players, {abroad} play outside the {home_league}.",
    "ch2.e.aria": "{Adj} players abroad by destination bucket",
    "ch2.e.median_mult": "median multiplier {m}",
    "ch2.e.note": "* Buckets by the league of the player's own {season} season; a player is counted once per position group, like everywhere else on the page, so one with rows in two groups counts in each; the number in front of each bar is the player count, the median multiplier is the bucket's median league multiplier. Sideways: {definition}.",
    "ch2.f.h3": "F · The {event} squad by league tier",
    "ch2.f.p": "Where the {n} players named to the {event} squad played in {season}, next to {peers}. Tier = the league of the player's most-minutes {season} row.",
    "ch2.f.th.country": "Country",
    "ch2.f.th.squad": "Squad",
    "ch2.f.th.top9": "Top-9 %",
    "ch2.f.th.stepping": "Stepping %",
    "ch2.f.th.domestic": "Domestic %",
    "ch2.f.th.other": "Other %",
    "ch2.f.th.median_min": "Median minutes",
    "ch2.f.th.median_mult": "Median multiplier",
    "ch2.f.th.u22": "U22",
    "ch2.f.th.c2325": "23–25",
    "ch2.f.th.c2629": "26–29",
    "ch2.f.th.c30plus": "30+",
    "ch2.f.note": "* {unmatched} squad players have no {season} row in the fetched leagues and are counted as unmatched.",
    "ch2.f.detail": "Minutes, multipliers and age cohorts by country",

    # ---- slide 6 squad face grid (Task 25b): the {event} squad as portraits,
    # tinted by league tier; the peer-country bars fold under "how the peers
    # are sourced" below it
    "squad.grid.aria": "{event} squad by league tier, one portrait per player",
    "squad.peers.summary": "How the peers are sourced",

    # ---- chapter III
    "ch3.cards.rules.summary": "How the {n} cards were chosen",
    "ch3.cards.rules": "Why these cards: one card per position group per rule, applied in this order — (a) highest {metric}, (b) youngest national-team call-up, (c) most top-9 minutes among the {event} squad, (d) most domestic-league minutes among the {event} squad, (e) most top-9 minutes, (f) most domestic minutes under 23 without a top-9 season. A player already chosen by an earlier rule falls through to the next name, so a later row can show the second name by its measure. Rows group the six rules; the national-team core row holds two of them.",
    "ch3.reason.top_metric": "highest {metric} among {pos}",
    "ch3.card.nt": "NT {nt_years}",
    "ch3.card.latest_known": "latest known",
    "ch3.card.stat.rates": "Non-penalty goals / assists per 90",
    "ch3.card.stat.min": "Minutes",
    "ch3.card.style": "Style map",
    "ch3.card.quality": "Quality map",
    "ch3.card.tactical": "Tactical read",
    "ch3.card.traj": "Trajectory {previous} &rarr; {metrics}",
    "ch3.card.analogs": "Historical analogs at age {age}",
    "ch3.card.min": "min",
    "ch3.card.selected": "Selected as: {reason}.",
    "ch3.cards.note": "* Each card renders the existing dataset; no computation beyond the join. Age on the name line is the {current} season-start age (start year − birth year); the club is from the {current} tables, or — labelled \"{latest}\" — from FBref's country page where the player has no {current} row. Age on the analog line follows the analog finder's convention (season start year + 1 − birth year).",
    "ch3.gk.kicker": "Goalkeepers — most top-9 minutes · youngest in the top-{topn}",
    "gk.stat.ga90": "GA/90",
    "gk.stat.saves90": "Saves/90",
    "gk.stat.savepct": "Save %",
    "gk.card.tier": "Club tier",
    "gk.card.tier_line": "{club} ({league}) · {club_pct} of the league's goals scored",
    "gk.card.tier_line_na": "Club-tier percentile unavailable.",
    "gk.tier.summary": "Club tier: {adj} top-9 goalkeepers, {season}",
    "gk.tier.th.player": "Player",
    "gk.tier.th.club": "Club",
    "gk.tier.th.league": "League",
    "gk.tier.th.min": "Minutes",
    "gk.tier.th.club_pct": "Club goals percentile",
    "gk.production.summary": "Goalkeeper production: {adj} keepers, {season}",
    "gk.production.th.ga90": "GA/90",
    "gk.production.th.saves90": "Saves/90",
    "gk.production.th.savepct": "Save %",
    "gk.production.th.csshare": "Clean-sheet share",
    "gk.production.th.ga90q": "GA/90, quality-adj.",
    "gk.production.medians_label": "Peer median quality-adjusted GA/90:",
    "gk.per_million.summary": "Goalkeepers per million, by country",
    "gk.per_million.aria": "Top-9-league goalkeepers per million inhabitants by country",
    "ch3.analogs.h3": "Historical analogs",
    "ch3.analogs.p": "For each showcase player the finder takes the nearest {n} player-seasons at the same age across the whole corpus of every fetched league — the {topn} headline leagues back to {start}, the rest from {coverage} — all nationalities. Distance is computed on three standardised features: <code>npG+A/90 (quality-adjusted)</code>, <code>minutes</code>, <code>league multiplier</code>. For every analog the following seasons are shown as they happened. <strong>Description, not prediction</strong>: the reader sees the spread of paths; the method imposes none.",
    "ch3.analogs.target": "Target",
    "ch3.analogs.age": "age",
    "ch3.analogs.target_stats": "{group} &middot; age {age} &middot; {league} {season} &middot; {min} min &middot; {q} npG+A/90 quality",
    "ch3.analogs.cohort": "Nearest {n} at the same age",
    "ch3.analogs.row": "{league} {season} &middot; {min} min &middot; {q} npG+A/90 &middot; d&nbsp;=&nbsp;{d}",
    "ch3.analogs.followed": "Followed by:",
    "ch3.analogs.none": "No later season in the corpus.",
    "ch3.analogs.note": "* Corpus: player-seasons with at least {min} minutes in any fetched league — headline leagues {start} → {current}, the other leagues {coverage} → {current}; the target's own seasons are excluded. A path that ends early means the player left the covered leagues, not that the career ended.",

    # ---- player index
    "pi.h2": "Player index",
    "pi.framing": "Every {adj}-eligible player with a complete {season} season in a covered league — {n} players — with the numbers behind the atlases. Names with a card link to it.",
    "pi.search": "Search by name",
    "pi.search.placeholder": "Name…",
    "pi.summary": "Table of {n} players",
    "pi.th.player": "Player",
    "pi.th.pos": "Pos",
    "pi.th.age": "Age",
    "pi.th.club": "Club",
    "pi.th.league": "League",
    "pi.th.min": "Min",
    "pi.th.cluster": "Style cluster",
    "pi.th.nt": "NT",
    "pi.nt_yes": "NT",
    "pi.note": "* {season} season, at least {min} minutes; the club is the one with the most minutes that season. NT = national-team call-up {nt_years}.",

    # ---- chapter IV
    "ch4.aria": "Chapter IV",
    "ch4.title": "How it is built, validated and where it stops",
    "ch4.synopsis": "A replicable pipeline: data sources, league multipliers, Bayesian shrinkage, PCA loadings, sensitivity analysis. Limitations and reproducibility.",
    "ch4.h2": "How it is built, validated and where it stops",
    "ch4.sources.h3": "Data sources",
    "ch4.sources.fbref": "<strong>FBref</strong> (via <code>soccerdata</code>): player season tables (standard, playing time) for the {topn} headline leagues, the {home_league}, the peer domestic leagues and the German second tier; the country page \"Players from {nation}\" for pool discovery; the nationality column for peer counts",
    "ch4.sources.wikipedia": "<strong>Wikipedia</strong>: national-team squad tables ({events}) for the call-up flag",
    "ch4.sources.wikidata": "<strong>Wikidata / Wikimedia Commons</strong>: player portraits (P18) matched on name, citizenship and date of birth; credits in the footer",
    "ch4.sources.uefa": "<strong>UEFA association coefficients</strong> (via Wikipedia) as the league-strength source, ClubElo being unreachable at run time",
    "ch4.sources.eurostat": "<strong>Eurostat</strong>: population estimates, 2024",

    "ch4.eda.h3": "From raw tables to a feature vector",
    "ch4.eda.intro": "One {season} player-season, traced from its raw FBref row to the five-number vector the rest of this chapter builds on: {player}, the {adj} player with the most {season} minutes among those who cleared the inclusion floor.",
    "ch4.eda.tables.summary": "{player}: raw row and feature row",
    "ch4.eda.raw.caption": "Raw FBref row, {season}",
    "ch4.eda.raw.th.column": "Column",
    "ch4.eda.raw.th.value": "Value",
    "ch4.eda.feature.caption": "Feature row after the pipeline",
    "ch4.eda.feature.th.feature": "Feature",
    "ch4.eda.feature.th.raw": "Raw",
    "ch4.eda.feature.th.shrunk": "Shrunk",
    "ch4.eda.feature.th.quality": "Quality-adjusted",
    "ch4.eda.feature.th.z": "Z-score",
    "ch4.eda.cleaning.p": "Six wrangling checks turn the raw rows above into the pool used everywhere else in this report, recomputed on every run:",
    "ch4.eda.cleaning.link": "The full log, with the recorded pipeline incidents, is in <a href=\"#data-quality\">the data-quality log</a> below.",
    "ch4.eda.features.p": "Every position group shares the same five-number vector (spec §5): a raw column becomes a per-90 rate, shrunk toward its league-season median {cite_efron_morris}, then multiplied by the league quality projection.",
    "ch4.eda.features.npg_p90.def": "non-penalty goals per 90 minutes",
    "ch4.eda.features.npg_p90.why": "penalties are shot quality, not open-play production, and inflate a taker's raw goal count for reasons that have nothing to do with how the player creates chances",
    "ch4.eda.features.ast_p90.def": "assists per 90 minutes",
    "ch4.eda.features.ast_p90.why": "the direct creative complement to non-penalty goals, on the same basic table for every league in the corpus",
    "ch4.eda.features.min_share.def": "minutes played ÷ (club matches × 90)",
    "ch4.eda.features.min_share.why": "the coach's own read of the player, sturdier than counting appearances (see below)",
    "ch4.eda.features.age.def": "age at the season's start (start year − birth year)",
    "ch4.eda.features.age.why": "median production still shifts by age band in this corpus (see below), so it stays as its own axis rather than being folded into anything else",
    "ch4.eda.features.cards_p90.def": "yellow + 2 × red cards per 90 minutes",
    "ch4.eda.features.cards_p90.why": "a discipline signal folded into one rate because red cards alone are too sparse a signal on their own (see below)",
    "ch4.eda.rejected.p": "Five candidates considered for the {season} vector and what the data said about each, corpus-wide (every fetched nationality, the same population the rest of this chapter describes):",
    "ch4.eda.rejected.th.candidate": "Candidate",
    "ch4.eda.rejected.th.statistic": "Statistic",
    "ch4.eda.rejected.th.value": "Value",
    "ch4.eda.rejected.th.decision": "Decision",
    "ch4.eda.rejected.gls_p90.statistic": "Correlation with npg_p90",
    "ch4.eda.rejected.gls_p90.decision": "Replaced by npg_p90",
    "ch4.eda.rejected.mp.statistic": "Correlation with minutes played",
    "ch4.eda.rejected.mp.decision": "Replaced by minutes share",
    "ch4.eda.rejected.crdr_p90.statistic": "Share of player-seasons with zero red cards",
    "ch4.eda.rejected.crdr_p90.decision": "Folded into cards",
    "ch4.eda.rejected.age.statistic": "Spread of median goals + assists per 90 across age bands (max − min band)",
    "ch4.eda.rejected.age.decision": "Kept",
    "ch4.eda.rejected.born.statistic": "Share of player-seasons missing a birth year",
    "ch4.eda.rejected.born.decision": "Kept — required for the player key",
    "ch4.eda.rejected.note": "Despite the high correlation, goals and non-penalty goals diverge for the players who take penalties: {top3}. Appearances (mp) correlate strongly with minutes but not perfectly — a substitute cameo counts the same as 90 minutes started, which is why minutes share, not appearances, measures playing time here. Median goals + assists per 90 by age band runs from {age_range}.",
    "ch4.eda.fig1.alt": "Small multiples: the five raw per-90 features' distributions by league, boxplots per league, the {home_league} highlighted, {n} leagues shown.",
    "ch4.eda.fig1.caption": "The picture behind league adjustment: the same raw rate reads very differently depending on the league it was earned in.",
    "ch4.eda.fig2.alt": "Scatter of raw vs shrunk non-penalty goals per 90 against minutes for {adj}-eligible players, with the shrinkage weight on the league median as a function of minutes overlaid.",
    "ch4.eda.fig2.caption": "What shrinkage does to a low-minute player: at the inclusion floor the league median still carries most of the weight; {player}'s rate moves the most of any {adj}-eligible player this season.",

    "ch4.mult.h3": "League multipliers (quality projection)",
    "ch4.mult.th.league": "League",
    "ch4.mult.th.value": "Multiplier",
    "ch4.mult.method": "Method: <code>{method}</code>. {source} The sensitivity analysis below shows the ranking's robustness to ±20 % on any one multiplier.",
    "ch4.shrink.h3": "Bayesian shrinkage",
    "ch4.shrink.p1": "Per-90 rates of players with few minutes are shrunk towards the median of their league and season (players with at least {phantom} minutes) using the empirical Bayes formula {cite_efron_morris}, with K = 10 phantom matches expressed as {phantom} minutes:",
    "ch4.shrink.formula": "shrunk_rate = (events + K × league_median) / (minutes / 90 + K), &nbsp; K = 10",
    "ch4.shrink.tex": "\\text{{shrunk rate}} = \\dfrac{{\\text{{events}} + K \\cdot \\text{{league median}}}}{{\\text{{minutes}} / 90 + K}},\\qquad K = 10",
    "ch4.shrink.p2": "At {min} minutes (the inclusion floor) the league median carries {weight} of the weight; at {phantom} minutes the player's own rate and the median weigh the same. Minutes share and age are not shrunk.",
    "ch4.gk.p": "Goalkeeper rates (chapter II's counter-example) use the same formula. GA/90 and saves/90 are shrunk toward their league-season median with the same K = {phantom} minutes, and GA/90 is then quality-adjusted by the league multiplier — a goal conceded in a stronger league counts less. Save percentage is shrunk the same way but against shots on target faced, not minutes: a single season's shot count sits far below K = {phantom}, so save_pct_shrunk compresses hard toward the league median for almost every goalkeeper — a large gap in the raw, unshrunk save percentage is the more informative read there.",
    "ch4.mult.tex": "\\text{{npG/90}}_{{\\text{{quality}}}} = \\text{{npG/90}}_{{\\text{{shrunk}}}} \\times m_{{\\text{{league}}}}",
    "ch4.mult.formula": "npG/90_quality = npG/90_shrunk × m_league",
    "ch4.pca.h3": "PCA loadings",
    "ch4.pca.p": "One five-feature vector per position group ({features}), standardised, reduced to two components per projection. Style uses the shrunk rates; quality multiplies the rates by the league multiplier first.",
    "ch4.pca.th.group": "Group",
    "ch4.pca.th.projection": "Projection",
    "ch4.pca.th.variance": "% variance",
    "ch4.pca.th.share": "min share",
    "ch4.pca.th.age": "age",
    "ch4.sens.h3": "Sensitivity analysis (±20 % multipliers)",
    "ch4.sens.p": "For each scenario the quality-adjusted ranking of {adj}-eligible players within each position group was recomputed and compared with the baseline; \"top-10\" is the union of the {groups} groups' own top tens ({base} players at baseline). Of the {n} scenarios, {zero} change nobody in that set; the largest churn is {churn}{worst}*.",
    "ch4.sens.worst": " ({description}, mean rank shift {delta} in the top twenty)",
    "ch4.sens.th.scenario": "Scenario",
    "ch4.sens.th.description": "Description",
    "ch4.sens.th.overlap": "Top-10 overlap",
    "ch4.sens.th.churn": "Top-10 churn",
    "ch4.sens.th.delta": "Mean Δ rank (top 20)",
    "ch4.sens.note": "* Churn = baseline top-10 members that leave the set under the scenario; mean Δ rank = mean absolute rank change over the baseline top-20 union. Scenarios: baseline, every league ±20 % on its own, and all leagues ±20 % at once.",
    "ch4.sens.live.p": "The table above is fixed at the config multipliers; the panel below is the same {adj}-eligible top ten made interactive — drag any league's slider (0.5×–1.5× of its default) and the ranking recomputes in the browser.",
    "ch4.sens.live.reset": "Reset",
    "ch4.sens.live.slider_aria": "{league} multiplier",
    "ch4.sens.live.th.rank": "#",
    "ch4.sens.live.th.player": "Player",
    "ch4.sens.live.th.league": "League",
    "ch4.sens.live.th.change": "Vs. default",
    "ch4.sens.live.how": "This is the offline sensitivity table above (§ Sensitivity analysis) made interactive: q = (npG/90_shrunk + A/90_shrunk) × m_league, recomputed client-side from the shrunk rates of every {adj}-eligible metrics-season player, no server round-trip. The rank-change column compares each row's rank under the current sliders to its rank at the config defaults.",

    "ch4.strength.h3": "League strength: two estimates",
    "ch4.strength.p1": "How much is a {home_league} season worth in Premier League terms? The UEFA multiplier above answers that from countries' continental results; this model answers the same question from the players who actually changed leagues.",
    "ch4.strength.p1_is_ref": "How much is a season in Europe's other strongest leagues worth in {home_league} terms? The UEFA multiplier above answers that from countries' continental results; this model answers the same question from the players who actually changed leagues.",
    "ch4.strength.design": "Movers — {players} players observed in at least two leagues across {rows} qualifying player-seasons — anchor the model, since only a player's own before/after change of league separates their level from the league's scoring environment. A hierarchical Poisson model of non-penalty goals plus assists per 90 {cite_bda} fits a league effect and a player effect together, sampled with NUTS {cite_nuts} in PyMC {cite_pymc} and diagnosed with ArviZ {cite_arviz}. Partial pooling keeps the league effects regularised while leaving player effects close to unpooled, the same within-subject logic behind plus-minus and RAPM ratings elsewhere in team sports {cite_rapm}.",
    "ch4.strength.fig_alt": "Dot and 90 % HDI of the model's league-strength multiplier m_L per league, sorted, with each league's UEFA multiplier as a hollow marker.",
    "ch4.strength.home": "In these terms, a {home_league} season converts to {median} of a Premier League one (90 % HDI {lo}–{hi}).",
    "ch4.strength.home_is_ref": "As the model's own reference point, {home_league} converts to 1.00 by construction; the table below puts every other league in these terms.",
    "ch4.strength.th.league": "League",
    "ch4.strength.th.median": "m_L (median)",
    "ch4.strength.th.hdi": "90 % HDI",
    "ch4.strength.th.transitions": "Transitions",
    "ch4.strength.th.uefa": "UEFA",
    "ch4.strength.oos.p": "Refit on seasons before {season}, the model predicts each mover's first {season} row after a league change — {n} such moves — against two baselines: the same rate as before, and that rate scaled by the ratio of UEFA multipliers. This is the same population CIES Football Observatory's expatriate-player reports track {cite_cies}.",
    "ch4.strength.oos.th.method": "Method",
    "ch4.strength.oos.th.logpd": "Log predictive density",
    "ch4.strength.oos.th.mae": "MAE (rate)",
    "ch4.strength.oos.method.naive": "Same rate as before",
    "ch4.strength.oos.method.uefa": "Rate × UEFA ratio",
    "ch4.strength.oos.method.model": "Model",
    "ch4.strength.spearman": "Against {n} leagues in common, the model's medians and the UEFA multipliers correlate at Spearman's rho = {rho}.",
    "ch4.strength.disagreement": "{league}: model rank {model_rank} vs UEFA rank {uefa_rank} (m_L {model_median} vs multiplier {uefa}).",
    "ch4.strength.diagnostics": "R-hat ≤ {rhat}, minimum bulk ESS {ess}, {div} divergent transitions across {rows} player-seasons from {players} movers; fit in {runtime} s.",
    "ch4.strength.selection": "What the movers do not show: they are not a random sample — players tend to move up when they are good and down when they are older — so the within-player contrast describes the league difference for the kind of player who moves, and the age term absorbs only the part of that selection that is age. The interval is the model's uncertainty, not the selection's.",
    "ch4.strength.ranking": "The report's rankings keep the UEFA-coefficient multiplier throughout; the model above is shown alongside it as a check on that multiplier's own assumption — that continental results track player-level strength — not as a replacement for it.",
    "ch4.strength.ppc.summary": "Posterior predictive check",
    "ch4.strength.ppc.p": "Observed vs. replicated non-penalty goals plus assists per player-season {cite_ppc}: {obs_zero} vs {rep_zero} share of zeros, mean {obs_mean} vs {rep_mean}, 90th percentile {obs_p90} vs {rep_p90}.",
    "ch4.strength.ppc.fig_alt": "Bar chart comparing the observed and posterior-predictive-replicated distribution of non-penalty goals plus assists per player-season, grouped 0/1/2/3/4/5+.",

    "ch4.compare.h3": "Three models, one task, five seasons",
    "ch4.compare.q": "What does a player's season tell us about the next one, given where he plays, how old he is and — for exports — at what age he moved? In model terms: predict a player's league-adjusted production next season (non-penalty goals plus assists per 90, quality-adjusted) from this season's numbers, for every player-season pair with at least {min} minutes in both seasons, every nationality in the corpus.",
    "ch4.compare.design": "Evaluated by rolling-origin cross-validation {cite_ro}: for each of {n_origins} target seasons in turn, every model trains only on pairs whose target season came earlier and is tested on that season's pairs — the same discipline a forecaster uses when the future is genuinely unknown at fit time, and what makes the per-season table below a real \"performance over time\" read rather than one blended number. Two baselines — persistence (next season = this season) and shrinkage to the league mean — sit alongside three fitted models sharing the same eight features: a hierarchical Bayesian regression (target ~ Normal(μ, σ), partial pooling on league and player, NUTS, {chains} chains × {draws} draws per origin {cite_bayes}), a gradient-boosted regressor and a small multilayer perceptron (scikit-learn {cite_sklearn}, hidden layers 64/32 — a small MLP, not an embedding model: PyTorch is not part of this pipeline). The Bayesian model's training rows are subsampled to at most {max_train} per origin to keep five origins' worth of fits inside the runtime budget; the other four models train on the full split. The target is adjusted with the multiplier of the league the player is in next season; the features only know this season's league, so a move is a change the models cannot see coming — a limitation shared by all five.",
    "ch4.compare.fig_alt": "Line chart of RMSE per target season, one line per model, persistence dashed.",
    "ch4.compare.th.model": "Model",
    "ch4.compare.th.pooled": "Pooled",
    "ch4.compare.model.persistence": "Persistence",
    "ch4.compare.model.shrinkage_league_mean": "Shrinkage to league mean",
    "ch4.compare.model.bayesian": "Hierarchical Bayesian",
    "ch4.compare.model.gbm": "Gradient boosting",
    "ch4.compare.model.mlp": "Small MLP",
    "ch4.compare.note": "Each cell: RMSE (MAE), in league-adjusted npG+A per 90. The first origin's training set is empty by construction — the corpus's earliest feature season leaves no earlier target season to train on — so only the two baselines are reported there.",
    "ch4.compare.coverage": "The Bayesian model's 90 % predictive interval covered the observed value {pooled} of the time, pooled across the {n} origins it was fit for ({per_origin}).",
    "ch4.compare.winner": "By pooled RMSE, {winner} wins ({rmse} vs {persistence_rmse} for persistence, {margin} lower).",
    "ch4.compare.drift": "The clearest season-to-season move in the winner's own RMSE is between {from} and {to} ({value}) — the kind of drift this rolling-origin table exists to surface.",

    "ch4.series.h3": "Dating the break and one forecast",
    "ch4.series.design": "The series is modelled as a local level in state space {cite_ss}: the log of the season count follows a Gaussian random walk (σ ~ HalfNormal(0.2)), plus one step change δ in the level at an unknown break season τ. NUTS only samples continuous parameters, so τ is not sampled directly — every candidate season at least {margin} seasons from either end is marginalised out of the model with a single log-sum-exp potential and its own posterior recovered afterwards from the continuous draws, the standard move for a marginalised discrete parameter {cite_marg}; the changepoint idea itself is due to {cite_cp}, applied here to a batch, single-break setting. A rolling-origin backtest {cite_ro} refits the same local level without the step at each of {n_backtest} origins, forecasting one season ahead and scoring against the naive \"same as last season\" baseline — the honest forecaster's read, since no real origin knows in advance which side of a break it sits on. The one forecast below, from the same change-point-free model fitted on the full series, is a demonstration of the method on a count of players, not a statement about any player.",
    "ch4.series.fig_alt": "Line chart of the {nation} series with the change-point model's fitted level and band, a bar strip below the axis for the posterior probability of the break at each candidate season, and the one-season forecast with its 90 % interval at the right edge.",
    "ch4.series.break.p": "For {nation}, the model dates the break to {season} ({prob} posterior probability), a ×{delta} ({lo}–{hi}, 90 % HDI) change in the level; the random walk's own innovation scale is σ = {sigma}.",
    "ch4.series.break.top_item": "{season}: {prob}",
    "ch4.series.contrast.p": "The same model, fit separately for the two contrast countries:",
    "ch4.series.contrast.item": "{name}: {season} ({prob} posterior), ×{delta} ({lo}–{hi}).",
    "ch4.series.backtest.p": "One-step-ahead rolling-origin backtest of the plain local level (no change point) against the naive \"same as last season\", {n} origins from {start} to {end}:",
    "ch4.series.backtest.th.origin": "Origin",
    "ch4.series.backtest.th.next": "Forecast season",
    "ch4.series.backtest.th.actual": "Actual",
    "ch4.series.backtest.th.model": "Model median (90 % interval)",
    "ch4.series.backtest.th.naive": "Naive",
    "ch4.series.backtest.note": "Pooled across {n} origins: MAE {mae_model} for the model against {mae_naive} for the naive baseline, {coverage} of the 90 % intervals covered the observed value.",
    "ch4.series.forecast.p": "The one forecast, for next season ({season}), from the same change-point-free model fitted on the full series:",
    "ch4.series.forecast.th.country": "Country",
    "ch4.series.forecast.th.season": "Season",
    "ch4.series.forecast.th.median": "Median",
    "ch4.series.forecast.th.interval": "90 % interval",
    "ch4.series.forecast.note": "A demonstration of the method on a count of players, not a statement about any player.",
    "ch4.series.diagnostics": "Change-point fit: R-hat ≤ {rhat}, minimum bulk ESS {ess}, {div} divergent transitions across {t} seasons.",

    "ch4.panel.h3": "Cross-country youth-minutes panel",
    "ch4.panel.design": "For each of the {n_countries} peer countries, the {seasons} average U21 share of domestic-league minutes (x) against the {seasons} average top-9 players per million (y) — one row per country. A Bayesian simple regression, y ~ Normal(α + β·x, σ), weakly informative priors ({chains} chains × {draws} draws {cite_pymc}), answers the between-country question slide 3 asks: does a country with a higher average U21 share also have a deeper pool, on average {cite_bda}. Cross-checked against a plain pooled least-squares slope on the full two-season panel (numpy polyfit, ignoring country structure entirely, {n_boot} percentile-bootstrap resamples — statsmodels is not a dependency here), which should agree in sign. Two seasons per country (previous and metrics; the current season is partial and left out); a peer whose top flight FBref does not track is absent from the panel, which is why n can be below the peer count.",
    "ch4.panel.fig_alt": "Scatter of the panel with the between-country fitted line and its 90 % band.",
    "ch4.panel.bootstrap": "β = {beta} per 10 percentage points of U21 share (90 % HDI {lo}–{hi}), R² = {r2}; OLS on the same {n} country means lands close by, at {ols_means} ({ols_means_lo}–{ols_means_hi}), and the pooled-panel OLS slope agrees in sign at {ols} ({ols_lo}–{ols_hi}). n = {n}; the interval is wide because the panel is small.",
    "ch4.panel.diagnostics": "R-hat ≤ {rhat}, minimum bulk ESS {ess}, {div} divergent transitions.",
    "ch4.panel.within": "A separate check: the same regression, but with a country random intercept fit on the full two-season panel instead of country means. Within-country changes across the two seasons carry no signal — β_within = {beta_within} per 10 percentage points (90 % HDI {lo}–{hi}), n = {n} country-seasons (R-hat ≤ {rhat}, minimum bulk ESS {ess}, {div} divergent transitions; posterior-median country-intercept scale σ_country = {sigma_country}). With only two seasons per country the intercept absorbs almost all of the between-country pattern the fit above isolates, leaving this estimate driven by season-to-season noise alone; reported here as a robustness check, not a second headline.",
    "ch4.panel.note": "Descriptive only: a country's average U21 share and its average per-capita count are shown together because they are the numbers on hand, not because one is claimed to produce the other.",
    "ch4.panel.table.summary": "Panel rows (n = {n})",
    "ch4.panel.th.country": "Country",
    "ch4.panel.th.season": "Season",
    "ch4.panel.th.x": "U21 share",
    "ch4.panel.th.y": "Per million",

    "ch4.gap.h3": "What the gap is made of",
    "ch4.gap.design": "Ridge regression (α = {alpha}, standardised channels, converted back to original units) of top-9 players per million on three channels — U21 share of domestic minutes, domestic league strength (<a href=\"#league-strength\">M2's m_L</a> where the country's top flight is in that model's fitted set, else the UEFA-coefficient multiplier (every country in this run used the model estimate)) and median export age (recent entrants, or the all-time median for a country with none recently) — over the {n} peer countries with data on all three channels, metrics season. For one contrast country at a time, the fitted model's own prediction splits the gap exactly into one term per channel — the linear-model form of the Blinder-Oaxaca wage decomposition {cite_ob}, applied here to a per-capita player count. Three linear channels means this split is Shapley-equivalent: the Shapley value of an additive term in a linear model equals its own coefficient's contribution, so no permutation machinery is implemented. The residual is whatever the three channels do not carry.",
    "ch4.gap.fig_alt": "Horizontal stacked bar per contrast country: three channel contributions plus the residual; whiskers show each channel's bootstrap interval.",
    "ch4.gap.bootstrap": "Bootstrap 90 % intervals on each channel's contribution, {n_boot} resamples of the panel's rows (the model refit on each resample; the home/contrast countries' own values held fixed); the residual itself is not bootstrapped — it is the two countries' own observed counts minus the fitted gap.",
    "ch4.gap.note": "A decomposition of a correlation this panel happens to show, not a causal accounting; with n = {n} and three correlated national-level channels, the shares are indicative, not precise. A channel's share of the gap is only shown when the gap itself is at least {min_gap} players per million — below that, a small denominator can send a share past 100 % in either direction; the contribution itself, in players per million, is always reported.",
    "ch4.gap.th.contrast": "Contrast",
    "ch4.gap.th.channel": "Channel",
    "ch4.gap.th.contribution": "Contribution",
    "ch4.gap.th.share": "Share of gap",
    "ch4.gap.th.interval": "90 % interval",
    "ch4.gap.residual_label": "Residual",
    "ch4.gap.gap_total_label": "Gap (players per million)",

    "ch4.export.h3": "Age at export",
    "ch4.export.design": "For every peer-nationality player (home nation included) whose first top-{topn}-league season lies inside the fetched window and isn't censored (the same censoring rule as \"Where do {adj} players go when they leave?\", reused here) — {n} players, ages {age_min}–{age_max} — age at that season is modelled against league-adjusted production over the player's first one or two top-{topn} seasons. f(age) is a natural cubic spline with knots at 19, 21, 23 and 25 (a plain quadratic below n = 150; the {branch} branch was used here), alongside origin-league strength (the transfer-graph model, <a href=\"#league-strength\">§ League strength</a>), position and a partially pooled country effect {cite_bda}, sampled with NUTS {cite_nuts}, {chains} chains × {draws} draws; every design column and the outcome were standardised before fitting, the youth-minutes panel's own lesson about raw-scale priors on differently-scaled covariates.",
    "ch4.export.branch.spline": "natural cubic spline",
    "ch4.export.branch.quadratic": "quadratic",
    "ch4.export.fig_alt": "Line chart: the fitted age-at-export curve with its 90 % band, home-nation exports as oxblood points against every other peer export in grey, and a rug of every export's age along the axis.",
    "ch4.export.th.age": "Age",
    "ch4.export.th.y": "Expected G+A/90 (median)",
    "ch4.export.th.hdi": "90 % HDI",
    "ch4.export.beta": "β, per one-unit increase in origin-league strength (m_L): {beta} ({lo}–{hi}).",
    "ch4.export.home": "{Adj} exports' own country effect: {home_effect} ({lo}–{hi}); {adj} exports arrive at a median age of {age_home}.",
    "ch4.export.no_strength": "The same model, fit again without origin-league strength: the country-effect scale (σ_n) is {sigma_with} with the league term in the model and {sigma_without} without it — what moves between the two is what the league term is absorbing.",
    "ch4.export.lono": "Leave-one-nation-out: excluding {nation}'s own {n_excluded} exports (n = {n} remaining) and refitting, the 21-vs-24 difference is {diff} ({lo}–{hi}), against {full_diff} in the full fit.",
    "ch4.export.ppc.summary": "Posterior predictive check",
    "ch4.export.ppc.p": "Observed vs. replicated y (mean league-adjusted G+A/90 over the first two top-9 seasons): mean {obs_mean} vs {rep_mean}, sd {obs_sd} vs {rep_sd}, 10th percentile {obs_p10} vs {rep_p10}, 90th percentile {obs_p90} vs {rep_p90}.",
    "ch4.export.diagnostics": "R-hat ≤ {rhat}, minimum bulk ESS {ess}, {div} divergent transitions across {n} players; fit in {runtime} s.",
    "ch4.export.selection": "What this model does not separate: the corpus is not a random sample of players who could have left later. Players who leave earlier tend to be the ones judged ready earliest — a selection effect the age curve mixes with any genuine development effect of arriving young, and this report does not try to tell the two apart.",

    "ch4.validation.h3": "Validation & robustness",
    "ch4.validation.stub": "Each model in this pipeline carries its own validation next to where it is described; this section collects one headline diagnostic from each as it lands. So far:",
    "ch4.validation.m1": "Season-to-season model comparison (M1): rolling-origin evaluation over {n_origins} seasons, pooled RMSE favours {winner} ({rmse} vs {persistence_rmse} for persistence), the Bayesian model's 90 % interval covered {coverage} of observed values.",
    "ch4.validation.m2": "League strength (M2): R-hat ≤ {rhat}, {div} divergent transitions, out-of-sample log predictive density favours \"{oos_winner}\" ({oos_logpd}), Spearman rho = {rho} against the UEFA multipliers.",
    "ch4.validation.m3": "The break and forecast (M4): the break dates to {season} ({prob} posterior) for {nation}, a ×{delta} level change; the plain local level {verb} the naive baseline on MAE ({mae_model} vs {mae_naive}) with {coverage} of the 90 % intervals covering the observed value over {n} rolling-origin backtests.",
    "ch4.validation.verb.beats": "beats",
    "ch4.validation.verb.not_beats": "does not beat",
    "ch4.validation.m4": "The youth-minutes panel (M3): across {n_countries} countries (country means, n = {n}), the between-country slope is {beta} per 10 percentage points of U21 share ({lo}–{hi}), R² = {r2}; a plain pooled OLS slope agrees in sign at {ols} ({ols_lo}–{ols_hi}) — the interval is wide because the panel is small. A within-country check (country-random-intercept fit on the full two-season panel) finds no signal: β_within = {beta_within}.",
    "ch4.validation.m5": "The gap decomposition (M5): ridge fit (α = {alpha}) on n = {n} peer countries; for {contrast}, the residual is {resid} of a {gap} gap — a decomposition of a correlation, not a causal accounting.",
    "ch4.validation.m6": "Age at export (M1 proper): R-hat ≤ {rhat}, {div} divergent transitions across {n} players; β on origin-league strength is {beta}; leaving out {n_excluded} {adj} exports and refitting shifts the 21-vs-24 difference by {shift}.",

    "ch4.related.h3": "Related methods and what was taken from them",
    "ch4.related.intro": "The methods below shaped this report's design. Each entry states what the method is, what this report took from it, and what was left out and why.",
    "ch4.related.novel": "One pairing here has no single citation behind it: the transfer-graph league-strength model (<a href=\"#league-strength\">§ League strength</a>) and the age-at-export curve (<a href=\"#export-age-model\">§ Age at export</a>) are fit independently and joined only through origin-league strength as a covariate — a within-player league-identification model feeding a spline-in-age production curve is, to the author's knowledge, this report's own combination, not drawn whole from any one method below.",
    "ch4.related.shrinkage": "Empirical-Bayes shrinkage of a sparse per-unit rate toward a group mean {cite} · taken: per-90 rates are shrunk toward the league-season median with a K = 10 phantom-match prior before the quality projection (§ Bayesian shrinkage) · left out: the fully hierarchical variance-component estimate the original method also supports, since one shared K fits this corpus's minutes floor well enough for a descriptive report.",
    "ch4.related.hierarchical": "Multilevel (partial-pooling) regression and posterior predictive checking as a model-diagnosis routine {cite} · taken: the league-strength and youth-panel models pool leagues and countries partially rather than fitting each alone or merging them into one, and the league-strength posterior predictive check (§ League strength) compares simulated to observed production · left out: model comparison by WAIC/LOO, since every model here is instead scored on seasons it never trained on (rolling-origin backtests), a stronger check for this report's purpose.",
    "ch4.related.nuts": "The No-U-Turn Sampler, the gradient-based MCMC method PyMC uses by default {cite} · taken: every Bayesian model in this report — league strength, model comparison, the change-point series, the youth panel — is fit with it and diagnosed on R-hat and divergences · left out: variational inference as a faster approximate alternative, since none of the four models is slow enough to need it.",
    "ch4.related.rapm": "Plus-minus and regularised adjusted plus-minus ratings, which isolate a player's contribution from teammates' and opponents' by regression {cite} · taken: the league-strength model's within-player logic — only a mover's own before/after change of league separates their level from the league's scoring environment — follows the same identification idea, applied to leagues rather than teammates · left out: an actual RAPM fit over lineup data, which this corpus's season-level tables (no lineups, no possession data) cannot support.",
    "ch4.related.changepoint": "Bayesian online change-point detection, a sequential method for locating a shift in a data-generating process {cite} · taken: a single unknown break season with a marginalised discrete location parameter, applied here to a short batch series rather than sequentially · left out: the online/sequential setting and multiple change points, since the series in question (one country's Big-5 count per season) is short, fixed, and plausibly has at most one structural shift.",
    "ch4.related.statespace": "The local-level model — a random walk plus noise for a slowly drifting series — in the state-space tradition {cite} · taken: the change-point model (§ Dating the break) is exactly this local level in log space, with one added step change at the break · left out: a local linear trend or seasonal component, since the series is annual and too short for a trend term to be identifiable.",
    "ch4.related.rollingorigin": "Rolling-origin (time-series) cross-validation: refit on data up to each origin, score only on what came after it {cite} · taken: both the model-comparison exercise (§ Three models, one task) and the change-point backtest (§ Dating the break) are scored this way, never on a random split that could leak future seasons into training · left out: expanding-vs-sliding-window variants beyond the single expanding-window scheme, since the corpus's five metrics seasons leave little room to compare schemes.",
    "ch4.related.decomposition": "The Oaxaca–Blinder decomposition, splitting a gap between two groups' means into an explained and an unexplained part via a linear model {cite} · taken: the gap-decomposition exhibit (§ What the gap is made of) splits the per-capita gap into the three measured channels plus a residual the same way · left out: the detailed, coefficient-level decomposition of the explained share, since three channels are few enough to read directly off the coefficients themselves.",
    "ch4.related.clustervalidation": "The silhouette coefficient, a per-point measure of how well a clustering separates its groups {cite} · taken: used to sanity-check the PCA cluster counts per position group and projection before they were fixed (§ Cluster archetypes) · left out: a silhouette sweep reported in the text, since the chosen cluster counts are stable across position groups and projections.",
    "ch4.related.baselines": "Gradient-boosted trees and a small multilayer perceptron, two non-Bayesian machine-learning baselines standard in this kind of comparison {cite} · taken: both sit alongside the persistence, shrinkage and Bayesian models in § Three models, one task, on the same eight features and the same rolling-origin split · left out: hyperparameter search beyond scikit-learn's defaults (plus the MLP's 64/32 hidden layers), since the comparison's point is model family, not a tuned leaderboard.",
    "ch4.related.cies": "CIES Football Observatory's periodic counts of footballers playing outside their home association {cite} · taken: the out-of-sample league-strength check (§ League strength) tracks the same population — players who changed league — though it does not reuse CIES's own counts · left out: CIES's expatriate-share figures as a number quoted in this report, since the per-capita and pathways exhibits already answer the same question from this report's own fetched player tables.",
    "ch4.related.future.h4": "Next steps not attempted",
    "ch4.related.future.embeddings": "Player-season embeddings and graph methods over the transfer network — clubs and moves as a graph, players as nodes with learned representations — are natural next tools (graph neural networks, specifically) for a pool this size, but were not attempted here.",
    "ch4.related.future.tracking": "Event- and tracking-derived features (pressing intensity, progressive carries, expected threat) would sharpen the style axis beyond the five box-score numbers used here, but no tracking data source was available for this corpus.",
    "ch4.refs.h3": "References",

    "ch4.dq.h3": "Data-quality log",
    "ch4.dq.p": "Every wrangling decision that changed a count, with the count. The first block is recomputed on every run; the second is the incident record (dates and counts as recorded at the time).",
    "ch4.dq.col.check": "Check",
    "ch4.dq.col.count": "Count",
    "ch4.dq.col.what": "What it counts",
    "ch4.dq.recorded": "{n} {unit}, recorded",
    "ch4.dq.summary": "{n_checks} recomputed checks · {n_events} recorded incidents",
    "dq.women_filtered.label": "Women's entries filtered",
    "dq.women_filtered.what": "FBref country-page entries dropped for a surname ending in -ová (see Limitations).",
    "dq.namesakes.label": "Namesakes in the pool",
    "dq.namesakes.what": "Active pool players sharing a normalised name (e.g. father and son), disambiguated by club.",
    "dq.no_tables.label": "Pool players without season tables",
    "dq.no_tables.what": "{Adj} professionals on FBref's country page who play in a league without season tables and carry no metrics.",
    "dq.split_seasons.label": "Split-season rows collapsed",
    "dq.split_seasons.what": "Player-season-group rows merged into one after a mid-season transfer (minutes summed, rates minutes-weighted).",
    "dq.nt_unmatched.label": "Unmatched call-up names",
    "dq.nt_unmatched.what": "National-team squad-table names that match no {adj}-eligible row in the feature tables.",
    "dq.missing_born.label": "Missing birth years",
    "dq.missing_born.what": "Season-table rows of nation {code} with no birth year, which cannot form a player_key.",
    "dq.gk_unjoined.label": "Unjoined goalkeeper rows",
    "dq.gk_unjoined.what": "Keeper-page rows with no matching GK row in the season tables on (league, season, team, player_key); dropped from every goalkeeper exhibit.",
    "ch4.lim.h3": "Limitations of this analysis",
    "ch4.repro.h3": "Reproducibility",
    "ch4.repro.p": "The full pipeline is public: <a href=\"{url}\">{url_short}</a>. MIT licence. From a clean clone, <code>uv sync &amp;&amp; make restore-snapshot &amp;&amp; make render</code> renders this report from the committed data snapshot and <code>make pages</code> builds the site; <code>make all</code> refetches everything and runs the whole pipeline. Random seed {seed} for every stochastic step (KMeans). Fetchers cache raw pages and are idempotent; the render step never touches the network.",
    "ch4.repro.bq": "The processed tables also load into BigQuery unchanged: <code><a href=\"{url}/tree/main/infra/bigquery\">infra/bigquery/</a></code> has generated schemas, a <code>bq load</code> script and a key/unit contract for the model-output JSONs the tables don't cover. Run <code>infra/bigquery/load.sh -n &lt;dataset&gt; &lt;nation&gt;</code> to see the load commands without running them.",
    "ch4.built.h3": "How this was built",
    "ch4.built.summary": "Spec → plan → task agents → reviews → ledger · {n_rulings} rulings · {n_tests} tests",
    "ch4.built.p1": "The report was produced with an agentic workflow: a written design spec, an implementation plan of small tasks, a fresh coding agent per task, a spec-compliance and code-quality review after each, a whole-branch review at the end. Every decision the controller made without the author is a dated <em>ruling</em> in a ledger — {n_rulings} across this edition and the last. The author wrote the framing, the cluster reads and the rulings; the agents wrote the code under {n_tests} tests.",
    "ch4.built.flow.spec": "Spec",
    "ch4.built.flow.plan": "Plan",
    "ch4.built.flow.agent": "Task agent",
    "ch4.built.flow.task_review": "Task review",
    "ch4.built.flow.task_review_sub": "spec + quality",
    "ch4.built.flow.fix_rounds": "Fix rounds ≤ {n}",
    "ch4.built.flow.whole_branch_review": "Whole-branch review",
    "ch4.built.flow.deploy": "Deploy",
    "ch4.built.flow.ledger": "Ledger",
    "ch4.built.svg.title": "Build-flow diagram",
    "ch4.built.svg.desc": "Spec, then plan, then one task agent per task, a two-stage task review, up to five fix rounds, a whole-branch review, then deploy; the ledger on the side records every ruling — {n_rulings} so far, across {n_tasks} tasks.",
    "ch4.built.svg.rulings": "rulings: {n}",
    "ch4.built.legend": "Implementers and reviewers: {impl} · controller: {ctrl}.",
    "ch4.built.peer_review": "Reviews are two-stage per task — spec compliance, then code quality — and every review's findings are written into the ledger, not just its verdict: {n_reviews} lines mentioning a review across the {n_tasks} tasks of this edition and the last.",
    "ch4.built.p2": "Spec: <a href=\"{spec}\">design</a> · plan: <a href=\"{plan}\">tasks</a> · ledger: <a href=\"{ledger}\">rulings</a>.",
    "ch4.built.p3": "Every edition's own design spec and ledger:",
    "ch4.built.spec_word": "spec",
    "ch4.built.ledger_word": "ledger",

    # ---- footer
    "foot.kicker": "Built by Barbora Šandová — data &amp; cloud engineer",
    "foot.body": "Tracking-data PoCs for football and hockey. This page is the deliverable: pipeline, models, validation and the report are one repository.",
    "foot.credits": "Photo credits ({n} portraits, Wikimedia Commons)",
    "foot.rendered": "Rendered: {at}",

    # ---- generated: observations
    "obs.1.title": "Per capita: rank {rank} of {n}",
    "obs.1.body": "{cze_n} {adj} players on {season} rosters of the {topn} strongest leagues give {pm} per million inhabitants, rank {rank} of {n}. {top} leads with {top_pm}, {ratio} times the {adj} density",
    "obs.1.above": "; {name} sits one place above with {pm} from {players} players and a population {size}",
    "obs.1.smaller": "{ratio} times smaller",
    "obs.1.larger": "{ratio} times larger",
    "obs.1.below": "Below {nation}: {names}.",
    "obs.1.none_below": "No peer sits below.",
    "obs.2.title": "The largest cohort gap: {group} {cohort}",
    "obs.2.title_empty": "Cohort gaps",
    "obs.2.gap": "{group} {cohort} — {cze} {adj} against a peer median of {peer}",
    "obs.2.body": "Counting {season} top-{topn} players by position group and age cohort and comparing the {adj} count with the median of the other {peers} peer{s}, the {k} largest shortfall{plural} {gaps}. The cohort tables above show the medians behind the counts.",
    "obs.3.title": "Trajectories {previous} → {metrics}: {verdict}",
    "obs.3.stable": "mostly stable",
    "obs.3.mixed": "mixed",
    "obs.3.part": "{group} {n} ({up} up, {stable} stable, {down} down)",
    "obs.3.body": "{n} {adj}-eligible players had at least {min} minutes in both {previous} and {metrics}: {parts}. A move counts as up or down when league-adjusted goals + assists per 90 changed by more than {band}; {stable} of {n} stayed within that band. These are season-over-season deltas, not projections.",

    # ---- generated: card row kickers
    "kicker.highest": "Highest quality-adjusted production",
    "kicker.youngest": "Youngest national-team call-up",
    "kicker.top9": "Most top-9 minutes",
    "kicker.domestic": "Most domestic minutes under 23, no top-9 season yet",
    "kicker.ntcore": "National-team core — most top-9 minutes in the {event} squad",
    "kicker.ntcore_home": "National-team core at home — most domestic-league minutes in the {event} squad",
    "kicker.ntcore_merged": "National-team core — {event} squad: most top-9 minutes, most home-league minutes",
    "kicker.other": "Other rules",

    # ---- generated: limitations
    "lim.leagues.title": "Leagues without metrics",
    "lim.leagues.body": "The pipeline fetches {n_leagues} competitions from FBref. {n_no_tables} of the {n_pool} {adj} professionals found on FBref's country page play in a league without season tables and carry no metrics; they are listed by name and club only.{leagues_note}",
    "lim.features.title": "Free-tier feature set",
    "lim.features.body": "The feature vector is five basic columns per 90 minutes: non-penalty goals, assists, minutes share, age and cards. No expected goals, no progressive passes, no tackles — the rule was one identical vector across every league in the corpus, and only the basic table is available for all of them. Defensive and creative contributions beyond assists are invisible to the map.",
    "lim.nt.title": "National-team flag source",
    "lim.nt.body": "The flag \"called up {nt_years}\" is parsed from Wikipedia squad tables ({nt_events}) and matched on normalised name plus birth year. {n_nt_flagged} of the {n_with_metrics} mapped players carry it. A squad table edit or a name variant can drop a call-up; the flag is a tag, not a cap count.",
    "lim.photos.title": "Photo coverage",
    "lim.photos.body": "{n_photos} of the {n_pool} pool players have a Wikimedia Commons portrait (Wikidata P18, matched on name, citizenship and birth date, occupation filtered to association football player) used on the site. Players without a portrait on the site show initials.",
    "lim.seasons.title": "Season split",
    "lim.seasons.body": "The headline per-capita count and every metric use the complete {metrics} season; trajectories run {previous} → {metrics}; the club on a card is the {current} club (season in progress at build time).",
    "lim.multipliers.title": "League multipliers",
    "lim.multipliers.body": "ClubElo was unreachable at run time, so the multipliers are UEFA association coefficients scaled to the strongest league = {max_multiplier}, and second-tier leagues are set to {tier2_factor} × the first tier of the same country by assumption. The club-strength proxy in chapter II is the club's goals-scored percentile within its league, not an Elo rating. The sensitivity table shows how far a ±20 % error in any one multiplier moves the {adj} ranking.",
    "lim.origins.title": "Export origins from recent entrants only",
    "lim.origins.body": "The origin league of an export is known only when the season before the first top-9 season was fetched: {history_start} onwards for the headline leagues, {coverage_start} onwards for the peer domestic leagues. Origin shares and the recent export age are therefore computed over players whose first top-9 season is {metrics} or {current}; earlier entrants count towards the full export age but not the origin mix, and a first appearance already in {history_start} is censored (the censored share is shown).",
    "lim.identity.title": "Player identity",
    "lim.identity.body": "FBref's season tables carry no player id, so players are joined on normalised name plus birth year across leagues and seasons; two players sharing both would collapse into one. A mid-season transfer produces two club rows that are collapsed into one minutes-weighted row before ranking.",
    "lim.women.title": "Women's entries and the -ová heuristic",
    "lim.women.body": "FBref's country page mixes men's and women's competitions. Entries whose surname ends in -ová were dropped from the pool; a woman with a different surname ending would survive the filter, and a man with that ending would not. The suffix is specific to Czech feminine surnames, so for a nation whose naming convention doesn't use it (English, for one) the filter catches close to none of the contamination it targets; the \"Women's entries filtered\" count in the data-quality log below says how many it caught this run.",
    "lim.scope.title": "No market values, no scouting",
    "lim.scope.body": "Transfer fees, market values, video and scouting reports are outside the public sources used here. The map describes statistical footprints and counts; selection and development decisions require the federation's own data and expertise, which this method does not have.",
    "lim.tracking.title": "No event or tracking data",
    "lim.tracking.body": "Every feature here is a season aggregate from free FBref tables. The author's tracking work lives elsewhere: <a href=\"https://github.com/sandovabarbora/tactical-cz\">tactical-cz</a> (broadcast-video player tracking for Czech football) and the hockey video PoC linked from <a href=\"https://hockey.datasimply.eu\">hockey.datasimply.eu</a>. New columns enter in <code>src/features.py::per90</code> and the feature list in <code>config/feature_definitions.yaml</code>.",

    # ---- generated: sensitivity descriptions
    "sens.baseline": "current multipliers from config/league_quality.yaml",
    "sens.one": "{league} multiplier {sign}20%",
    "sens.all": "every league multiplier {sign}20%",
}
# fmt: on

# English data labels the render passes through `term()`; every one of them
# needs a Czech entry under `terms:` in cs.yaml. Kept here so the completeness
# check can run without loading the data.
TERMS_EN: tuple[str, ...] = (
    "Forwards", "Midfielders", "Defenders",
    "improving", "stable", "declining",
    "domestic league", "stepping-stone league", "top-9 league", "other covered league",
    "domestic", "top-9", "stepping stone", "peer country league", "other",
    "Czechia", "Slovakia", "Austria", "Hungary", "Poland", "Croatia", "Denmark",
    "Switzerland", "Norway",
    "England", "France", "Germany", "Spain", "Italy", "Netherlands", "Portugal", "Belgium",
    "highest quality-adjusted npG+A per 90 among {pos}",
    "youngest national-team call-up among {pos}",
    "most top-9 league minutes among {pos}",
    "most domestic-league minutes among under-23 {pos} without a top-9 season",
    "most top-9 minutes among 2026 FIFA World Cup squad {pos}",
    "most domestic minutes among 2026 FIFA World Cup squad {pos}",
    "destination league multiplier <= the domestic league's multiplier",
    "goals-scored percentile within league",
    "entries", "players", "rows", "names", "leagues", "portraits",
    "most top-9 minutes among home goalkeepers",
    "youngest home goalkeeper with minimum top-9 minutes",
    "U21 minutes", "League strength", "Export age",
)

_DECIMAL = re.compile(r"(?<=\d)\.(?=\d)")
_TEXT_NODE = re.compile(r">([^<]*)<")
_PROTECTED = re.compile(r"<(script|code|style)\b.*?</\1>", re.S)


def load_cs() -> dict[str, dict[str, str]]:
    raw = yaml.safe_load(CS_PATH.read_text(encoding="utf-8")) or {}
    return {"strings": dict(raw.get("strings") or {}), "terms": dict(raw.get("terms") or {})}


def check_complete(cs: dict[str, dict[str, str]], extra_terms: list[str] | tuple[str, ...] = ()) -> None:
    """Raise KeyError listing every English string or term without a Czech entry."""
    missing = sorted(k for k in EN if k not in cs["strings"])
    missing_terms = sorted(t for t in (*TERMS_EN, *extra_terms) if t not in cs["terms"])
    if missing or missing_terms:
        raise KeyError(f"cs.yaml incomplete — strings: {missing} terms: {missing_terms}")
    unknown = sorted(k for k in cs["strings"] if k not in EN)
    if unknown:
        raise KeyError(f"cs.yaml has strings without an English default: {unknown}")


def placeholders(s: str) -> set[str]:
    return set(re.findall(r"(?<!\{)\{([a-z_0-9]+)\}", s))


def _is_auto_name(name: str) -> bool:
    """True for a name auto-injected by `_auto_params` (nation, adj, Adj, code,
    home_league, and any cs_*) -- allowed in either language's string
    regardless of whether the other one also uses it."""
    return name in _AUTO_NAMES or name.startswith("cs_")


def check_placeholders(cs: dict[str, dict[str, str]]) -> list[str]:
    """Keys whose Czech placeholders differ from the English ones (a subset is allowed).

    A Czech string that drops a placeholder is legal (word order, a count
    folded into the sentence) but worth a look, so it is logged by key.
    Auto-injected nation-word names (see `_auto_params`) are exempt from
    this comparison in both directions -- a string in either language may
    use or drop any of them independently of the other.
    """
    bad = []
    for key, en in EN.items():
        cz = cs["strings"].get(key)
        if cz is None:
            continue
        cz_ph = {p for p in placeholders(cz) if not _is_auto_name(p)}
        en_ph = {p for p in placeholders(en) if not _is_auto_name(p)}
        if not cz_ph <= en_ph:
            bad.append(key)
        elif cz_ph < en_ph:
            log.warning("cs.yaml %s drops placeholder(s) %s", key, sorted(en_ph - cz_ph))
    return bad


class Translator:
    """`t(key, **params)` and `term(label)` for one language."""

    def __init__(self, lang: str = "en", cs: dict[str, dict[str, str]] | None = None):
        if lang not in LANGS:
            raise ValueError(f"unknown language {lang!r}")
        self.lang = lang
        self.strings: dict[str, str] = EN
        self.terms: dict[str, str] = {}
        self.auto: dict[str, str] = _auto_params()
        if lang == "cs":
            cs = cs or load_cs()
            check_complete(cs)
            self.strings = cs["strings"]
            self.terms = cs["terms"]

    # -- strings ---------------------------------------------------------
    def raw(self, key: str, **params: Any) -> str:
        """Plain text (no escaping) — for SVG titles, alt texts, generated prose."""
        if key not in EN:
            raise KeyError(f"unknown i18n key {key!r}")
        s = self.strings[key]
        return s.format(**{**self.auto, **params})

    def __call__(self, key: str, **params: Any) -> Markup:
        """HTML-safe: the authored string is trusted, the parameters are escaped."""
        if key not in EN:
            raise KeyError(f"unknown i18n key {key!r}")
        s = self.strings[key]
        merged = {**self.auto, **params}
        safe = {k: (v if isinstance(v, Markup) else escape(v)) for k, v in merged.items()}
        return Markup(s.format(**safe))

    # -- data labels -----------------------------------------------------
    def term(self, label: str) -> str:
        """Translate an English data label; Czech render fails on an unknown one."""
        if self.lang == "en" or not label:
            return label
        if label not in self.terms:
            raise KeyError(f"no Czech term for {label!r}")
        return self.terms[label]

    def term_soft(self, label: str) -> str:
        """Like term(), but an unknown label passes through (proper names)."""
        return self.terms.get(label, label) if self.lang == "cs" else label

    def reason(self, reason: str) -> str:
        """Showcase reasons end in a position code: '… among FW' -> pattern + pos.

        A handful of patterns display a plain metric label instead of the
        raw jargon in the underlying reason string (Task 22 item 9: "highest
        quality-adjusted npG+A per 90 among FW" reads as "highest {metric.prod}
        among FW") -- `_REASON_DISPLAY` maps the pos-generic pattern to the
        i18n key that renders it. The reason string itself (used for card
        grouping and tests) is untouched; this only changes what's shown.
        """
        for pos in ("FW", "MF", "DF"):
            if re.search(rf"\b{pos}\b", reason):
                pattern = re.sub(rf"\b{pos}\b", "{pos}", reason)
                display_key = _REASON_DISPLAY.get(pattern)
                if display_key:
                    return self.raw(display_key, pos=pos, metric=self.strings["metric.prod"])
                return self.term(pattern).format(pos=pos)
        return self.term(reason)

    def sensitivity(self, description: str) -> str:
        if self.lang == "en":
            return description
        m = re.fullmatch(r"(.+) multiplier ([+-])20%", description)
        if m and m.group(1) == "every league":
            return self.raw("sens.all", sign=m.group(2).replace("-", "−"))
        if m:
            return self.raw("sens.one", league=m.group(1), sign=m.group(2).replace("-", "−"))
        if description == EN["sens.baseline"]:
            return self.raw("sens.baseline")
        return self.term(description)

    # -- numbers ---------------------------------------------------------
    def ordinal(self, n: int) -> str:
        if self.lang == "cs":
            return f"{n}."
        if n % 100 in (11, 12, 13):
            return f"{n}th"
        return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"

    def num(self, s: str) -> str:
        """Decimal comma for Czech prose built in Python."""
        return _DECIMAL.sub(",", s) if self.lang == "cs" else s

    def number_word(self, n: int, words: list[str]) -> str:
        """English spells small counts; Czech keeps digits (case-free)."""
        if self.lang == "en" and 0 <= n < len(words):
            return words[n]
        return str(n)


def localize_html_numbers(html: str) -> str:
    """Decimal point -> comma in the text nodes of a Czech page.

    Attributes (style, data-tex, alt) and <script>/<code>/<style> blocks are
    left alone; the page carries no thousands separators, so `(?<=\\d)\\.(?=\\d)`
    is the whole rule.
    """
    keep: list[str] = []

    def protect(m: re.Match) -> str:
        keep.append(m.group(0))
        return f"\x00{len(keep) - 1}\x00"

    out = _PROTECTED.sub(protect, html)
    out = _TEXT_NODE.sub(lambda m: ">" + _DECIMAL.sub(",", m.group(1)) + "<", out)
    return re.sub(r"\x00(\d+)\x00", lambda m: keep[int(m.group(1))], out)
