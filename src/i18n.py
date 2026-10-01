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
    "meta.description": "The {adj} professional football player pool against {n} peer countries: players per head in Europe's top-ranked leagues, cohort counts, youth minutes at home, moves abroad and the national-team squad. Exploratory and descriptive, from public data; not pre-registered.",
    "skip": "Skip to content",
    "toc.aria": "Report contents",
    "toc.hide": "Hide contents",
    "toc.show": "Show contents",
    "toc.heading": "Contents",
    "toc.q1": "Players per million",
    "toc.q2": "Cohort counts",
    "toc.q3": "Youth minutes at home",
    "toc.q4": "Destinations abroad",
    "toc.q4b": "Arrival age and output",
    "toc.q5": "Minutes share abroad",
    "toc.q6": "National-team squad by tier",
    "toc.q7": "Big-5 count and its steps",
    "toc.q8": "{a} and {b}",
    "toc.q8b": "Goalkeepers",
    "toc.q8c": "Gap decomposition",
    "toc.q9": "Showcase cards and the pool",
    "toc.q10": "Change since last season",
    "toc.autumn": "This autumn",
    "toc.explore": "Explore the data",
    "toc.benchmark": "Benchmark vs peer countries",
    "toc.clusters": "Cluster archetypes",
    "toc.trajectories": "Trajectories",
    "toc.pathways": "Five pathway measures",
    "toc.analogs": "Historical analogs",
    "toc.players": "Player index",
    "toc.methodology": "Methodology, data and limitations",
    "toc.multipliers": "League multipliers",
    "toc.strength": "League strength",
    "toc.compare": "Five methods, one task, five seasons",
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
    "toc.tracking": "What tracking data would add",
    "toc.glossary": "Glossary",
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
    "toc.short.tracking": "Tracking",
    "toc.short.glossary": "Glossary",
    "toc.short.references": "References",

    # ---- masthead (first screen: same pitch as the hero kicker/lead below it)
    "mast.kicker": "Research · Player pool atlas · public data",
    "mast.title": "Atlas of the <em>player pool</em>",
    "mast.subtitle": "One country's professional player pool measured against peer countries from public data: players per head in Europe's top-ranked leagues, youth minutes at home, moves abroad and the national-team squad.",
    "mast.pool": "Pool",
    "mast.pool_value": "<strong>{n}</strong> players",
    "mast.with_metrics": "With {season} metrics",
    "mast.nt": "NT call-up {nt_years}",
    "mast.facts": "{n_leagues} leagues · {n_seasons} seasons · {n_tests} automated tests · every number computed from the run · one registered forecast",

    # ---- hero
    "hero.stamp.report": "Report",
    "hero.stamp.atlas": "Atlas · {season}",
    "hero.stamp.edition": "first edition · MIT",
    "hero.stamp.aria": "Document identification",
    "hero.kicker": "Research · Player pool atlas, {adj} edition · {season}",
    "hero.h2": "{Adj} players in Europe's {topn} top-ranked leagues per million inhabitants, {season}",
    "hero.finding": "Per head, {nation} ranks {rank} of {n}.",
    "hero.finding.lead": "Beside that count sit",
    "hero.finding.youth": "{per_club} regular under-21 starters per club at home against {best_per_club} in {best}",
    "hero.finding.move": "a median age of {age} at the first season with real playing time in a foreign league (n = {n})",
    "hero.finding.break": "a most probable {kind} in the Big-5 count in {season} (posterior {prob}; level ×{delta}, 90 % HDI {lo}–{hi})",
    "hero.path": "The findings, the five pathway measures and the one-page brief summarise the atlas; each question page holds the evidence, and the methodology page the data, limitations and references.",
    "hero.unit": "players per million in Europe’s {topn} top leagues, {season}",
    "hero.lead": "How one country’s professional pool compares with its peers, where its players move abroad and which leagues the national-team squad plays in, computed from public data on every run.",
    "hero.sublead.gap": "The largest cohort gap is in <strong>{group} aged {cohort}</strong>: {cze_n} {adj} player{s} in the top-{topn} leagues against a peer median of {peer}.",
    "hero.sublead.export": "A recent {adj} export (first top-{topn} season in the last two seasons) first reached a top-{topn} roster at a median age of {cze} (n = {n_cze}); one from {b} at {den} (n = {n_den}).",
    "hero.sublead.close": "Built from FBref, Wikipedia and Wikidata. {nation} is the worked example; the pipeline takes a nationality code and a peer set.",
    "hero.footnote": "* {n} players who appeared (any minutes), per {pop} M inhabitants; an administrative count. <a href=\"#methodology\">Methodology</a>.",

    # ---- quickread (Task 25a): the 60-second opener, four tiles between the
    # hero and the slides — each tile's figure is typed in the template, its
    # line comes from here; the closing note points at the eleven slides below
    "quickread.1": "per million inhabitants — {rank} of {n} peer countries",
    "quickread.2": "largest cohort gap: {group} aged {cohort}, against a peer median of {peer} (administrative count)",
    "quickread.3": "of the {event} squad in the top-{topn} leagues ({n_top9} of {n}; administrative count); best of the {n_peers} peers at the tournament {best_pct} %",
    "quickread.4": "most probable season of the {kind} in the Big-5 count (posterior {break_prob}; level ×{delta}, 90 % HDI {lo}–{hi})",
    "quickread.note": "Each question page holds the evidence for these numbers.",
    "quickread.glossary_note": "Terms used on this page are explained in the <a href=\"#glossary\">glossary</a>.",

    # ---- why the train left (Task 26A): a five-stage funnel right after the
    # 60-second opener, home nation next to the two comparison countries
    # used throughout the report. Every number is reused from elsewhere in
    # this context except the club-breadth, league-age and first-move-abroad
    # figures, which are new (Task 26B).
    "why_funnel.h2": "Five pathway measures: {nation}, {a} and {b}, {season}",
    "why_funnel.lead": "Five measures, from youth minutes at home to players in Europe’s top-ranked leagues, for {adj} football and the two comparison countries used throughout the atlas. Each links to the page with the full evidence. The order follows a player’s path; it is not a causal chain.",
    "why_funnel.stage1.line": "Playing time for under-21 nationals in the country’s own top league.",
    "why_funnel.stage1.metric1": "Share of league minutes that went to players aged 21 or under",
    "why_funnel.stage1.metric2": "Clubs that gave those young players more than a tenth of their own playing time",
    "why_funnel.stage1.metric3": "Under-21 nationals who were regular starters, per club in the league",
    "why_funnel.regulars_cell": "{per_club} per club ({n} players)",
    "why_funnel.stage1.note": "They are not used mainly as late substitutes: {starts} % of the league’s starts went to them against {minutes} % of its minutes, and a starting under-21 was on the pitch for a median {mn} minutes against the league’s {league_mn}.",
    "why_funnel.stage1.note_early": "{starts} % of the league’s starts went to them against {minutes} % of its minutes, so they start about as often as they play at all; in a start they played a median {mn} minutes against the league’s {league_mn}.",
    "why_funnel.stage1.bound": "This share is a floor. FBref records no nationality for part of this league\u2019s rows, and every \u201cown nationals\u201d share counts those players as foreign while keeping their minutes in the total, so the true figure lies between {lo} % and {hi} % \u2014 an error that moves this country\u2019s number and almost none of its peers\u2019 (see the data-quality log).",
    "why_funnel.take_one_thing.note": "It describes associations across {n} countries and does not say what would change the gap.",
    "why_funnel.stage1.bound_starts": "The same floor applies to the share of starts.",
    "why_funnel.stage1.threshold": "The regular-starter line is drawn at ten starts; at five it is {five} per club, at fifteen {fifteen} (ten: {ten}).",
    "why_funnel.breadth_cell": "{above} of {total} clubs",
    "why_funnel.stage2.line": "The age profile of the home league.",
    "why_funnel.stage2.metric1": "Average age of a minute played in the league",
    "why_funnel.stage2.metric2": "Share of league minutes that went to players aged 30 or over",
    "why_funnel.stage3.line": "Age at the first season with real playing time in a foreign league.",
    "why_funnel.stage3.metric1": "Median age at the first season with real playing time in a foreign league, over the players abroad today",
    "why_funnel.stage3.age_cell": "{age} years",
    "why_funnel.stage3.n_cell": "({n} players)",
    "why_funnel.stage4.line": "Moves abroad to a league no stronger than the home league.",
    "why_funnel.stage4.metric1": "Share of players abroad in a league no stronger than their own (UEFA-coefficient multiplier)",
    "why_funnel.stage5.line": "Players in Europe’s top-ranked leagues per million people.",
    "why_funnel.stage5.metric1": "Players in Europe's top-ranked leagues, for every million people",
    "why_funnel.stage5.break": "The change-point model’s most probable season for a {kind} in the count of {adj} players in the Big-5 is {season} (posterior {prob}), a level change of ×{delta} (90 % HDI {lo}–{hi}).",
    "why_funnel.caveat.h3": "What this does not show",
    "why_funnel.caveat.1": "Money: transfer fees, wages and academy budgets play no part in any number above.",
    "why_funnel.caveat.2": "How the academy and coaching set-up actually work day to day, which no public data source used here can see.",
    "why_funnel.caveat.3": "Agents, and how a move abroad actually gets arranged, which happens off any table this pipeline can read.",
    "why_funnel.caveat.4": "The direction of the arrow: a low share of playing time for young players at home could help cause a thin generation, or just as easily be a symptom of one — the five numbers above are associations measured the same way for every country.",
    "why_funnel.take_one_thing.same": "In the gap decomposition (descriptive, see its page), the channel with the largest contribution for both {a} and {b} is {channel}.",
    "why_funnel.take_one_thing.diff": "In the gap decomposition (descriptive, see its page), the channel with the largest contribution is {channel_a} for {a} and {channel_b} for {b}.",
    "why_funnel.figure.alt": "Five-stage funnel: {adj} football next to {a} and {b} on the share of playing time young players get at home, the league's average age, the age of the first move abroad, the share of sideways moves, and players per million people in Europe's strongest leagues.",
    "why_funnel.figure.caption": "How to read it: one rung per stage of the argument, each on its own scale, so the dots show the distance between countries, not the size of the number. The filled green dot is {nation}; the open dots are the two comparison countries. Under each rung is which direction means a more open pathway. Hover a dot for the exact value.",
    "unit.percent": "percent",

    # ---- act markers (Task 25d): three section breaks between the slides,
    # a kicker and one sentence each, no numbers -- rhythm, not more findings
    "act.1.kicker": "Counting the pool",
    "act.1.line": "The next pages count who is in the pool and where the count is small.",
    "act.2.kicker": "The path abroad",
    "act.2.line": "These pages follow a player from youth minutes at home to the move abroad and the playing time after it.",
    "act.3.kicker": "National team and long run",
    "act.3.line": "The last pages cover the national-team squad, the Big-5 count over three decades and the two comparison countries.",

    # ---- slides (Task 13b): nine questions between the hero and "for a
    # federation", each q (h2) / a (one sentence, headline number in
    # <strong>) / proof (one exhibit, markup in the template) / how (mono
    # sourcing line, shared "How we know" label below)
    "slide.how_label": "Sources",
    "slide.1.q": "{Adj} players in Europe's {topn} top-ranked leagues per million inhabitants, {season}",
    "slide.1.aq": "In numbers: distinct players who appeared (any minutes) on {season} rosters of the {topn} top-ranked leagues, per million inhabitants, {nation} and {n_peers} peers.",
    "slide.1.a": "{nation} ranks <strong>{rank} of {n}</strong> countries at {pm} per million; {top} leads at {top_pm}.",
    "slide.7.a_unconverged": "{Adj} players with ≥ {min} Big-5 minutes numbered <strong>{peak_n}</strong> at the {peak_season} peak, {low_n} at the {low_season} low and {last_n} in {last_season}; the change-point fit does not meet the convergence rule, so no step is dated.",
    "ch4.series.unconverged.p": "For {nation}, the change-point fit does not meet the convergence rule after both sampler stages (diagnostics below), so no step is dated and neither its seasons nor its step sizes are reported.",
    "slide.7.a_nobreak": "{Adj} players with ≥ {min} Big-5 minutes numbered <strong>{peak_n}</strong> at the {peak_season} peak, {low_n} at the {low_season} low and {last_n} in {last_season}; the model finds no step change (best candidate {break_season}, posterior {break_prob}, ×{delta}).",
    "ch4.series.nobreak.p": "For {nation}, the model finds no step change worth dating: the best candidate is {season} at {prob} posterior with a ×{delta} ({lo}–{hi}) change in the level; the random walk's own innovation scale is σ = {sigma}.",
    "slide.1.a_leader": "{nation} leads <strong>{n}</strong> countries at {pm} per million; {second} is next at {second_pm}.",
    "slide.1.how": "Distinct players with at least one minute on {season} rosters of the {topn} UEFA top-ranked leagues ÷ population on 1 January 2024 (Eurostat, table demo_pjan, accessed 14 September 2026); every country counted the same way.",
    "slide.2.q": "{Adj} players in the top-{topn} leagues by position group and age cohort, {season}",
    "slide.2.aq": "In numbers: {adj} player count against the peer-country median, by age cohort and position group, ≥ {min} minutes, {season} season.",
    "slide.2.a": "The largest cohort gap is <strong>{group} aged {cohort}</strong>: {cze} {adj} players against a peer median of {peer}.",
    "slide.2.how": "Age at season start; cohorts U22 / 23–25 / 26–29 / 30+; ≥ {min} minutes; outfield players only (goalkeepers are counted on the goalkeeper page), and a player with rows in two position groups counts in each.",
    "slide.3.q": "Share of home-league minutes played by own under-21 nationals, {season}",
    "slide.3.aq": "In numbers: share of domestic-league minutes played by players aged ≤ 21 at season start, {season}, by country's top flight.",
    "slide.3.a": "Own under-21 nationals played <strong>{cze_pct} %</strong> of the {home_league}’s minutes; the highest share among the peers is {best_name}’s {best_pct} %.",
    "slide.3.how": "Share of all league minutes played by players aged ≤ 21 at season start, {season}, per domestic top flight.",
    "slide.3.uncertain": "Across {n} countries (country means over two seasons), ten points more under-21 share go with {beta} more top-{topn} players per million (90 % HDI {lo} to {hi}, R² = {r2}). Within countries, from one season to the next, the estimate is {within} (90 % HDI {wlo} to {whi}), n = {n_within} country-seasons. The share is measured; its association with the per-head count is not settled.",
    "slide.3.panel": " Across the {n_countries} countries (country averages over both seasons), 10 points more U21 share go with {beta} more top-{topn} players per million (90 % HDI {lo} to {hi}).",
    "slide.3.panel.summary": "Across countries",
    "slide.3.panel.alt": "Scatter of U21 share of domestic-league minutes against top-9 players per million, {n_countries} countries, two seasons each connected by a line, {nation} highlighted, with the fitted line and its 90 % band.",
    "slide.4.q": "Where {adj}-eligible players with {min}+ minutes played in {season}, by league tier",
    "slide.4.aq": "In numbers: destination-league tier of every {adj}-eligible player's {season} row, split into top-{topn}, sideways and other abroad moves.",
    "slide.4.a": "<strong>{abroad} of {total}</strong> played abroad: {top9_n} in the {topn} top-ranked leagues and {sideways_n} ({sideways_pct} %) in a league no stronger than the {home_league} by UEFA-coefficient multiplier.",
    "slide.4.how": "Destination league of every {adj}-eligible player's {season} row with at least 450 minutes, one row per position group; sideways = destination multiplier ≤ {adj} league multiplier, both UEFA-coefficient multipliers (<a href=\"#league-strength\">league strength: two estimates, § Methodology</a>).{home_note}",
    "slide.4b.q": "Age at the first top-{topn} season and output over the first two seasons, {n} exports",
    "slide.4b.zero_note": ", an interval that includes zero: no detectable difference at n = {n}",
    "slide.4b.aq": "In numbers: mean league-adjusted goals + assists per 90 over the first two top-{topn} seasons, as a function of age at the first one, given origin-league strength and position, {n} peer-nationality exports.",
    "slide.4b.a": "Players who reach a top-{topn} league at 21 produce <strong>{diff}</strong> more league-adjusted goals plus assists per 90 over their first two seasons than those arriving at 24 (90 % HDI {dlo} to {dhi}, n = {n} exports).",
    "slide.4b.a_zero": "No measurable difference: players who reach a top-{topn} league at 21 and at 24 differ by <strong>{diff}</strong> league-adjusted goals plus assists per 90 over their first two seasons (90 % HDI {dlo} to {dhi}, n = {n} exports).",
    "slide.4b.a_detail": "At 21: {y21} (90 % HDI {lo}–{hi}); at 24: {y24} ({lo24}–{hi24}); the difference {diff} ({dlo} to {dhi}). {Adj} exports in the model sample reached a top-{topn} league at a median age of {age_home} (n = {n_home}).",
    "slide.4b.how": "Age curve ({branch}) on league-adjusted production, given origin-league strength (<a href=\"#league-strength\">§ Methodology</a>), position and a country effect, {n} peer-nationality exports {cite}; 90 % HDI; better players tend to leave earlier, so the curve mixes selection with development and this atlas does not separate them.",
    "slide.4b.alt": "Line chart: the fitted age-at-export curve with its 90 % band, {adj} exports as points against every other peer export, and a rug of every export's age along the axis.",
    "slide.4b.caption": "How to read it: the horizontal axis is a player\u2019s age in his first top-9 season; the vertical axis is his league-adjusted goals plus assists per 90 over the first two seasons there. The line is the model\u2019s expected value at each age, the band its 90 % interval; a flat line means no measurable difference in output by arrival age. Green dots are {adj} exports \u2014 hover for the name.",
    "slide.5.q": "Share of club minutes played by exports in the top-{topn} leagues, by country of origin, {season}",
    "slide.5.aq": "In numbers: median share of a club's {season} minutes kept by players abroad, by country of origin.",
    "slide.5.a": "{Adj} exports played a median <strong>{cze} %</strong> of their club's minutes (90 % bootstrap interval {lo}–{hi} %, n = {n_home}), {rank} of {n} by the median; {overlap} of the other countries’ intervals overlap it.",
    "slide.5.a2": "A {home_league} season converts to {m_l} of a Premier League one by the transfer-graph model (90 % HDI {lo}–{hi}), against {uefa} by the UEFA-coefficient multiplier; the destination tiers and the sideways share on this page use the UEFA value.",
    "slide.5.how": "Median share of club minutes (player minutes ÷ club matches × 90) for players with the country's nationality at a top-{topn} club, one row per player; 90 % percentile-bootstrap interval, 2 000 resamples of players, seed 42.{home_note}",
    "slide.5.alt": "Dot plot: each country's median share of club minutes for players abroad, with a thin line spanning the other countries' values; {nation} highlighted.",
    "slide.5.caption": "How to read it: one row per country, sorted; the dot is the median share of his club\u2019s minutes that a country\u2019s exported player keeps, the thin line the range across its exports. {Adj} exports are the green row. Further right means exports who play a larger share of their club\u2019s minutes.",
    "slide.5.table_summary": "Country-by-country figures",
    "ch2.headline_note": "Not informative for this nation: {home_league} and every peer's own league are themselves top-{topn} leagues, so the domestic / top-{topn} split has no content here; the exhibit is kept for comparability with other nations.",
    "slide.home_note": " {home_league} is itself one of Europe's top-{topn} leagues; here 'abroad' means the other {topn_minus_1}.",
    "slide.6.q": "League tier of the {event} squad: {nation} and the peers at the tournament",
    "slide.6.aq": "In numbers: league tier of every {event} squad member's most-minutes {season} row, matched by name and birth year, per country.",
    "slide.6.a": "<strong>{cze_pct} %</strong> of {nation}’s {event} squad ({n_top9} of {n}) played in the {topn} top-ranked leagues in {season}; the highest share among the {n_peers} peers at the tournament is {best_name}’s {best_pct} %.",
    "slide.6.how": "Wikipedia squad lists (CC BY-SA 4.0, accessed 14 September 2026) matched to {season} league rows on normalised name plus birth year; tier = league of the most-minutes row; squad players without a {season} row, per country: {unmatched}.",
    "slide.7.q": "{Adj} players with {min}+ minutes in the Big-5 leagues per season, {first_season} to {last_season}",
    "slide.7.rules.both": "the dashed rule marked \u201cbreak\u201d is the season the model dates the {kind} to and the one marked \u201crise\u201d the season it dates the rise to, each with its posterior probability;",
    "slide.7.rules.break": "the dashed rule marked \u201cbreak\u201d is the season the model dates the {kind} to, with its posterior probability; the model\u2019s other step is not a rise of 5 % or more and is not marked;",
    "slide.7.rules.rise": "the dashed rule marked \u201crise\u201d is the season the model dates the rise to, with its posterior probability;",
    "slide.7.rules.unconverged": "no season is marked: the change-point fit does not meet the convergence rule;",
    "slide.7.rules.none": "no season is marked: the model finds no step in the level more than 5 % from no change;",
    "slide.7.aq": "In numbers: {adj} players with ≥ {min} minutes in the Big-5 leagues each season since {first_season}, with each step in the level that a change-point model can date.",
    "slide.7.a": "{Adj} players with ≥ {min} Big-5 minutes numbered <strong>{peak_n}</strong> at the {peak_season} peak, {low_n} at the {low_season} low and {last_n} in {last_season}.",
    "slide.7.a_rise": " The rise before it is dated to {rise_season}.",
    "slide.7.a_rise_after": " The recovery after it is dated to {rise_season}.",
    "slide.7.a_detail": "The change-point model’s most probable season for the {kind} is {break_season} (posterior {break_prob}), a level change of ×{delta} (90 % HDI {lo}–{hi}).",
    "slide.7.a_detail_rise": " Its most probable season for the rise is {rise_season} (posterior {rise_prob}), ×{rise_delta} (90 % HDI {rise_lo}–{rise_hi}).",
    "slide.7.how": "FBref Big-5 player tables {first_season} → {last_season}; peers on the same rule. The names are, for each of the three seasons with the highest counts, the {adj} players with the most Big-5 minutes that season, goalkeepers included, listed as a record of presence and not as a quality ranking: {golden}. The dates come from a Bayesian local-level model with two ordered change points, one for the rise and one for the fall {cite_cp}; detail in <a href=\"#series-model\">§ Methodology</a>.",
    "slide.7.alt": "Line chart: {adj} players with at least {min} minutes in the Big-5 leagues, {start} to {end}, against eight peer countries; a lower panel shows per-million rates for {nation}, {a} and {b}.",
    "slide.7.caption": "How to read it: each line is one country\u2019s count of players with at least 450 minutes in the five biggest leagues, season by season since {first_season}. {Adj} players are the green line; {rules} the point past the last season is the forecast for next season with its 90 % interval. Toggle countries and switch to per million to compare fairly across sizes.",
    "slide.8.q": "{nation}, {a} and {b} on seven pathway measures, {season}",
    "slide.8.aq": "In numbers: {a} and {b} against {nation} on the same seven pathway definitions, same seasons.",
    "slide.8.a": "On the same definitions, {a} gives its under-21 nationals <strong>{nor_u21} %</strong> of home-league minutes against {cze_u21} % in {nation}, and {nor_top9} % of its tournament squad played in the {topn} top-ranked leagues against {cze_top9} %.",
    "slide.8.how": "Same definitions, same seasons; a comparison, not a causal claim. The chart rescales the first six measures 0–1 across the three countries, direction chosen so 1.0 is always the more open pathway (more players per million, more U21 minutes, an earlier age at the first top-9 season, fewer sideways moves, a bigger minutes share abroad, more of the squad in the top-9); the table keeps the raw numbers.",
    "slide.8.alt": "Slope chart: {a}, {b} and {nation} on six pathway metrics, each rescaled 0 (worst of the three) to 1 (best of the three), one line per country.",
    "slide.8.caption": "How to read it: six measures, each rescaled so 0 is the worst of the three countries and 1 the best, one line per country. With only three countries the rescaling stretches any difference to the full height, including differences of a few tenths; read the raw values in the table.",
    "slide.8.table_summary": "The seven numbers, unscaled",
    "slide.8b.q": "{Adj} goalkeepers in the top-{topn} leagues per million and their age at the first top-{topn} season, {season}",
    "slide.8b.aq": "In numbers: {adj} goalkeepers with ≥ {min} minutes in the top-{topn} leagues, per million inhabitants, against outfield export age.",
    "slide.8b.a": "{n_gk} {adj} goalkeepers played ≥ {min} minutes in the top-{topn} leagues, <strong>{pm} per million</strong> (rank {rank} of {n}), and their median age at the first top-{topn} season was {gk_age} (n = {n_gk_age}) against {out_age} for outfield exports (n = {n_out}).",
    "slide.8b.a_detail": "{pm} per million; first top-{topn} season at a median age of {gk_age} (n = {n_gk_age}), against {out_age} for outfield exports (n = {n_out}); with this few goalkeepers the two medians cannot be compared.",
    "slide.8b.earlier": "earlier than outfield exports",
    "slide.8b.later": "later than outfield exports",
    "slide.8b.same_age": "at about the same age as outfield exports",
    "slide.8b.alt": "Strip plot of age at first top-9-league appearance, {adj} goalkeepers against outfield exports, one dot per player, medians marked.",
    "slide.8b.how": "{min}-minute floor, {season} rosters; goals against and saves per 90 are shrunk toward the league median with a prior worth {phantom} minutes, as every rate in the atlas; first season in a fetched top-{topn} table; players already there in {history_start} are censored ({censored_pct} % of the goalkeepers, {censored_out_pct} % of the outfield exports); a comparison of two pathways inside one nation, not a causal claim.{home_note}",
    "slide.8b.home_note": " First top-{topn} season needs no move for a {home_league} keeper.",
    "slide.8c.q": "Gap in players per million between {nation} and {a} and {b}, split over three measured channels (descriptive)",
    "slide.8c.aq": "In numbers: a linear split of the per-capita gap into U21 minutes, league strength and export age across {n} peer countries.",
    "slide.8c.a": "Of the <strong>{gap}</strong> players per million between {contrast} and {nation}, youth minutes go with {c1} ({c1lo} to {c1hi}), league strength with {c2} ({c2lo} to {c2hi}) and export age with {c3}; of the {gap2} for {contrast2}, with {d1} ({d1lo} to {d1hi}), {d2} ({d2lo} to {d2hi}) and {d3} (90 % bootstrap intervals).",
    "slide.8c.a_detail": "Of the {gap} per million between {contrast} and {nation}, a residual of {resid} is not carried by the three channels.",
    "slide.8c.alt": "One horizontal stacked bar per contrast country: the contribution of U21 minutes, league strength and export age to its per-capita gap with {nation}, plus the residual; whiskers show each channel's bootstrap interval.",
    "slide.8c.caption": "How to read it: the whole bar is the gap in players per million between the comparison country and {nation}. Each segment is how much of that gap goes with one measured channel \u2014 youth minutes, league strength, export age \u2014 under the decomposition; the hatched remainder is what the three channels do not carry. A segment is negative where the fitted term for that channel predicts fewer players per million for the comparison country than for {nation}.",
    "slide.8c.how": "Ridge-regression linear split (α = {alpha}, standardised channels), Blinder-Oaxaca-style {cite_ob}, fit on the {n} peer countries with data on all three channels; 90 % bootstrap intervals, {n_boot} resamples, seed 42 plus the contrast’s index; with {n} countries and three correlated channels the split is indicative; a decomposition of a correlation, not a causal accounting.",
    "slide.9.q": "Showcase cards: {n} {adj} players chosen by six selection rules, and the {season} pool",
    "slide.9.aq": "In numbers: {n} showcase cards chosen from the {season} pool by six selection rules, one per position group per rule.",
    "slide.9.a": "<strong>{n} cards</strong>, one player per position group under each of six selection rules.",
    "slide.9.how": "{season} FBref, Wikipedia and Wikidata rows joined by name and birth year; six selection rules, applied in order — see below.",

    # ---- slide-so lines (Task 25e): one closing line per slide, ≤ 20 words,
    # descriptive -- what a federation reader would watch next, never a
    # recommendation
    "slide.1.so": "A federation tracking this would watch the per-million rank move over seasons, not any one year's number.",
    "slide.2.so": "A federation tracking this would watch which cohort's gap narrows or widens season to season, not just today's snapshot.",
    "slide.3.so": "A federation tracking this would watch the U21 share season by season, not the export count.",
    "slide.4.so": "A federation tracking this would watch the sideways-move share over time, not the raw count of players abroad.",
    "slide.4b.so": "A federation tracking this would watch how the age-at-export curve shifts across cohorts, not any single player's outcome.",
    "slide.5.so": "A federation tracking this would watch whether an export's minutes share holds after the first season, not just the median.",
    "slide.6.so": "A federation tracking this would watch the tier mix of future squads over cycles, not one tournament's snapshot.",
    "slide.7.so": "A federation tracking this would watch whether the post-break level holds for another season, not treat one break as final.",
    "slide.8.so": "A federation tracking this would watch which of the six numbers moves first, not the overall picture alone.",
    "slide.8b.so": "A federation tracking this would watch whether the goalkeeper pathway keeps diverging from outfield export age, not one season's gap.",
    "slide.8c.so": "A federation tracking this would watch which channel's contribution grows, not treat the split as fixed.",
    # ---- slide 10 (Task 31): what changed between the two seasons
    "slide.10.q": "League tier of {adj}-eligible players in {previous} and {metrics}",
    "slide.10.aq": "In numbers: every {adj}-eligible player with at least {min} minutes in {previous} or {metrics}, placed on the pathway\u2019s tier ladder in each season, and the move between the two.",
    "slide.10.did": "We took each player’s main league last season and this season, sorted the leagues into the four tiers the atlas uses everywhere — home league, other covered league, stepping stone (the German second tier), top nine — and counted who moved up, who moved down, who appeared and who is no longer in any league we can see.",
    "slide.10.a": "<strong>{up} moved up a tier and {down} moved down</strong> between {previous} and {metrics}; the top-{topn} leagues held {top_curr} players, from {top_prev}.",
    "slide.10.minutes": "{prev} → {curr} minutes",
    "slide.10.tiers_note": "Players of the pool in each tier, {previous} → {metrics}, with the minutes they played there: {n_prev} players last season, {n_curr} this season, outfield players with at least {min} minutes, one row per player (the destinations page counts one row per position group, so a player with two positions counts twice there).",
    "slide.10.move_up": "Moved up a tier",
    "slide.10.move_down": "Moved down a tier",
    "slide.10.move_entered": "New to the pool",
    "slide.10.move_left": "No longer in a covered league",
    "slide.10.more": "and {n} more",
    "slide.10.left_note": "\u201cNo longer in a covered league\u201d means exactly that: retired, injured for the season, or playing in a league this report does not fetch. The data cannot tell those apart and this page does not guess. \u201cNew to the pool\u201d likewise mixes debutants with players returning from leagues outside the set.",
    "slide.10.how": "Season feature tables for both seasons; a player\u2019s league is the one he played most minutes in; {min}-minute floor in a season to count as present in it; rungs as defined in the pathways chapter.",
    "slide.10.so": "A federation tracking this would watch the two moving columns each summer, and the stepping-stone count above all.",
    # ---- "This autumn" (#autumn): dated news beside the snapshot's numbers
    "autumn.h2": "This autumn",
    "autumn.asof": "Atlas data as of {data}; squad news as of {news}",
    "autumn.lede": "Since the World Cup the national team has a new head coach, and three players of the pool have retired from it. The dated facts below come from the sources listed at the end; every number is the atlas\u2019s own, from its snapshot, which this section does not refresh.",
    "autumn.coach.h3": "A new head coach",
    "autumn.coach": "{previous} left the post of head coach by mutual agreement on {left}.{n_left} {new} was appointed head coach on {appointed}, on a {years}-year contract,{n_appointed} and presented publicly on {presented}.{n_presented}",
    "autumn.retire.h3": "Three retirements from the national team",
    "autumn.retire.lede": "Each of the three announced his own retirement from international football before {new} was appointed; none of them was left out by a selection decision.{notes}",
    "autumn.card.announced": "Announced {date}",
    "autumn.card.minutes": "{min} minutes in {season}",
    "autumn.card.squad_yes": "In the {event} squad",
    "autumn.card.squad_no": "Not in the {event} squad",
    "autumn.card.quote": "He called it “{gloss}”{fn}.",
    "autumn.card.unmatched": "Not found in the atlas pool.",
    "autumn.data_note": "Club, tier and minutes: the atlas pool, season {season} (the league he played most minutes in), matched by name; the World Cup line is the squad list of the national-team page.",
    "autumn.unmatched": "Not matched to the pool: {names}.",
    "autumn.not_shown": "Not shown yet: the September squad set against the World Cup squad by league rung. The September list could be read only in a secondary transcription, not in the federation\u2019s own nomination, so it is left out until it can be checked.",
    "autumn.sources.h": "Sources",
    "autumn.source.nd": "n.d.",
    "autumn.source.accessed": "accessed {date}",
    # ---- pre-registered forecast scoreboard on slide 7 (Task 32)
    "pred.kicker": "The registered forecast",
    "pred.claim": "Forecast for {season}: <strong>{point}</strong> {adj} players with at least {min} minutes in the Big-5 leagues (90 % interval {lo}–{hi}).",
    "pred.registered": "Registered",
    "pred.baseline": "Baseline to beat",
    "pred.baseline_value": "{n} \u2014 last season\u2019s count, the \u201csame as last year\u201d forecast",
    "pred.scoring": "Scored by",
    "pred.scoring_rule": "whether the observed count falls inside the {pct} % interval, and whether the point forecast\u2019s error is smaller than the baseline\u2019s",
    "pred.outcome": "Outcome",
    "pred.open": "open \u2014 resolves after {date}, when the season\u2019s tables are final",
    "pred.due": "due \u2014 the season ended on {date} and the count has not been entered yet",
    "pred.hit": "inside the interval",
    "pred.miss": "outside the interval",
    "pred.vs_naive": "error {model} against the baseline\u2019s {naive}",
    "pred.drift": "The model has been refitted since registration and now says {point} ({lo}\u2013{hi}). The registered numbers above are the ones that will be scored.",
    "pred.backtest": "Refitted at {n} past origins, the model behind this number missed by {mae_model} players on average against {mae_naive} for “same as last year”; the registered forecast itself is scored only when the season ends.",
    "pred.why": "The registered numbers stay fixed in config/predictions.yaml and are scored by the rule above once the season’s tables are final.",
    "atlas.kicker": "The atlas: every player-season of {season}, one dot each",
    "atlas.read": "How to read it: every dot is the {season} season of one of the {group} in the leagues this report covers. The two axes are the first two principal components of his five per-90 numbers (goals, assists, minutes share, age, cards) \u2014 dots that sit close together had similar seasons. The style projection uses the raw numbers, the quality projection the league-adjusted ones, so switching shows who moves when the strength of his league is counted. Colours are the clusters named below; green dots are {adj}-eligible players, a black ring marks a national-team call-up. Hover a dot for the player, click to pin, scroll to zoom, type a name to find him.",
    "slide.10.sankey_caption": "How to read it: the left column is last season\u2019s rung for every player in the pool, the right column this season\u2019s; each ribbon is the players who went from one to the other, its width their number. Green ribbons climb, orange come down, teal are new to the pool, grey are no longer in a covered league. Hover a ribbon for the names.",
    "slide.8b.caption": "How to read it: one dot per player at the age of his first season in a top-9 league; goalkeepers in the upper strip, outfield exports in the lower, medians marked. Further left is an earlier first appearance.",
    "slide.9.so": "A federation tracking this would watch how the showcase set changes as a cohort ages, not any one card.",

    # ---- slide chain kickers (Task 26C): every slide's question is followed
    # by "As an analytics question" (the aq sentence, already present) and a
    # new "What we did" sentence -- one plain sentence a coach can read, no
    # symbols, no abbreviations, describing the operation rather than naming
    # the statistics.
    "slide.method_summary": "How we know",
    "slide.aq_label": "As an analytics question",
    "slide.did_label": "What we did",
    "slide.1.did": "We counted every player with the home nation's nationality who appeared in one of Europe's top-ranked leagues that season, then divided the count by the country's population.",
    "slide.2.did": "We split players into position groups and age bands, counted how many the home nation had in each one, and compared that count with the middle value among the other countries.",
    "slide.3.did": "We counted every minute played in the league and looked at how many of them went to players aged 21 or younger.",
    "slide.4.did": "We looked at where every eligible player was actually playing that season and grouped each one by how strong that league is compared with the player's own home league.",
    "slide.4b.did": "We looked at the age a player first arrived in one of the strongest leagues and checked whether players who arrived earlier ended up producing more, once we accounted for the strength of the league they came from.",
    "slide.5.did": "We worked out what share of each club's playing time the player actually got, took the median over each country's exports and resampled the players to put an interval on that median.",
    "slide.6.did": "We matched every named squad player to his club season and recorded which level of league he was actually playing in.",
    "slide.7.did": "We counted, season by season, how many home-nation players had real playing time in Europe's five biggest leagues, then asked a change-point model for the most probable seasons of a lasting rise and a lasting fall, with a probability on each.",
    "slide.8.did": "We compared the home nation with the two comparison countries on seven numbers, each one defined and measured in exactly the same way for all three.",
    "slide.8b.did": "We counted goalkeepers the same way we counted outfield players, then compared the age each group first reached one of the strongest leagues.",
    "slide.8c.did": "We used the players who changed leagues to work out what a season in one league is worth in another, then split the gap between countries into the parts that line up with young players' minutes, league strength and the age players move abroad.",
    "slide.9.did": "We matched each player's season to his national-team call-ups and photo, then picked one player per position group under each of six rules.",

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
    "peer_compare.export_age": "Age at first top-9 season (recent entrants)",
    "peer_compare.sideways": "Sideways moves",
    "peer_compare.minutes_share": "Exports' club-minutes share",
    "peer_compare.wc_top9": "National-team squad in the top-9 leagues",
    "peer_compare.big5_now": "Big-5 players now",

    # ---- explore the data (folded; today's chapters I-III material)
    # ---- #pool (Task 30): every player in the pool, findable
    "pool.summary": "Every player in the {season} pool \u2014 all {n}, searchable",
    "pool.intro": "The cards above pick by rule. This is everyone with a {season} season in the data: {fw} forwards, {mf} midfielders, {df} defenders and {gk} goalkeepers. Open a name for what the report measures about him, in plain words. Rank is within his own position group on quality-adjusted production; the two arrows mark a mid-season move.",
    "pool.search": "Find a player",
    "pool.search.placeholder": "name or club, accents optional",
    "pool.filter.pos": "Position",
    "pool.filter.tier": "League",
    "pool.filter.age": "Age",
    "pool.filter.all": "All",
    "pool.count": "{shown} of {total}",
    "pool.empty": "No player matches. The pool is every {adj}-eligible player with a season row in the leagues this report covers; a player in a league it does not cover is not here.",
    "pool.col.player": "Player",
    "pool.col.age": "Age",
    "pool.col.pos": "Pos",
    "pool.col.club": "Club",
    "pool.col.min": "Minutes",
    "pool.col.rank": "Rank",
    "pool.nt_title": "Called up to the national team in the seasons this report covers",
    "pool.moved_title": "Two clubs this season",
    "pool.pos.FW": "forward",
    "pool.pos.MF": "midfielder",
    "pool.pos.DF": "defender",
    "pool.pos.GK": "goalkeeper",
    "pool.pos_pl.FW": "forwards",
    "pool.pos_pl.MF": "midfielders",
    "pool.pos_pl.DF": "defenders",
    "pool.pos_pl.GK": "goalkeepers",
    "pool.tier.domestic": "{home_league}",
    "pool.tier.stepping_stone": "stepping-stone league",
    "pool.tier.top9": "top-9 league",
    "pool.tier.other": "other covered league",
    "pool.band.u21": "21 and under",
    "pool.band.22-25": "22\u201325",
    "pool.band.26-29": "26\u201329",
    "pool.band.30plus": "30 and over",
    "pool.profile.aria": "Percentile profile against his position group",
    "pool.profile.note": "Percentiles among all {pos_pl} with at least 450 minutes in the covered leagues, {season} \u2014 100 is the top.",
    "pool.link": "Link to this player",
    "pool.career": "Career, season by season →",
    "pool.line.id": "{age}, {pos}, {club} ({where}).",
    "pool.line.usage_starts": "Started {starts} games and came on {subs} times, finishing {compl} of the starts; {mn} minutes in a typical start and {share} % of his club\u2019s available minutes.",
    "pool.line.usage_min": "{min} minutes, {share} % of his club\u2019s available minutes.",
    "pool.line.prod": "{npg} non-penalty goals and {ast} assists per 90; adjusted for the strength of his league that is {q}, which ranks him {rank} of {n} {pos_pl} in the pool.",
    "pool.line.role": "Per 90 he attempts {crs} crosses, wins {tkl} tackles, makes {int} interceptions and is fouled {fld} times.",
    "pool.line.moved": "Two clubs this season: {stints}; the numbers above are the whole season.",
    "pool.line.gk": "{min} minutes; {ga} goals conceded per 90, {save} % of shots on target saved, {cs} clean sheets.",
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

    # ---- one-page brief (Task 26E2): the whole argument on one screen,
    # before Explore, sized to print on a single A4 page (see @media print)
    "brief.h2": "One-page brief",
    "brief.open": "Show the one-page brief",
    "brief.print": "Print this page",
    "brief.intro": "The five pathway measures on one screen with their samples, the largest channel in the gap decomposition, and two model checks with their intervals.",
    "brief.th.number": "Number",
    "brief.check.strength": "How strong is the home league",
    "brief.check.strength_value": "A season in the home league is worth about {median} of a season in the Premier League (90 % HDI {lo}–{hi}).",
    "brief.check.break": "Most probable season of the dated step in the Big-5 count",
    "brief.check.break_value": "{season} (posterior {prob}); level ×{delta} (90 % HDI {lo}–{hi}).",

    # ---- downloads (Task 26E3): raw links into the committed data snapshot,
    # inside Explore
    "explore.downloads.h3": "Download the tables",
    "explore.downloads.intro": "The tables behind this report, exactly as the pipeline produced them, committed to the public repository. An analyst can take these and work from them directly, not only from the pictures above.",
    "downloads.pool": "Every player found in the pool, one row per player, before any season's numbers are attached.",
    "downloads.per_capita": "Players per million people, one row per country, the numbers behind the per-head page, and the same count at floors of 1, 450 and 900 minutes.",
    "downloads.features": "The five-number season vector for every covered player, one file per position group (forwards, midfielders, defenders).",
    "downloads.cohorts": "Production by country, position group and age band, the numbers behind the international comparison.",
    "downloads.pathways": "Youth minutes at home, the age and route of the move abroad, how exports fare, and where they land — every number behind the pathway exhibits, in one file.",
    "downloads.big5_history": "Season-by-season counts of home-nation players in Europe's five biggest leagues, back to the start of the fetched history.",
    "downloads.fbref_players": "Every season row this pipeline has fetched, for every league and nationality it covers — the raw table everything else in this report is built from.",
    "downloads.pca_loadings": "How each of the five season numbers contributes to the style and quality maps.",
    "downloads.sensitivity": "How much the top players change when a league's strength is nudged up or down.",
    "downloads.pipeline_facts": "The three new numbers behind the why-the-train-left funnel: club breadth of youth minutes, the league's own age structure, and the age at a player's first move abroad.",
    "downloads.fbref_roles": "FBref\u2019s playing-time and miscellaneous tables for every fetched league-season: starts, minutes per start, substitute appearances, on-off, crosses, interceptions, tackles won, fouls.",
    "downloads.fbref_history": "The history seasons of the home, peer and stepping-stone leagues back to the start of the fetched history, the rows behind the player atlas\u2019s careers.",
    "downloads.pool_table": "Every player in the pool as one row \u2014 the table behind the searchable list \u2014 with production, rank in his position group, playing-time split and role counts.",
    "downloads.season_changes": "Where the pool moved between the two seasons: each player\u2019s rung in each, the move between them, and minutes by rung.",

    # ---- plain-language metric labels (used everywhere outside chapter IV;
    # chapter IV keeps "npG+A/90 q" and explains it once)
    "metric.prod": "goals + assists per 90, league-adjusted",
    "metric.prod.short": "G+A / 90 adj.",

    # ---- chapter I
    "ch1.benchmark.h3": "Structural benchmark vs peer countries",
    "ch1.benchmark.p": "The tables below count {adj} players in the top-{topn} leagues by position group and age cohort against the peer countries, from the same season tables as every other count in the atlas.",
    "ch1.capita.aria": "Per-capita density of top-league players by country",
    "ch1.heatmap.alt": "Heatmap of the international cohort benchmark: {n} countries by position group and age cohort, {season} season; the {adj} row is outlined.",
    "ch1.heatmap.caption": "Median non-penalty goals + assists per 90 by country, position group and age cohort, {season}; the outlined row is {nation}.",
    "ch1.heatmap.note": "Each cell: player count and the median value; rows ordered by per-capita rank, {nation} highlighted.",
    "ch1.heatmap.full_lead": "The full picture, all nine peer countries at once, as a heatmap:",
    "ch1.cohorts.h4": "Cohort gaps — {group}",
    "ch1.cohorts.th": "Cohort",
    "ch1.cohorts.none": "no player",
    "ch1.cohorts.note": "* Count and median npG+A per 90 of players with the country's nationality in a top-{topn} league, {season}, at least {min} minutes; cohort by age at the season's calendar turn (start year + 1 − birth year). {shown} of the {n} countries are shown; the heatmap above carries all of them. Largest {adj} shortfalls against the peer median count: {gaps}.",
    "ch1.cohorts.gap_item": "{group} {cohort} ({cze} vs {peer})",
    "ch1.atlas.alt": "Two-panel atlas of {group} {season} in PCA projection. Left panel: style map without league multipliers; right panel: quality-adjusted map. Grey points are the whole corpus of {corpus} players; coloured points are the {czech} {adj}-eligible players by cluster; green rings mark the {nt} with a national-team call-up {nt_years}.",
    "ch1.atlas.caption": "Atlas of {group} {season} in both projections: {czech} {adj}-eligible players in colour against a corpus of {corpus}. Green rings mark the national-team pool (call-up {nt_years}, {nt} players).",
    "ch1.observations.h3": "Observations",
    "ch1.clusters.h3": "Cluster archetypes (style projection)",
    "ch1.clusters.p": "Clusters are fitted on the whole corpus of {season} player-seasons and read here through their {adj} members, K chosen by silhouette score {cite_rousseeuw} with scikit-learn {cite_pedregosa}. The label describes the cluster's median footprint; the count is {adj} members of the corpus cluster; names are the {adj} members with the most minutes.",
    "ch1.clusters.meta": "{n} {adj} of {corpus} · NT pool {nt} · median born {born}",
    "ch1.clusters.medians": "Corpus medians: {npg} non-penalty goals and {ast} assists per 90, {share} of the club's minutes, age {age}, {cards} cards per 90.",
    "ch1.clusters.tactical": "Author’s reading (not computed)",
    "ch1.traj.h3": "Trajectories {previous} → {metrics} ({adj}-eligible, ≥ {min} minutes in both seasons)",
    "ch1.traj.p": "Season-over-season change in goals + assists per 90, league-adjusted. A move counts as up or down beyond ± {band}; for scale, the standard deviation of this one-season change across the {n} {adj}-eligible players with both seasons is {sd}. Everything inside the band is listed as stable.",
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
    "ch2.a.nodata": "not on FBref",
    "ch2.a.note": "* Σ minutes of players with the league country's nationality and age ≤ 21 at the season's start ÷ Σ minutes of all players in the league, {season}. Under-23 shares: {u23}. A league without a bar is not covered by FBref.",
    "ch2.b.h3": "Exhibit B — export route",
    "ch2.b.p": "For every peer-country player on a {current} top-{topn} roster: the age at the first top-{topn} season (full roster, and recent entrants only) and, for recent entrants, the league of the season before it.",
    "ch2.b.cze": "{Adj} exports: {n} players, median export age {age} (recent entrants {n_recent}, median {age_recent}), {domestic} of the recent ones straight from the {home_league}*.",
    "ch2.b.th.country": "Country",
    "ch2.b.th.recent": "Recent",
    "ch2.b.th.age_all": "Age at first top-9 season (all)",
    "ch2.b.th.age_recent": "Age at first top-9 season (recent)",
    "ch2.b.th.domestic": "Domestic",
    "ch2.b.th.stepping": "Stepping stone",
    "ch2.b.th.other": "Other top-{topn}",
    "ch2.b.th.not_covered": "Not covered",
    "ch2.b.th.censored": "Censored",
    "ch2.b.note": "* Export age = age at the first season in any headline league, history back to {start}; a first appearance already in {start} is censored. Recent entrants: first top-{topn} season {metrics} or {current}, the only ones whose previous season lies inside the fetched window ({coverage} onwards for peer domestic leagues). Stepping-stone league: {stepping}, the one covered league below the top nine that is no peer’s home league. Not covered: no earlier row in the data.",
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
    "ch2.f.note": "* {unmatched} of the {total} squad players across the {countries} countries have no {season} row in the fetched leagues and are counted as unmatched ({per_country}).",
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
    "ch3.card.tactical": "Author’s reading (not computed)",
    "ch3.card.traj": "Trajectory {previous} &rarr; {metrics}",
    "ch3.card.analogs": "Historical analogs at age {age} (d = distance on three standardised features: league-adjusted goals + assists per 90, minutes, league multiplier)",
    "ch3.card.min": "min",
    "ch3.card.selected": "Selected as: {reason}.",
    "ch3.cards.note": "* Each card renders the existing dataset; no computation beyond the join. Age on the name line is the {current} season-start age (start year − birth year); the club is from the {current} tables, or — labelled \"{latest}\" — from FBref's country page where the player has no {current} row. Age on the analog line follows the analog finder's convention (season start year + 1 − birth year).",
    "ch3.gk.kicker": "Goalkeepers — most top-9 minutes · youngest in the top-{topn}",
    "gk.stat.ga90": "Goals against / 90",
    "gk.stat.saves90": "Saves / 90",
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
    "gk.production.th.ga90": "Goals against per 90",
    "gk.production.th.saves90": "Saves per 90",
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
    "ch4.title": "Methodology, data and limitations",
    "ch4.synopsis": "Data sources and availability, the models behind the numbers, all limitations in one place, reproduction and references.",
    "ch4.h2": "Methodology, data and limitations",
    "ch4.sources.h3": "Data sources",
    "ch4.sources.fbref": "<strong>FBref</strong> (Sports Reference), read with <code>soccerdata</code> {sd}: player season tables (standard, playing time) for the {topn} headline leagues, the {home_league}, the peer domestic leagues and the German second tier; the country page \"Players from {nation}\" for pool discovery; the nationality column for peer counts. Season tables fetched {fetched}; the Big-5 history back to 1995/96 is in the snapshot committed {history}",
    "ch4.sources.wikipedia": "<strong>Wikipedia</strong>: national-team squad tables ({events}), accessed {accessed}; text under CC BY-SA 4.0",
    "ch4.sources.wikidata": "<strong>Wikidata / Wikimedia Commons</strong>: player portraits (P18) matched on name, citizenship and date of birth; Wikidata is CC0, each Commons file carries its own licence (credits in the footer)",
    "ch4.sources.uefa": "<strong>UEFA association coefficients</strong>, men’s five-season ranking ({window}, as published on the fetch date), primary source uefa.com, read from Wikipedia’s transcription of UEFA’s table on {accessed} because ClubElo was unreachable; ranks 1–9 of that ranking are exactly the nine headline leagues (England, Italy, Spain, Germany, France, Portugal, Belgium, the Netherlands, Türkiye)",
    "ch4.sources.eurostat": "<strong>Eurostat</strong>: population on 1 January 2024, table demo_pjan, accessed {accessed}; reuse under the European Commission’s reuse policy with attribution",

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

    # ---- "in plain terms" leads (Task 26D): one plain paragraph before each
    # model section's technical text, 2-4 sentences, no symbols, a football
    # analogy where one is honest.
    "ch4.strength.plain": "A season in one league is not automatically worth the same as a season in another: goals and assists come easier in some competitions than others. This section works out an exchange rate between leagues by watching the same players before and after they change league, the way a manager judges a new signing by how his output changes at the new club.",
    "ch4.compare.plain": "Here we ask a simple question of five different methods: given a player's numbers this season, how well can each one guess his numbers next season. Each method is tested only on seasons it has not already seen, the way a scout's judgement only really counts for what he predicts before a season starts, not after it has finished.",
    "ch4.series.plain": "This section finds the two seasons when the count of home-nation players in Europe's five biggest leagues changed level for good — the rise and the fall — and puts a probability on each being the true turning point rather than an ordinary dip. It also makes one forecast for next season, as a demonstration of the method, not a prediction about any player.",
    "ch4.panel.plain": "This section asks whether the pattern from the funnel above — countries that give young players more minutes at home tend to have a deeper pool in the strongest leagues — holds up across every country in the comparison set, not only the two shown earlier. Two seasons and a handful of countries is a small sample, so the range around the estimate is wide.",
    "ch4.gap.plain": "The gap between the home nation and a comparison country, in players per million, can be split into pieces that line up with three things this report already measures: how much young players play at home, how strong the domestic league is, and how old players are when they move abroad. This does not say which of the three causes the gap, only how much of it moves together with each one — the way a manager might note that a poor season lines up with an injury crisis without claiming the injuries alone explain it.",
    "ch4.export.plain": "This section asks whether players who reach one of the top-ranked leagues younger produce more there in their first two seasons, holding the strength of the league they came from fixed. Clubs are also more willing to take an early chance on a player they already rate highly, so the curve cannot separate that selection from any effect of leaving young.",
    "ch4.gk.plain": "Goalkeepers are counted the same way as outfield players throughout this report, with one difference: because a goalkeeper's save numbers swing around a lot from game to game, the model needs a bigger sample of shots faced before it trusts a keeper's own numbers over the league average.",

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
    "ch4.strength.oos.method.model": "Transfer-graph model",
    "ch4.strength.spearman": "Against {n} leagues in common, the model's medians and the UEFA multipliers correlate at Spearman's rho = {rho}.",
    "ch4.strength.disagreement": "{league}: model rank {model_rank} vs UEFA rank {uefa_rank} (m_L {model_median} vs multiplier {uefa}).",
    "ch4.strength.diagnostics": "R-hat ≤ {rhat}, minimum bulk ESS {ess}, {div} divergent transitions across {rows} player-seasons from {players} movers; fit in {runtime} s.",
    "ch4.strength.selection": "What the movers do not show: they are not a random sample — players tend to move up when they are good and down when they are older — so the within-player contrast describes the league difference for the kind of player who moves, and the age term absorbs only the part of that selection that is age. The interval is the model's uncertainty, not the selection's.",
    "ch4.strength.ranking": "The report's rankings keep the UEFA-coefficient multiplier throughout; the model above is shown alongside it as a check on that multiplier's own assumption — that continental results track player-level strength — not as a replacement for it.",
    "ch4.strength.ppc.summary": "Posterior predictive check",
    "ch4.strength.ppc.p": "Observed vs. replicated non-penalty goals plus assists per player-season {cite_ppc}: {obs_zero} vs {rep_zero} share of zeros, mean {obs_mean} vs {rep_mean}, 90th percentile {obs_p90} vs {rep_p90}.",
    "ch4.strength.ppc.fig_alt": "Bar chart comparing the observed and posterior-predictive-replicated distribution of non-penalty goals plus assists per player-season, grouped 0/1/2/3/4/5+.",

    "ch4.compare.h3": "Five methods, one task, five seasons",
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
    "ch4.series.design": "The series is modelled as a local level in state space {cite_ss}: the log of the season count follows a Gaussian random walk (σ ~ HalfNormal(0.2)), plus two ordered step changes δ₁, δ₂ in the level at unknown seasons τ₁ < τ₂ — on the series since 1995/96 one step is misspecified wherever the count both rises and falls, and a single step lands on whichever change buys more likelihood. NUTS only samples continuous parameters, so the τ pair is not sampled directly — every ordered pair of candidate seasons at least {margin} seasons from either end and from each other is marginalised out of the model with a single log-sum-exp potential, and each break's own posterior is recovered afterwards from the continuous draws, the standard move for a marginalised discrete parameter {cite_marg}; the changepoint idea itself is due to {cite_cp}, applied here to a batch, two-break setting. The report's \"break\" is the step that lowers the level; the other is the rise. Each step is dated to the season where its own marginal posterior peaks, and a step within ±5 % of no change is not dated. A rolling-origin backtest {cite_ro} refits the same local level without the step at each of {n_backtest} origins, forecasting one season ahead and scoring against the naive \"same as last season\" baseline — the honest forecaster's read, since no real origin knows in advance which side of a break it sits on. The one forecast below, from the same change-point-free model fitted on the full series, is a demonstration of the method on a count of players, not a statement about any player.",
    "ch4.series.fig_alt": "Line chart of the {nation} series with the change-point model's fitted level in a pale green band, a vertical rule marking the most probable break season with its posterior probability, and the one-season forecast with its 90 % interval at the right edge, past a dashed divider.",
    "ch4.series.caption": "How to read it: the black dots are the observed count, the pale green band the model\u2019s fitted level; the dashed rules are the most probable rise and fall seasons with their posterior probabilities; past the divider on the right, the one-season forecast with its 90 % interval.",
    "ch4.series.break.p": "For {nation}, the model dates the break to {season} ({prob} posterior probability), a ×{delta} ({lo}–{hi}, 90 % HDI) change in the level; the random walk's own innovation scale is σ = {sigma}.",
    "ch4.series.rise.p": "The rise before it is dated to {season} ({prob} posterior), a ×{delta} ({lo}–{hi}) change in the level. The most probable seasons for each:",
    "ch4.series.rise_after.p": "The recovery after it is dated to {season} ({prob} posterior), a ×{delta} ({lo}–{hi}) change in the level. The most probable seasons for each:",
    "ch4.series.rise.label": "rise",
    "ch4.series.fall.label": "fall",
    "ch4.series.earlier.p": "The other step is a fall too, dated to {season} ({prob} posterior), a ×{delta} ({lo}–{hi}) change: the level came down in two moves rather than rising first.",
    "ch4.series.not_a_fall": "Neither step lowers the level for {nation}; the later one is reported as the break.",
    "ch4.series.break.top_item": "{season}: {prob}",
    "ch4.series.contrast.p": "The same model, fit separately for the two contrast countries:",
    "ch4.series.contrast.item_unconverged": "{name}: not dated; the fit does not meet the convergence rule.",
    "ch4.series.contrast.item": "{name}: {season} ({prob} posterior), ×{delta} ({lo}–{hi}).",
    "ch4.series.contrast.item_rise": " Rise: {season} ({prob}), ×{delta}.",
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
    "ch4.series.diagnostics": "Change-point fit, {chains} chains × {draws} draws across {t} seasons: max R-hat {rhat}, minimum bulk ESS {ess}, minimum tail ESS {tail}, {div} divergent transitions. Every fit in this section is checked against a convergence rule fixed on 1 October 2026, before the refit (design/edition-refit-protocol.md): max R-hat ≤ 1.01, bulk and tail ESS ≥ 400, no divergent transitions, with a stricter step size only for a fit that fails.",
    "ch4.series.checks": "The peers' change-point fits and the forecast fits: {passed} of {n} pass. Backtest origins whose fit fails, kept in the scores: {bt_failed} of {bt_n}.",

    "ch4.panel.h3": "Cross-country youth-minutes panel",
    "ch4.panel.design": "For each of the {n_countries} peer countries, the {seasons} average U21 share of domestic-league minutes (x) against the {seasons} average top-9 players per million (y), one row per country. A Bayesian simple regression, y ~ Normal(α + β·x, σ), weakly informative priors ({chains} chains × {draws} draws {cite_pymc}), answers the between-country question of the youth-minutes page: does a country with a higher average U21 share also have a deeper pool, on average {cite_bda}. Cross-checked against a plain pooled least-squares slope on the full two-season panel (numpy polyfit, ignoring country structure entirely, {n_boot} percentile-bootstrap resamples; statsmodels is not a dependency here), which should agree in sign. Two seasons per country (previous and metrics; the current season is partial and left out); a peer whose top flight FBref does not track is absent from the panel, which is why n can be below the peer count.",
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
    "ch4.export.fig_alt": "Line chart: the fitted age-at-export curve with its 90 % band, home-nation exports as green points against every other peer export in grey, and a rug of every export's age along the axis.",
    "ch4.export.th.age": "Age",
    "ch4.export.th.y": "Expected G+A/90 (median)",
    "ch4.export.th.hdi": "90 % HDI",
    "ch4.export.beta": "β, per one-unit increase in origin-league strength (m_L): {beta} ({lo}–{hi}).",
    "ch4.export.home": "{Adj} exports' own country effect: {home_effect} ({lo}–{hi}); {adj} exports arrive at a median age of {age_home}.",
    "ch4.export.no_strength": "The same model, fit again without origin-league strength: the country-effect scale (σ_n) is {sigma_with} with the league term in the model and {sigma_without} without it — what moves between the two is what the league term is absorbing.",
    "ch4.export.lono_diag": "The refit meets the convergence rule (max R-hat {rhat}, minimum bulk ESS {ess}, minimum tail ESS {tail}, {div} divergent transitions).",
    "ch4.export.lono_diag_fail": "The refit does not meet the convergence rule (max R-hat {rhat}, minimum bulk ESS {ess}, minimum tail ESS {tail}, {div} divergent transitions), so nothing is read from it.",
    "ch4.export.lono": "Leave-one-nation-out: excluding {nation}'s own {n_excluded} exports (n = {n} remaining) and refitting, the 21-vs-24 difference is {diff} ({lo}–{hi}), against {full_diff} in the full fit.",
    "ch4.export.ppc.summary": "Posterior predictive check",
    "ch4.export.ppc.p": "Observed vs. replicated y (mean league-adjusted G+A/90 over the first two top-9 seasons): mean {obs_mean} vs {rep_mean}, sd {obs_sd} vs {rep_sd}, 10th percentile {obs_p10} vs {rep_p10}, 90th percentile {obs_p90} vs {rep_p90}.",
    "ch4.export.diagnostics": "R-hat ≤ {rhat}, minimum bulk ESS {ess}, {div} divergent transitions across {n} players; fit in {runtime} s.",
    "ch4.export.selection": "What this model does not separate: the corpus is not a random sample of players who could have left later. Players who leave earlier tend to be the ones judged ready earliest — a selection effect the age curve mixes with any genuine development effect of arriving young, and this report does not try to tell the two apart.",

    "ch4.validation.h3": "Validation & robustness",
    "ch4.validation.stub": "Each model in this pipeline carries its own validation next to where it is described; this section collects one headline diagnostic from each as it lands. So far:",
    "ch4.validation.m1": "Season-to-season model comparison (M1): rolling-origin evaluation over {n_origins} seasons, pooled RMSE favours {winner} ({rmse} vs {persistence_rmse} for persistence), the Bayesian model's 90 % interval covered {coverage} of observed values.",
    "ch4.validation.m2": "League strength (M2): R-hat ≤ {rhat}, {div} divergent transitions; out-of-sample log predictive density {lpd}; Spearman rho = {rho} against the UEFA multipliers.",
    "ch4.validation.m3": "The break and forecast (M4): the break dates to {season} ({prob} posterior) for {nation}, a ×{delta} level change; the plain local level {verb} the naive baseline on MAE ({mae_model} vs {mae_naive}) with {coverage} of the 90 % intervals covering the observed value over {n} rolling-origin backtests.",
    "ch4.validation.m3_nobreak": "The break and forecast (M4): the model dates no step for {nation} (its best candidate is within 5 % of no change); the plain local level {verb} the naive baseline on MAE ({mae_model} vs {mae_naive}) with {coverage} of the 90 % intervals covering the observed value over {n} rolling-origin backtests.",
    "ch4.validation.m3_unconverged": "The break and forecast (M4): the model dates no step for {nation} (its change-point fit does not meet the convergence rule); the plain local level {verb} the naive baseline on MAE ({mae_model} vs {mae_naive}) with {coverage} of the 90 % intervals covering the observed value over {n} rolling-origin backtests.",
    "ch4.validation.verb.beats": "beats",
    "ch4.validation.verb.not_beats": "does not beat",
    "ch4.validation.m4": "The youth-minutes panel (M3): across {n_countries} countries (country means, n = {n}), the between-country slope is {beta} per 10 percentage points of U21 share ({lo}–{hi}), R² = {r2}; a plain pooled OLS slope agrees in sign at {ols} ({ols_lo}–{ols_hi}) — the interval is wide because the panel is small. A within-country check (country-random-intercept fit on the full two-season panel) finds no signal: β_within = {beta_within}.",
    "ch4.validation.m5": "The gap decomposition (M5): ridge fit (α = {alpha}) on n = {n} peer countries; for {contrast}, the residual is {resid} of a {gap} gap — a decomposition of a correlation, not a causal accounting.",
    "ch4.validation.m6": "Age at export (M6): R-hat ≤ {rhat}, {div} divergent transitions across {n} players; β on origin-league strength is {beta}; leaving out {n_excluded} {adj} exports and refitting shifts the 21-vs-24 difference by {shift}.",

    "ch4.tracking.h3": "What tracking data would add",
    "ch4.tracking.plain": "Everything above is built from season tables, because that is what exists for every league in the benchmark. The next layer of data \u2014 every player\u2019s position ten times a second \u2014 exists for none of them publicly. So here is one match of it, from a different league, to show concretely what it answers that a season table cannot: not how many goals a player scored, but how he moves when he does not have the ball.",
    "ch4.tracking.caption": "How to read it: the pitch is drawn with both teams attacking left to right; every arrow is one off-ball run, from where it started to where it ended, coloured by the kind of run SkillCorner\u2019s model labelled it. Bright arrows were passed to; thick ones were received. Pick a team, switch run types on and off, hover an arrow for the player and what came of it. Data: {cite}, one A-League match, MIT licence; none of it enters any number in this report.",
    "ch4.tracking.p": "For a federation this is the layer that turns \u201chow many minutes\u201d into \u201cwhat kind of minutes\u201d: whether a young winger\u2019s runs are the runs the first team needs, whether an export\u2019s physical output matches his new league, whether a squad presses as one. The atlas cannot see it and does not pretend to; the pipeline is built so that a tracking feed, when a federation has one, becomes another table beside the season tables rather than a different project.",
    "ch4.related.h3": "Related methods and what was taken from them",
    "ch4.related.intro": "The methods below shaped this report's design. Each entry states what the method is, what this report took from it, and what was left out and why.",
    "ch4.related.novel": "One pairing here has no single citation behind it: the transfer-graph league-strength model (<a href=\"#league-strength\">§ League strength</a>) and the age-at-export curve (<a href=\"#export-age-model\">§ Age at export</a>) are fit independently and joined only through origin-league strength as a covariate — a within-player league-identification model feeding a spline-in-age production curve is, to the author's knowledge, this report's own combination, not drawn whole from any one method below.",
    "ch4.related.shrinkage": "Empirical-Bayes shrinkage of a sparse per-unit rate toward a group mean {cite} · taken: per-90 rates are shrunk toward the league-season median with a K = 10 phantom-match prior before the quality projection (§ Bayesian shrinkage) · left out: the fully hierarchical variance-component estimate the original method also supports, since one shared K fits this corpus's minutes floor well enough for a descriptive report.",
    "ch4.related.hierarchical": "Multilevel (partial-pooling) regression and posterior predictive checking as a model-diagnosis routine {cite} · taken: the league-strength and youth-panel models pool leagues and countries partially rather than fitting each alone or merging them into one, and the league-strength posterior predictive check (§ League strength) compares simulated to observed production · left out: model comparison by WAIC/LOO, since every model here is instead scored on seasons it never trained on (rolling-origin backtests), a stronger check for this report's purpose.",
    "ch4.related.nuts": "The No-U-Turn Sampler, the gradient-based MCMC method PyMC uses by default {cite} · taken: every Bayesian model in this report — league strength, model comparison, the change-point series, the youth panel — is fit with it and diagnosed on R-hat and divergences · left out: variational inference as a faster approximate alternative, since none of the four models is slow enough to need it.",
    "ch4.related.rapm": "Plus-minus and regularised adjusted plus-minus ratings, which isolate a player's contribution from teammates' and opponents' by regression {cite} · taken: the league-strength model's within-player logic — only a mover's own before/after change of league separates their level from the league's scoring environment — follows the same identification idea, applied to leagues rather than teammates · left out: an actual RAPM fit over lineup data, which this corpus's season-level tables (no lineups, no possession data) cannot support.",
    "ch4.related.changepoint": "Bayesian online change-point detection, a sequential method for locating a shift in a data-generating process {cite} · taken: unknown break seasons with a marginalised discrete location parameter, here two ordered change points (a rise and a fall) on a short batch series rather than sequentially · left out: the online, sequential setting and more than two change points, since one country’s Big-5 count per season is short and fixed.",
    "ch4.related.statespace": "The local-level model — a random walk plus noise for a slowly drifting series — in the state-space tradition {cite} · taken: the change-point model (§ Dating the break) is exactly this local level in log space, with two added step changes at the breaks · left out: a local linear trend or seasonal component, since the series is annual and too short for a trend term to be identifiable.",
    "ch4.related.rollingorigin": "Rolling-origin (time-series) cross-validation: refit on data up to each origin, score only on what came after it {cite} · taken: both the model-comparison exercise (§ Three models, one task) and the change-point backtest (§ Dating the break) are scored this way, never on a random split that could leak future seasons into training · left out: expanding-vs-sliding-window variants beyond the single expanding-window scheme, since the corpus's five metrics seasons leave little room to compare schemes.",
    "ch4.related.decomposition": "The Oaxaca–Blinder decomposition, splitting a gap between two groups' means into an explained and an unexplained part via a linear model {cite} · taken: the gap-decomposition exhibit (§ What the gap is made of) splits the per-capita gap into the three measured channels plus a residual the same way · left out: the detailed, coefficient-level decomposition of the explained share, since three channels are few enough to read directly off the coefficients themselves.",
    "ch4.related.clustervalidation": "The silhouette coefficient, a per-point measure of how well a clustering separates its groups {cite} · taken: used to sanity-check the PCA cluster counts per position group and projection before they were fixed (§ Cluster archetypes) · left out: a silhouette sweep reported in the text, since the chosen cluster counts are stable across position groups and projections.",
    "ch4.related.baselines": "Gradient-boosted trees and a small multilayer perceptron, two non-Bayesian machine-learning baselines standard in this kind of comparison {cite} · taken: both sit alongside the persistence, shrinkage and Bayesian models in § Three models, one task, on the same eight features and the same rolling-origin split · left out: hyperparameter search beyond scikit-learn's defaults (plus the MLP's 64/32 hidden layers), since the comparison's point is model family, not a tuned leaderboard.",
    "ch4.related.cies": "CIES Football Observatory’s periodic counts of footballers playing outside their home association {cite} · taken: the population of players who changed league, which the out-of-sample league-strength check tracks, and the framing of the atlas’s contribution on the front page · left out: CIES’s own counts, since the atlas computes its per-head and pathway measures from its own fetched tables.",
    "ch4.related.future.h4": "Next steps not attempted",
    "ch4.related.future.embeddings": "Player-season embeddings and graph methods over the transfer network — clubs and moves as a graph, players as nodes with learned representations — are natural next tools (graph neural networks, specifically) for a pool this size, but were not attempted here.",
    "ch4.related.future.tracking": "Event- and tracking-derived features (pressing intensity, progressive carries, expected threat) would sharpen the style axis beyond the five box-score numbers used here, but no tracking data source was available for this corpus.",
    # ---- glossary (Task 26D): ten terms, one plain sentence each with a
    # football example, before References.
    "glossary.h2": "Glossary",
    "glossary.intro": "Terms used in the <a href=\"#methodology\">sections above</a>, each in one plain sentence.",
    "glossary.per90.term": "Per 90",
    "glossary.per90.def": "A rate scaled to a full match: a player with three goals in five matches, each played the full ninety minutes, has a rate of 0.6 goals per 90 — it lets a player who came on as a substitute be compared fairly with one who started every match.",
    "glossary.minutes_share.term": "Minutes share",
    "glossary.minutes_share.def": "How much of a club's available playing time a player actually got, out of every minute the club's matches could have offered that season; a player who played every minute of every match has a minutes share of 100 percent.",
    "glossary.shrinkage.term": "Shrinkage",
    "glossary.shrinkage.def": "A way of not trusting a small sample too much: a player with only a handful of matches has his numbers pulled part of the way toward the league's typical number, the way a manager waits for more than one good game before trusting that a young player's form is real.",
    "glossary.multiplier.term": "League multiplier / league strength",
    "glossary.multiplier.def": "A number saying how much a goal, an assist or a minute is worth in one league compared with another; a striker's goal in a weaker league counts for less once it is adjusted by that league's own multiplier — the same idea as judging a transfer by the level the player is coming from.",
    "glossary.quality_adjusted.term": "Quality-adjusted",
    "glossary.quality_adjusted.def": "A player's raw numbers after they have been multiplied by the league multiplier above, so a rate earned in a strong league and one earned in a weaker league can be compared on the same footing.",
    "glossary.interval.term": "Interval (90 percent)",
    "glossary.interval.def": "A range around a number that shows how sure the model is, not a single guess; a ninety percent interval means the model thinks the true value falls inside that range about nine times out of ten.",
    "glossary.posterior.term": "Posterior",
    "glossary.posterior.def": "What the model believes about a number after it has seen the data, expressed as a range of plausible values rather than one single figure; the probability attached to a break season in this report is a posterior probability.",
    "glossary.oos.term": "Out-of-sample",
    "glossary.oos.def": "Checking a method only on matches, players or seasons it was not shown while it was being built — the way a manager judges a scouting report by what actually happens once the player signs, not by how well the report described what had already happened.",
    "glossary.cluster.term": "Cluster",
    "glossary.cluster.def": "A group of players whose season numbers look similar to each other and different from other groups, found automatically from the data rather than assigned by hand; a cluster is a style label such as \"high-volume scorers\", not a formal position.",
    "glossary.changepoint.term": "Change point",
    "glossary.changepoint.def": "The point in a series of seasons where the level genuinely shifts to a new one and stays there, rather than just one unusually high or low season on its own; this report finds one for the count of home-nation players in Europe's biggest leagues.",

    "close.kicker": "More from this atlas",
    "close.statement": "A federation does not need another opinion about its pool. It needs the same measured questions asked every summer, answered the same way, with the uncertainty on the page \u2014 and a name for every player the staff ask about.",
    "close.line": "This is one country, built from public data in the open. The pipeline takes a nationality code and a peer set; the same code produced the other editions linked below, and the comparison across them. With a federation\u2019s own data \u2014 tracking, academy, medical \u2014 the tables get deeper and the questions stay the same.",
    "close.link.brief": "The one-page brief",
    "close.link.pool": "Every player in the pool",
    "close.link.data": "Download the tables",
    "close.link.eng": "The England edition",
    "close.link.cze": "The Czech edition",
    "ch4.refs.h3": "References",

    "ch4.full_method": "Full method, figures and diagnostics",
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
    "dq.home_league_no_nation.label": "{home_league} rows without a nationality",
    "dq.home_league_no_nation.what": "Season-table rows in the {home_league} where FBref records no nationality — the highest rate of any league in this pipeline. Every “own nationals” share reads that column as its numerator while the denominator keeps the league’s full minutes, so those shares are floors, not point estimates.",
    "ch4.lim.h3": "Limitations of this analysis",
    "ch4.repro.h3": "Reproducibility",
    "ch4.repro.p": "The pipeline is public: <a href=\"{url}\">{url_short}</a>, code under the MIT licence. From a clean clone, <code>uv sync &amp;&amp; make restore-snapshot &amp;&amp; make figures &amp;&amp; make pages</code> rebuilds this edition from the committed data snapshot (commit {snapshot}; FBref tables fetched {fetched}); <code>make figures</code> refits the models with their seeds (about 15 minutes an edition), which reproduces the model outputs in the snapshot, and redraws the figures. The findings on the front page come from the cross-edition file: run <code>make restore-snapshot &amp;&amp; make figures</code> for every edition (<code>NATION=den</code>, <code>eng</code>, <code>esp</code>, <code>ger</code>, <code>nor</code> and the default), then <code>make nations</code>, then <code>make pages</code> for each edition. <code>make test</code> runs the automated checks; <code>make all</code> refetches everything and reruns the whole pipeline. Seed {seed} for every stochastic step: KMeans, every PyMC fit (random_seed), the bootstrap on the minutes share and the gap decomposition’s bootstrap ({seed} plus the contrast’s index). Fetchers cache raw pages; the render step never touches the network. Each question page names the module that computes its data in its metadata line.",
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
    "foot.kicker": "Barbora Šandová",
    "foot.body": "Data and code are in the repository below. Corrections are welcome by e-mail.",
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
    "lim.scope.body": "Transfer fees, market values, video and scouting reports are outside the public sources used here. The atlas describes statistical footprints and counts; it makes no selection or development recommendation.",
    "lim.tracking.title": "No event or tracking data",
    "lim.tracking.body": "Every feature is a season aggregate from free FBref tables; no event or tracking data enter any number.",

    # ---- generated: sensitivity descriptions
    "sens.baseline": "current multipliers from config/league_quality.yaml",
    "sens.one": "{league} multiplier {sign}20%",
    "sens.all": "every league multiplier {sign}20%",

    # ---- journal pass (29 September 2026): new strings
    "word.fall": "fall",
    "word.rise": "rise",
    "toc.availability": "Data availability",
    "toc.checks": "Internal automated checks",
    "hero.floors": "With a floor of 450 minutes the count is {n450} ({pm450} per million, rank {r450} of {n}); with 900 minutes it is {n900} ({pm900}, rank {r900}). ",
    "front.kicker": "Research · Player pool atlas, {adj} edition · {nation} and {n_peers} peers, {season}",
    "front.meta.aria": "About this page",
    "front.meta.published": "<span class=\"meta-k\">published</span> {published} · updated {updated} · version {version} (<a href=\"#changelog\">change log</a>)",
    "front.meta.status": "<span class=\"meta-k\">status</span> research, {status}. The one registered item is the Big-5 forecast for {season} (registered forecast: numbers committed at {commit} on {date}; commit times are self-reported).",
    "front.meta.data": "<span class=\"meta-k\">data</span> FBref season tables via soccerdata {soccerdata}, fetched {fetched}; Big-5 history from 1995/96, committed {history}; Wikipedia squad lists (CC BY-SA 4.0), Wikidata (CC0), {population}, UEFA association coefficients; snapshot commit {snapshot}. Sources, licences and hashes: <a href=\"#data-availability\">data availability</a>.",
    "front.meta.code": "<span class=\"meta-k\">code</span> <a href=\"{repo}\">{repo_short}</a>, data snapshot at {snapshot}; rebuild: <code>uv sync &amp;&amp; make restore-snapshot &amp;&amp; make figures &amp;&amp; make pages</code> (<a href=\"#reproducibility\">reproduction</a>)",
    "front.meta.cite": "<span class=\"meta-k\">cite as</span> Šandová, B. (2026). <em>{title}</em>. {url}, version {version}.",
    "front.meta.licence": "<span class=\"meta-k\">licence</span> code MIT; text, figures and data CC BY 4.0; player portraits are Wikimedia Commons files under their own licences (footer).",
    "front.contribution.h2": "The question and what this atlas adds",
    "front.contribution.p": "How many of a country’s players reach Europe’s top-ranked leagues, and how that number relates to the size of the country and to the path its players take, is usually studied in pieces. Research on player development looks inside clubs and national systems: at the environment of a Danish club with a record of producing senior players {cite_larsen}, at how selection and de-selection shape who progresses in German talent promotion {cite_gullich}, at the working relationship between youth and professional departments at elite European clubs {cite_relvas}, and at selection biases such as the relative age effect in European youth football {cite_helsen}. Counts of players abroad are published by the CIES Football Observatory {cite_cies}, without a per-head comparison of one nation against a fixed peer set. This atlas takes {nation} as a worked example and puts, on one set of definitions and from public data only, the per-head count of players in the {topn} top-ranked leagues beside measures of the path to them: youth minutes at home, the age and route of the first move abroad, playing time after it and the national-team squad. It is exploratory and descriptive and estimates no causal effect.",
    "front.cite.h2": "How to cite",
    "front.cite.p": "Šandová, B. (2026). <em>{title}</em>. {url}, version {version}. Code and data: <a href=\"{repo}\">{repo_short}</a>, data snapshot commit {snapshot}. Text, figures and data are CC BY 4.0; the code is MIT.",
    "front.changelog.h2": "Change log",
    "front.title": "{Adj} football player pool atlas",
    "page.means.h3": "What this means",
    "page.notshow.h3": "What this does not show",
    "page.meta": "Data snapshot: FBref tables fetched {fetched}, snapshot commit {snapshot} · code: <code>{code}</code> · status: exploratory, not pre-registered · <a href=\"#limitations\">all limitations</a>",
    "why_funnel.means": "The five measures are associations, measured the same way for {nation}, {a} and {b} and placed in the order of a player’s path. The order is not a causal chain: the page shows where {nation} differs from the two comparison countries, and it does not show which measure, if changed, would change the per-head count. Samples differ by measure and are given with each number.",
    "slide.1.read": "How to read it: one bar per country, sorted by players per million; the green bar is {nation}. The counts are administrative (every player who appeared, no sample), so the bars carry no interval; what moves them is the definition, given below.",
    "slide.1.means": "The count is {n_players} players for {pop} million people, an administrative count of who appeared, with no sampling interval. With a floor of 450 minutes {nation} has {n450} players ({pm450} per million, rank {r450} of {n}); with 900 minutes {n900} ({pm900}, rank {r900}). The rank describes presence in nine leagues chosen by UEFA coefficient; it does not measure the quality of the players or of the home league.",
    "slide.1.notshow": "Players in leagues outside the nine, however strong their clubs; how many minutes the counted players play beyond the two floors above; and why a country ranks where it does.",
    "slide.2.read": "How to read it: each row is one position group and age cohort, sorted by the size of the gap; the {code} column counts {adj} players with at least {min} minutes in a top-{topn} league, the bar the median count across the peer countries. Cells are counts of players, not estimates.",
    "slide.2.means": "{nation}’s shortfall against the peer median is largest for {group} aged {cohort}. The cells are single-digit counts with no interval: a difference of one or two players can come from a single transfer, loan or injury. The table shows where the counts differ, not how certain or how lasting the difference is.",
    "slide.2.notshow": "Goalkeepers, who are counted separately; players below {min} minutes; players outside the nine leagues; and anything about the players in a cell beyond their number.",
    "slide.3.read": "How to read it: one bar per country’s top flight, the share of its minutes played by its own nationals aged 21 or under at season start; green is {nation}. A country marked “not on FBref” has no top-flight tables on FBref.",
    "slide.3.means": "Under-21 nationals played {cze_pct} % of the {home_league}’s minutes in {season}{bound}. The between-country and within-country estimates above carry wide intervals and neither is a causal estimate, so the page describes where {nation} stands on this measure; it does not show that a higher share would raise the per-head count.",
    "slide.3.bound": " (a floor: with the rows FBref leaves without a nationality counted as own nationals it would be {hi} %)",
    "slide.3.notshow": "Minutes for under-21s in lower divisions or on loan abroad, minutes for foreign under-21s, and whether any young player was ready for more minutes, which no table here measures.",
    "slide.4.sideways": "The {n} sideways moves, by league: {leagues}.",
    "slide.4.read": "How to read it: each bar is a destination tier for the players abroad, with its player count in front and the median UEFA-coefficient multiplier of its leagues. The sideways moves are a subset of these bars and are listed under the chart.",
    "slide.4.means": "Of the {total} rows, {home_n} are at home and {abroad} abroad, {top9_n} of them in a top-{topn} league. The counts are administrative and a player counts once per position group he played in. They say where players were in one season; they do not say whether a move helped a player or how a player abroad would have done at home.",
    "slide.4.notshow": "Players in leagues this pipeline does not fetch (absent, not counted as abroad), loans and transfer fees, and the second club of a mid-season move, whose minutes are summed into one row.",
    "slide.4b.means_zero": "Across {n} exports from the peer countries, the age at the first top-{topn} season shows no measurable association with output in the first two seasons once origin-league strength and position are held fixed. The curve mixes selection with any effect of leaving young, so a flat curve does not show that the timing of a move is irrelevant to a career; it shows that output after arrival does not differ measurably by arrival age in this sample.",
    "slide.4b.means": "Across {n} exports from the peer countries, arriving at 21 goes with {diff} more league-adjusted goals plus assists per 90 than arriving at 24, with the interval above. The curve mixes selection (better players leave earlier) with any effect of leaving young, so it is an association and not an estimate of what an earlier move would do for a given player.",
    "slide.4b.notshow": "Players who never reached a top-{topn} league, output after the first two seasons, and minutes, which a player may not get at all after an early move.",
    "slide.5.means": "Once in a top-{topn} league, {adj} exports play a median {cze} % of their club’s minutes. Several countries have few exports, so the intervals are wide and the ranking of medians is loose. The measure describes playing time, not performance, and says nothing about the players who did not move.",
    "slide.5.notshow": "Performance per minute, the strength of a club within its league beyond a goals-scored proxy, and exports outside the nine leagues.",
    "slide.5.th.interval": "90 % bootstrap interval",
    "slide.6.read": "How to read it: one tile per squad player, tinted by the tier of the league where he played most minutes in {season}; the fold below compares the peers at the same tournament. Tier counts are administrative.",
    "slide.6.means": "{n_top9} of the {n} players {nation} took to the {event} played in a top-{topn} league. The share is a count over one squad, so one player moves it by about {pp} percentage points, and the comparison covers only the {n_peers} peers that reached the tournament, not the whole peer set.",
    "slide.6.notshow": "Players who were not selected, how the squad played, and whether a player’s league tier reflects his own level or his club’s.",
    "slide.7.no_change": " The 90 % interval for the {kind} includes ×1.00, so the {kind} is not distinguishable from no change at that level.",
    "slide.7.diag": "Change-point fit: max R-hat {rhat}, minimum bulk ESS {ess}, minimum tail ESS {tail}, {div} divergent transitions, within the convergence rule fixed before the refit of 1 October 2026 (R-hat ≤ 1.01, bulk and tail ESS ≥ 400, no divergences).",
    "slide.7.diag_fail": "Change-point fit: max R-hat {rhat}, minimum bulk ESS {ess}, minimum tail ESS {tail}, {div} divergent transitions; this fails the convergence rule fixed before the refit of 1 October 2026 (R-hat ≤ 1.01, bulk and tail ESS ≥ 400, no divergences), so no step is dated.",
    "slide.7.means": "The model’s most probable season for the {kind} is {break_season} (posterior {break_prob}; level ×{delta}, 90 % HDI {lo}–{hi}). A break model describes the timing of a change in level; it identifies no cause, and the posterior says how sure the model is of the season. The forecast is the one registered item in the atlas and is scored only when the season’s tables are final.",
    "slide.7.unconverged.means": "The change-point fit for this series does not meet the convergence rule fixed before the refit of 1 October 2026, even with the stricter step size, so the atlas dates no change in the level. The forecast is the one registered item in the atlas and is scored only when the season’s tables are final.",
    "slide.7.unconverged.notshow": "Players in leagues outside the Big-5 (the top-{topn} count on the per-head page is wider), when or why the level changed, and any season beyond the one registered forecast.",
    "slide.7.nobreak.means": "The model dates no step: its best candidate is {break_season} (posterior {break_prob}; level ×{delta}, 90 % HDI {lo}–{hi}), within 5 % of no change. A break model describes the timing of a change in level; it identifies no cause. The forecast is the one registered item in the atlas and is scored only when the season’s tables are final.",
    "slide.7.nobreak.notshow": "Players in leagues outside the Big-5 (the top-{topn} count on the per-head page is wider), why the level changed, and any season beyond the one registered forecast.",
    "slide.7.notshow": "Players in leagues outside the Big-5 (the top-{topn} count on the per-head page is wider), why the level changed, and any season beyond the one registered forecast.",
    "slide.8.table_note": "— : no value; for the squad row, the country did not play at the tournament.",
    "slide.8.means": "The table gives the seven measures side by side, measured the same way for the three countries, so a difference in the table is a difference in the data. With three countries no measure can be tied statistically to the per-head count, and the rescaled chart exaggerates small differences.",
    "slide.8.notshow": "Why the three countries differ, how the measures move over time, and any country outside the three.",
    "slide.8b.means": "{nation} had {n_gk} goalkeepers with at least {min} minutes in the top-{topn} leagues. The age comparison rests on {n_gk_age} goalkeepers, too few to tell two medians apart, and the per-million rank rests on counts of a few goalkeepers per country, where one player moves a country by several places.",
    "slide.8b.notshow": "Goalkeepers’ performance separated from their defence, goalkeepers in leagues outside the nine, and back-up goalkeepers below {min} minutes.",
    "slide.8c.sign_neg": "In this {n}-country fit the league-strength coefficient is negative ({b2} per unit of the league multiplier m_L): a weaker home league goes with more players per million in the top-ranked leagues, so a contrast country whose league is weaker than {nation}’s (m_L {home_x2}) gets a positive league-strength contribution.",
    "slide.8c.sign_pos": "In this {n}-country fit the league-strength coefficient is positive ({b2} per unit of the league multiplier m_L): a stronger home league goes with more players per million in the top-ranked leagues.",
    "slide.8c.x3_zero": "The export-age channel is zero for these contrasts because {countries} share the same median age at the first top-{topn} season among recent entrants ({age}); it carries nothing by construction, not by estimate.",
    "slide.8c.shares": "Shares of a gap can add up to more than 100 % when the residual is negative, that is when the channels together predict more than the observed gap.",
    "slide.8c.means": "The decomposition says how the gap lines up with three measured channels across {n} countries, with the contributions and intervals above. With {n} countries, three correlated channels and a ridge penalty, the split is indicative: it describes an association and gives no estimate of what would change if one channel changed.",
    "slide.8c.notshow": "Channels the model does not include (coaching, money, scouting), countries outside the {n}, and a causal share of the gap for any channel.",
    "slide.9.read": "How to read it: each card shows one player’s {season} numbers, his cluster in the style and quality maps, the change since the previous season and his nearest historical analogs; the rule that chose him is at the foot. The atlas below plots every player-season of {season}.",
    "slide.9.means": "The cards are examples chosen by rule, not a ranking or a selection: a player appears because he comes first under a rule, and a later rule skips anyone already chosen. A card’s numbers are one season’s; the analogs show what followed for similar player-seasons, not what will follow for this player.",
    "slide.9.notshow": "Players the rules did not pick (the full pool is in the list below), anything beyond the five season numbers, and any prediction for a player.",
    "ch3.card.change": "change",
    "ch3.card.one_season": "one season",
    "slide.10.means": "Between the two seasons {up} players moved up a tier, {down} moved down, {entered} are new to the pool and {left} are no longer in a covered league. These are counts of one season-to-season change; without earlier seasons there is no baseline for how many moves a typical year shows, so the balance of ups and downs is not a trend.",
    "slide.10.notshow": "Why a player moved, whether a move down was a loan or an injury, and players outside the covered leagues.",
    "pred.registration": "registered forecast: numbers committed at {commit} on {date}, before the {season} outcome exists; commit times are self-reported.",
    "autumn.quote_fn": "Original ({source}): “{quote}”.",
    "autumn.source.secondary": "Secondary source; the federation’s own release was not located",
    "brief.th.n": "n ({code})",
    "brief.n.youth": "{players} players, {clubs} clubs",
    "brief.n.age": "{minutes} league minutes",
    "brief.n.move": "{n} players",
    "brief.n.abroad": "{n} players abroad",
    "brief.n.pm": "{n} players",
    "brief.limits": "What none of this shows is listed once, under <a href=\"#limitations\">limitations</a> on the methodology page.",
    "downloads.hash": "SHA-256, first 16 hex digits",
    "ch2.c.label.min": "Median share of the club’s minutes",
    "ch2.c.label.goals": "Median club goals-scored percentile within its league (club-strength proxy)",
    "ch4.availability.h3": "Data availability",
    "ch4.availability.p": "The processed tables behind every page are committed in the public repository under <code>data/snapshot/{nation_dir}/</code> (snapshot commit {snapshot}) and listed with their SHA-256 prefixes under <a href=\"#downloads\">Download the tables</a>. Raw FBref pages are not redistributed; FBref’s own terms of use apply to its data. Squad lists from Wikipedia are CC BY-SA 4.0 and are credited as such; Wikidata is CC0; Eurostat data are reused with attribution; the UEFA coefficients are public rankings quoted with their source. League or club headshots are not used: a portrait appears only where a Wikimedia Commons file exists, credited in the footer with a link to its file page. The atlas’s own text, figures and data are CC BY 4.0 and its code MIT.",
    "ch4.checks.p": "{n_tests} automated tests (pytest) check the pipeline and the site build on every change. No external review of the atlas has taken place.",
    "glossary.top9.term": "Top-9 leagues",
    "glossary.top9.def": "The nine leagues ranked 1–9 in UEFA’s men’s association coefficient ranking on the fetch date (England, Italy, Spain, Germany, France, Portugal, Belgium, the Netherlands, Türkiye); the Big-5 are the first five.",
    "glossary.export_age.term": "Export age (two measures)",
    "glossary.export_age.def": "Age at the first season with real playing time in a foreign league (the pathway measures and the brief), and age at the first season in a top-9 league (the destination tables and the gap decomposition, recent entrants only); the two are different numbers for the same players.",
    "glossary.pools.term": "Players counted",
    "glossary.pools.def": "Per head: players with the country’s FBref nationality who appeared in a top-9 league in the season, all positions. Destinations: {adj}-eligible outfield players with at least 450 minutes in a covered league, one row per position group. Season changes: the same players, one row per player. Pool list: every {adj}-eligible player with a season row. Country page: every professional FBref lists for the country, including those in leagues without tables.",
    "glossary.sideways.term": "Sideways move",
    "glossary.sideways.def": "A player abroad in a league whose UEFA-coefficient multiplier is no higher than his home league’s.",
    "glossary.stepping.term": "Stepping-stone league",
    "glossary.stepping.def": "A covered league below the top nine that is no peer’s home league; in this configuration only the German second tier.",
    "glossary.hdi.term": "90 % HDI and bootstrap interval",
    "glossary.hdi.def": "A 90 % highest-density interval is the narrowest range holding 90 % of a Bayesian model’s posterior; a 90 % bootstrap interval is the 5th to 95th percentile of an estimate recomputed on resampled data.",
    "lim.money.title": "Money",
    "lim.money.body": "Transfer fees, wages and academy budgets play no part in any number in the atlas.",
    "lim.academy.title": "Academies and coaching",
    "lim.academy.body": "How academies and coaching work day to day is invisible to every public source used here.",
    "lim.agents.title": "Agents and how moves happen",
    "lim.agents.body": "How a move abroad is arranged, and by whom, happens off every table this pipeline reads.",
    "lim.arrow.title": "Direction of the arrow",
    "lim.arrow.body": "A low share of playing time for young players at home could help cause a thin generation or be a symptom of one; every pathway measure is an association measured the same way for every country.",
    "lim.causal.title": "Exploratory, not causal",
    "lim.causal.body": "The atlas is exploratory and was not pre-registered, apart from one forecast. Break models describe the timing of a change; decompositions and panels describe associations; the reform dates on the cross-edition page are timing markers. No page estimates what a change in policy would do.",
    "lim.per_head.title": "The per-head count and its floor",
    "lim.per_head.body": "The per-head count includes every player who appeared in a top-9 league, however few minutes he played; the per-head page gives the same count at 450 and 900 minutes.",
    "lim.nationality.title": "Nationality gaps in the home league",
    "lim.nationality.body": "FBref records no nationality for part of the home league’s rows. Every “own nationals” share counts those players as foreign while keeping their minutes in the total, so the home under-21 share is a floor, with the upper bound given where it is used (see the data-quality log).",
    "lim.club_proxy.title": "Club-strength proxy",
    "lim.club_proxy.body": "Club strength is the club’s goals-scored percentile within its league, not an Elo rating: ClubElo was unreachable at run time, and goals scored mixes attacking style with overall strength.",
    "lim.small_n.title": "Small samples",
    "lim.small_n.body": "Several measures rest on few units: cohort cells are single-digit counts, the goalkeeper comparison has a handful of players per country, the gap decomposition and the youth panel have eight or nine countries, and the season-change panel has two seasons. Their intervals, where given, are wide; counts without an interval are administrative.",
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
    "how much playing time young players get at home",
    "how strong the domestic league is",
    "how old players are when they move abroad",
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
            # The Czech edition was retired on 2026-09-21 (the site publishes
            # English only). The strings stay in cs.yaml for a possible return,
            # but they are no longer a contract: a key without a Czech entry
            # falls back to the English one instead of failing the render.
            cs = cs or load_cs()
            self.strings = {**EN, **cs["strings"]}
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
        """Translate an English data label; an unknown one passes through."""
        if self.lang == "en" or not label:
            return label
        return self.terms.get(label, label)

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
