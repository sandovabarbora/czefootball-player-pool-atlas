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

ROOT_DIR = Path(__file__).resolve().parent.parent
CS_PATH = ROOT_DIR / "config" / "i18n" / "cs.yaml"
LANGS = ("en", "cs")
log = logging.getLogger(__name__)

# fmt: off
EN: dict[str, str] = {
    # ---- head / chrome
    "meta.title": "Czech football · Player pool atlas",
    "meta.description": "Structural benchmark of the Czech professional football player pool against {n} peer countries: per-capita density in Europe's strongest leagues, cohort gaps, PCA atlases by position group, pathways abroad. Descriptive, reproducible, public data only.",
    "skip": "Skip to content",
    "toc.aria": "Report contents",
    "toc.hide": "Hide contents",
    "toc.show": "Show contents",
    "toc.heading": "Contents",
    "toc.q1": "Is the pool thin?",
    "toc.q2": "Where is it thin?",
    "toc.q3": "Youth minutes at home",
    "toc.q4": "Where they go",
    "toc.q5": "How they fare",
    "toc.q6": "World Cup squad",
    "toc.q7": "When the train left",
    "toc.q8": "Norway and Denmark",
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
    "toc.shrinkage": "Bayesian shrinkage",
    "toc.pca": "PCA loadings",
    "toc.sensitivity": "Sensitivity analysis",
    "toc.data_quality": "Data-quality log",
    "toc.limitations": "Limitations",
    "toc.reproducibility": "Reproducibility",
    "toc.how_built": "How this was built",
    "toc.short.benchmark": "Benchmark",
    "toc.short.multipliers": "Multipliers",
    "toc.short.shrinkage": "Shrinkage",
    "toc.short.pca": "PCA",
    "toc.short.sensitivity": "Sensitivity",
    "toc.short.limitations": "Limitations",

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
    "hero.sublead.gap": "The largest cohort gap is in <strong>{group} aged {cohort}</strong>: {cze_n} Czech player{s} in the top-{topn} leagues against a peer median of {peer}.",
    "hero.sublead.export": "A recent Czech export first reached a top-{topn} roster at a median age of {cze}; a Danish one at {den}.",
    "hero.sublead.close": "Built from FBref, Wikipedia and Wikidata. Czechia is the worked example; the pipeline takes a nationality code and a peer set. Football people recognise these numbers player by player; there is no place where they are aggregated.",
    "hero.footnote": "* {n} players with FBref nationality CZE on {season} rosters of the UEFA top-{topn} leagues ÷ {pop} M inhabitants (Eurostat 2024); peer countries computed the same way. <a href=\"#methodology\">Methodology</a>.",

    # ---- slides (Task 13b): nine questions between the hero and "for a
    # federation", each q (h2) / a (one sentence, headline number in
    # <strong>) / proof (one exhibit, markup in the template) / how (mono
    # sourcing line, shared "How we know" label below)
    "slide.how_label": "How we know",
    "slide.1.q": "Is the Czech pool thin?",
    "slide.1.a": "Czechia ranks <strong>{rank} of {n}</strong> countries at {pm} per million; {top} leads at {top_pm}.",
    "slide.1.how": "Distinct players with ≥ {min} minutes on {season} rosters of the {topn} strongest leagues ÷ population (Eurostat 2024); every country counted the same way.",
    "slide.2.q": "Where exactly is it thin?",
    "slide.2.a": "The largest cohort gap: <strong>{group} aged {cohort}</strong>, {cze} Czech players vs a peer median of {peer}.",
    "slide.2.how": "Age at season start; cohorts U22 / 23–25 / 26–29 / 30+; ≥ {min} minutes.",
    "slide.3.q": "Do young players get minutes at home?",
    "slide.3.a": "U21 share of domestic-league minutes <strong>{cze_pct} %</strong> vs {best_name} {best_pct} % (best peer).",
    "slide.3.how": "Share of all league minutes played by players aged ≤ 21 at season start, {season}, per domestic top flight.",
    "slide.4.q": "Where do Czech players go when they leave?",
    "slide.4.a": "<strong>{abroad} of {total}</strong> play abroad; {top9_pct} % in the {topn} strongest leagues, {sideways_pct} % moved sideways (to a league no stronger than the Czech one).",
    "slide.4.how": "Destination league of every Czech-eligible player's {season} row; sideways = destination multiplier ≤ Czech league multiplier.",
    "slide.5.q": "How do they fare there?",
    "slide.5.a": "Czech exports keep <strong>{cze} %</strong> of their club's minutes ({rank} of {n}).",
    "slide.5.how": "Median share of club minutes for players abroad, per country of origin.",
    "slide.6.q": "What is the World Cup squad built from?",
    "slide.6.a": "<strong>{cze_pct} %</strong> of the {event} squad plays in the {topn} strongest leagues; {best_name} {best_pct} %.",
    "slide.6.how": "Wikipedia squad lists matched to {season} league rows; tier = league of the most-minutes row.",
    "slide.7.q": "When did the train leave?",
    "slide.7.a": "Czech players with ≥ {min} minutes in the Big-5 leagues peaked at <strong>{peak_n}</strong> in {peak_season}, fell to {low_n} in {low_season}, {last_n} in {last_season}.",
    "slide.7.how": "FBref Big-5 player tables {first_season} → {last_season}; peers on the same rule; the golden-generation names are the most-minutes Czech players of each peak season: {golden}.",
    "slide.7.alt": "Line chart: Czech players with at least {min} minutes in the Big-5 leagues, {start} to {end}, against eight peer countries; a lower panel shows per-million rates for Czechia, Denmark and Croatia.",
    "slide.8.q": "How do Norway and Denmark do it?",
    "slide.8.a": "On the same six numbers Norway gives U21 players <strong>{nor_u21} %</strong> of domestic minutes against {cze_u21} % and sends {nor_top9} % of its squad to the {topn} strongest leagues against {cze_top9} %.",
    "slide.8.how": "Same definitions, same seasons; a comparison, not a causal claim.",
    "slide.9.q": "Who are the players?",
    "slide.9.a": "<strong>{n} cards</strong> chosen by six rules.",
    "slide.9.how": "{season} FBref, Wikipedia and Wikidata rows joined by name and birth year; six selection rules, applied in order — see below.",

    # ---- slide 2 proof: compact cohort-gap table (top 5 rows)
    "cohortgap.th.group": "Group",
    "cohortgap.th.cohort": "Cohort",
    "cohortgap.th.cze": "CZE",
    "cohortgap.th.peer": "Peer median",

    # ---- slide 8 proof: table.peer-compare (CZE / NOR / DEN, six numbers + Big-5 count now)
    "peer_compare.aria": "Czechia, Norway and Denmark on six same-definition pathway numbers",
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
    "fed.pathways.title": "Pathways",
    "fed.pathways.body": "Youth minutes at home, export age and route, how exports fare, where they land — six exhibits.",
    "fed.squad.title": "Tournament squad lens",
    "fed.squad.body": "A named squad by league tier, minutes and age, next to the peers at the same tournament.",
    "fed.models.title": "Models, validated",
    "fed.models.body": "Shrinkage, league multipliers with a sensitivity table, cluster archetypes, analogs — every number recomputed each run; data-quality log and review ledger in the repo.",
    "fed.note": "Run for England: <code>nation: ENG</code>, a peer set (e.g. FRA · GER · ESP · ITA · NED · POR · BEL), the same league list. Event or tracking features enter as extra columns of the feature vector; outputs are flat parquet that loads into BigQuery unchanged.",

    # ---- plain-language metric labels (used everywhere outside chapter IV;
    # chapter IV keeps "npG+A/90 q" and explains it once)
    "metric.prod": "goals + assists per 90, league-adjusted",
    "metric.prod.short": "G+A / 90 adj.",

    # ---- chapter I
    "ch1.benchmark.h3": "Structural benchmark vs peer countries",
    "ch1.benchmark.p": "Football intuition recognises the Czech pool player by player. <strong>Its structural position among the peer countries needs an aggregation nobody holds in one place.</strong> Three numbers below that are usually not collected together.",
    "ch1.capita.aria": "Per-capita density of top-league players by country",
    "ch1.heatmap.alt": "Heatmap of the international cohort benchmark: {n} countries by position group and age cohort, {season} season; the Czech row is outlined.",
    "ch1.heatmap.caption": "Median non-penalty goals + assists per 90 by country, position group and age cohort, {season}; the outlined row is Czechia.",
    "ch1.heatmap.note": "Each cell: player count and the median value; rows ordered by per-capita rank, Czechia highlighted.",
    "ch1.cohorts.h4": "Cohort gaps — {group}",
    "ch1.cohorts.th": "Cohort",
    "ch1.cohorts.none": "no player",
    "ch1.cohorts.note": "* Count and median npG+A per 90 of players with the country's nationality in a top-{topn} league, {season}, at least {min} minutes; cohort by age at the season's calendar turn (start year + 1 − birth year). {shown} of the {n} countries are shown; the heatmap above carries all of them. Largest Czech shortfalls against the peer median count: {gaps}.",
    "ch1.cohorts.gap_item": "{group} {cohort} ({cze} vs {peer})",
    "ch1.atlas.alt": "Two-panel atlas of {group} {season} in PCA projection. Left panel: style map without league multipliers; right panel: quality-adjusted map. Grey points are the whole corpus of {corpus} players; coloured points are the {czech} Czech-eligible players by cluster; oxblood rings mark the {nt} with a national-team call-up {nt_years}.",
    "ch1.atlas.caption": "Atlas of {group} {season} in both projections: {czech} Czech-eligible players in colour against a corpus of {corpus}. Oxblood rings mark the national-team pool (call-up {nt_years}, {nt} players).",
    "ch1.observations.h3": "Observations",
    "ch1.clusters.h3": "Cluster archetypes (style projection)",
    "ch1.clusters.p": "Clusters are fitted on the whole corpus of {season} player-seasons and read here through their Czech members. The label describes the cluster's median footprint; the count is Czech members of the corpus cluster; names are the Czech members with the most minutes.",
    "ch1.clusters.meta": "{n} Czech of {corpus} · NT pool {nt} · median born {born}",
    "ch1.clusters.medians": "Corpus medians: {npg} non-penalty goals and {ast} assists per 90, {share} of the club's minutes, age {age}, {cards} cards per 90.",
    "ch1.clusters.tactical": "Tactical read",
    "ch1.traj.h3": "Trajectories {previous} → {metrics} (Czech-eligible, ≥ {min} minutes in both seasons)",
    "ch1.traj.p": "Season-over-season change in goals + assists per 90, league-adjusted. A move counts as up or down beyond ± {band}; everything inside that band is stable and not listed.",
    "ch1.traj.h4": "{group} — {n} players: {up} up, {stable} stable, {down} down",
    "ch1.traj.up": "Moving up &middot; {metric}",
    "ch1.traj.down": "Moving down &middot; {metric}",
    "ch1.traj.th.player": "Player",
    "ch1.traj.th.league": "League",
    "ch1.traj.th.min": "Min {previous} / {metrics}",
    "ch1.traj.th.delta": "Change",
    "ch1.traj.none_up": "No Czech player moved up beyond the band.",
    "ch1.traj.none_down": "No Czech player moved down beyond the band.",

    # ---- chapter II
    "ch2.framing": "Four exhibits comparing Czechia with {n} peer countries: youth exposure at home, export route, how exports fare, and who made it.",
    "ch2.a.h3": "Exhibit A — youth exposure at home",
    "ch2.a.p": "Share of a domestic league's total minutes played by its own nationals aged 21 or under, {season}.",
    "ch2.a.aria": "Share of domestic-league minutes played by own under-21 nationals",
    "ch2.a.nodata": "league not on FBref",
    "ch2.a.note": "* Σ minutes of players with the league country's nationality and age ≤ 21 at the season's start ÷ Σ minutes of all players in the league, {season}. Under-23 shares: {u23}. A league without a bar is not covered by FBref.",
    "ch2.b.h3": "Exhibit B — export route",
    "ch2.b.p": "For every peer-country player on a {current} top-{topn} roster: the age at the first top-{topn} season (full roster, and recent entrants only) and, for recent entrants, the league of the season before it.",
    "ch2.b.cze": "Czech exports: {n} players, median export age {age} (recent entrants {n_recent}, median {age_recent}), {domestic} of the recent ones straight from the Czech First League*.",
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
    "ch2.d.p": "Goals + assists per 90, league-adjusted, in {season} by the tier of the player's own league: domestic, stepping stone, top-{topn}, or another covered league. Czech count and median against the median of the peer countries' values.",
    "ch2.d.summary": "Profile table by tier and position group",
    "ch2.d.th.tier": "Tier",
    "ch2.d.th.group": "Group",
    "ch2.d.th.cze_n": "CZE n",
    "ch2.d.th.cze_median": "CZE median",
    "ch2.d.th.peer_n": "Peer median n",
    "ch2.d.th.peer_median": "Peer median",
    "ch2.d.note": "* Tier = the league of the player's own {season} season. Peer median n and peer median are medians across the peer countries present in that tier and group; a tier a country has no player in is absent, not zero.",
    "ch2.e.h3": "Exhibit E — where Czech exports go",
    "ch2.e.p": "Of the {total} mapped Czech players, {abroad} play outside the Czech First League.",
    "ch2.e.aria": "Czech players abroad by destination bucket",
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

    # ---- chapter III
    "ch3.cards.rules.summary": "How the {n} cards were chosen",
    "ch3.cards.rules": "Why these cards: one card per position group per rule, applied in this order — (a) highest quality-adjusted npG+A per 90, (b) youngest national-team call-up, (c) most top-9 minutes among the {event} squad, (d) most domestic-league minutes among the {event} squad, (e) most top-9 minutes, (f) most domestic minutes under 23 without a top-9 season. A player already chosen by an earlier rule falls through to the next name, so a later row can show the second name by its measure. Rows group the six rules; the national-team core row holds two of them.",
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
    "pi.framing": "Every Czech-eligible player with a complete {season} season in a covered league — {n} players — with the numbers behind the atlases. Names with a card link to it.",
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
    "ch4.sources.fbref": "<strong>FBref</strong> (via <code>soccerdata</code>): player season tables (standard, playing time) for the {topn} headline leagues, the Czech First League, the peer domestic leagues and the German second tier; the country page \"Players from Czechia\" for pool discovery; the nationality column for peer counts",
    "ch4.sources.wikipedia": "<strong>Wikipedia</strong>: national-team squad tables ({events}) for the call-up flag",
    "ch4.sources.wikidata": "<strong>Wikidata / Wikimedia Commons</strong>: player portraits (P18) matched on name, citizenship and date of birth; credits in the footer",
    "ch4.sources.uefa": "<strong>UEFA association coefficients</strong> (via Wikipedia) as the league-strength source, ClubElo being unreachable at run time",
    "ch4.sources.eurostat": "<strong>Eurostat</strong>: population estimates, 2024",
    "ch4.mult.h3": "League multipliers (quality projection)",
    "ch4.mult.th.league": "League",
    "ch4.mult.th.value": "Multiplier",
    "ch4.mult.method": "Method: <code>{method}</code>. {source} The sensitivity analysis below shows the ranking's robustness to ±20 % on any one multiplier.",
    "ch4.shrink.h3": "Bayesian shrinkage",
    "ch4.shrink.p1": "Per-90 rates of players with few minutes are shrunk towards the median of their league and season (players with at least {phantom} minutes) using the empirical Bayes formula, with K = 10 phantom matches expressed as {phantom} minutes:",
    "ch4.shrink.formula": "shrunk_rate = (events + K × league_median) / (minutes / 90 + K), &nbsp; K = 10",
    "ch4.shrink.tex": "\\text{{shrunk rate}} = \\dfrac{{\\text{{events}} + K \\cdot \\text{{league median}}}}{{\\text{{minutes}} / 90 + K}},\\qquad K = 10",
    "ch4.shrink.p2": "At {min} minutes (the inclusion floor) the league median carries {weight} of the weight; at {phantom} minutes the player's own rate and the median weigh the same. Minutes share and age are not shrunk.",
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
    "ch4.sens.p": "For each scenario the quality-adjusted ranking of Czech-eligible players within each position group was recomputed and compared with the baseline; \"top-10\" is the union of the {groups} groups' own top tens ({base} players at baseline). Of the {n} scenarios, {zero} change nobody in that set; the largest churn is {churn}{worst}*.",
    "ch4.sens.worst": " ({description}, mean rank shift {delta} in the top twenty)",
    "ch4.sens.th.scenario": "Scenario",
    "ch4.sens.th.description": "Description",
    "ch4.sens.th.overlap": "Top-10 overlap",
    "ch4.sens.th.churn": "Top-10 churn",
    "ch4.sens.th.delta": "Mean Δ rank (top 20)",
    "ch4.sens.note": "* Churn = baseline top-10 members that leave the set under the scenario; mean Δ rank = mean absolute rank change over the baseline top-20 union. Scenarios: baseline, every league ±20 % on its own, and all leagues ±20 % at once.",
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
    "dq.no_tables.what": "Czech professionals on FBref's country page who play in a league without season tables and carry no metrics.",
    "dq.split_seasons.label": "Split-season rows collapsed",
    "dq.split_seasons.what": "Player-season-group rows merged into one after a mid-season transfer (minutes summed, rates minutes-weighted).",
    "dq.nt_unmatched.label": "Unmatched call-up names",
    "dq.nt_unmatched.what": "National-team squad-table names that match no Czech-eligible row in the feature tables.",
    "dq.missing_born.label": "Missing birth years",
    "dq.missing_born.what": "Season-table rows of nation CZE with no birth year, which cannot form a player_key.",
    "ch4.lim.h3": "Limitations of this analysis",
    "ch4.repro.h3": "Reproducibility",
    "ch4.repro.p": "The full pipeline is public: <a href=\"{url}\">{url_short}</a>. MIT licence. From a clean clone, <code>uv sync &amp;&amp; make restore-snapshot &amp;&amp; make render</code> renders this report from the committed data snapshot and <code>make pages</code> builds the site; <code>make all</code> refetches everything and runs the whole pipeline. Random seed {seed} for every stochastic step (KMeans). Fetchers cache raw pages and are idempotent; the render step never touches the network.",
    "ch4.built.h3": "How this was built",
    "ch4.built.summary": "Spec → plan → task agents → reviews → ledger · {n_rulings} rulings · {n_tests} tests",
    "ch4.built.p1": "The report was produced with an agentic workflow: a written design spec, an implementation plan of small tasks, a fresh coding agent per task, a spec-compliance and code-quality review after each, a whole-branch review at the end. Every decision the controller made without the author is a dated <em>ruling</em> in a ledger — {n_rulings} for the first edition. The author wrote the framing, the cluster reads and the rulings; the agents wrote the code under {n_tests} tests.",
    "ch4.built.flow.spec": "Spec",
    "ch4.built.flow.plan": "Plan",
    "ch4.built.flow.agent": "Task agent",
    "ch4.built.flow.review": "Reviews",
    "ch4.built.flow.ledger": "Ledger",
    "ch4.built.p2": "Spec: <a href=\"{spec}\">design</a> · plan: <a href=\"{plan}\">tasks</a> · ledger: <a href=\"{ledger}\">rulings</a>.",

    # ---- footer
    "foot.kicker": "Built by Barbora Šandová — data &amp; cloud engineer",
    "foot.body": "Tracking-data PoCs for football and hockey. This page is the deliverable: pipeline, models, validation and the report are one repository.",
    "foot.credits": "Photo credits ({n} portraits, Wikimedia Commons)",
    "foot.rendered": "Rendered: {at}",

    # ---- generated: observations
    "obs.1.title": "Per capita: rank {rank} of {n}",
    "obs.1.body": "{cze_n} Czech players on {season} rosters of the {topn} strongest leagues give {pm} per million inhabitants, rank {rank} of {n}. {top} leads with {top_pm}, {ratio} times the Czech density",
    "obs.1.above": "; {name} sits one place above with {pm} from {players} players and a population {size}",
    "obs.1.smaller": "{ratio} times smaller",
    "obs.1.larger": "{ratio} times larger",
    "obs.1.below": "Below Czechia: {names}.",
    "obs.1.none_below": "No peer sits below.",
    "obs.2.title": "The largest cohort gap: {group} {cohort}",
    "obs.2.title_empty": "Cohort gaps",
    "obs.2.gap": "{group} {cohort} — {cze} Czech against a peer median of {peer}",
    "obs.2.body": "Counting {season} top-{topn} players by position group and age cohort and comparing the Czech count with the median of the other {peers} peer{s}, the {k} largest shortfall{plural} {gaps}. The cohort tables above show the medians behind the counts.",
    "obs.3.title": "Trajectories {previous} → {metrics}: {verdict}",
    "obs.3.stable": "mostly stable",
    "obs.3.mixed": "mixed",
    "obs.3.part": "{group} {n} ({up} up, {stable} stable, {down} down)",
    "obs.3.body": "{n} Czech-eligible players had at least {min} minutes in both {previous} and {metrics}: {parts}. A move counts as up or down when league-adjusted goals + assists per 90 changed by more than {band}; {stable} of {n} stayed within that band. These are season-over-season deltas, not projections.",

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
    "lim.leagues.body": "The pipeline fetches {n_leagues} competitions from FBref; the Czech second tier and the Slovak top flight are not on FBref at all. {n_no_tables} of the {n_pool} Czech professionals found on FBref's country page play in a league without season tables and carry no metrics; they are listed by name and club only. Slovakia's exhibits in chapter II therefore rest on its players abroad.",
    "lim.features.title": "Free-tier feature set",
    "lim.features.body": "The feature vector is five basic columns per 90 minutes: non-penalty goals, assists, minutes share, age and cards. No expected goals, no progressive passes, no tackles — the rule was one identical vector across every league in the corpus, and only the basic table is available for all of them. Defensive and creative contributions beyond assists are invisible to the map.",
    "lim.nt.title": "National-team flag source",
    "lim.nt.body": "The flag \"called up {nt_years}\" is parsed from Wikipedia squad tables ({nt_events}) and matched on normalised name plus birth year. {n_nt_flagged} of the {n_with_metrics} mapped players carry it. A squad table edit or a name variant can drop a call-up; the flag is a tag, not a cap count.",
    "lim.photos.title": "Photo coverage",
    "lim.photos.body": "{n_photos} of the {n_pool} pool players have a Wikimedia Commons portrait (Wikidata P18, matched on name, citizenship and birth date, occupation filtered to association football player) used on the site. Players without a portrait on the site show initials.",
    "lim.seasons.title": "Season split",
    "lim.seasons.body": "The headline per-capita count and every metric use the complete {metrics} season; trajectories run {previous} → {metrics}; the club on a card is the {current} club (season in progress at build time).",
    "lim.multipliers.title": "League multipliers",
    "lim.multipliers.body": "ClubElo was unreachable at run time, so the multipliers are UEFA association coefficients scaled to the strongest league = {max_multiplier}, and second-tier leagues are set to {tier2_factor} × the first tier of the same country by assumption. The club-strength proxy in chapter II is the club's goals-scored percentile within its league, not an Elo rating. The sensitivity table shows how far a ±20 % error in any one multiplier moves the Czech ranking.",
    "lim.origins.title": "Export origins from recent entrants only",
    "lim.origins.body": "The origin league of an export is known only when the season before the first top-9 season was fetched: {history_start} onwards for the headline leagues, {coverage_start} onwards for the peer domestic leagues. Origin shares and the recent export age are therefore computed over players whose first top-9 season is {metrics} or {current}; earlier entrants count towards the full export age but not the origin mix, and a first appearance already in {history_start} is censored (the censored share is shown).",
    "lim.identity.title": "Player identity",
    "lim.identity.body": "FBref's season tables carry no player id, so players are joined on normalised name plus birth year across leagues and seasons; two players sharing both would collapse into one. A mid-season transfer produces two club rows that are collapsed into one minutes-weighted row before ranking.",
    "lim.women.title": "Women's entries and the -ová heuristic",
    "lim.women.body": "FBref's country page mixes men's and women's competitions. Entries whose surname ends in -ová were dropped from the pool; a woman with a different surname ending would survive the filter, and a man with that ending would not.",
    "lim.scope.title": "No market values, no scouting",
    "lim.scope.body": "Transfer fees, market values, video and scouting reports are outside the public sources used here. The map describes statistical footprints and counts; selection and development decisions require the federation's own data and expertise, which this method does not have.",
    "lim.tracking.title": "No event or tracking data",
    "lim.tracking.body": "Every feature here is a season aggregate from free FBref tables. The author's tracking work lives elsewhere: <a href=\"https://github.com/sandovabarbora/tactical-cz\">tactical-cz</a> (broadcast-video player tracking for Czech football) and the hockey video PoC linked from <a href=\"https://hockey.datasimply.eu\">hockey.datasimply.eu</a>.",

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
    "highest quality-adjusted npG+A per 90 among {pos}",
    "youngest national-team call-up among {pos}",
    "most top-9 league minutes among {pos}",
    "most domestic-league minutes among under-23 {pos} without a top-9 season",
    "most top-9 minutes among 2026 FIFA World Cup squad {pos}",
    "most domestic minutes among 2026 FIFA World Cup squad {pos}",
    "destination league multiplier <= the domestic league's multiplier",
    "goals-scored percentile within league",
    "entries", "players", "rows", "names", "leagues", "portraits",
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


def check_placeholders(cs: dict[str, dict[str, str]]) -> list[str]:
    """Keys whose Czech placeholders differ from the English ones (a subset is allowed).

    A Czech string that drops a placeholder is legal (word order, a count
    folded into the sentence) but worth a look, so it is logged by key.
    """
    bad = []
    for key, en in EN.items():
        cz = cs["strings"].get(key)
        if cz is None:
            continue
        cz_ph, en_ph = placeholders(cz), placeholders(en)
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
        return s.format(**params) if params else s.replace("{{", "{").replace("}}", "}")

    def __call__(self, key: str, **params: Any) -> Markup:
        """HTML-safe: the authored string is trusted, the parameters are escaped."""
        if key not in EN:
            raise KeyError(f"unknown i18n key {key!r}")
        s = self.strings[key]
        if not params:
            return Markup(s.replace("{{", "{").replace("}}", "}"))
        safe = {k: (v if isinstance(v, Markup) else escape(v)) for k, v in params.items()}
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
        """Showcase reasons end in a position code: '… among FW' -> pattern + pos."""
        for pos in ("FW", "MF", "DF"):
            if re.search(rf"\b{pos}\b", reason):
                return self.term(re.sub(rf"\b{pos}\b", "{pos}", reason)).format(pos=pos)
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
