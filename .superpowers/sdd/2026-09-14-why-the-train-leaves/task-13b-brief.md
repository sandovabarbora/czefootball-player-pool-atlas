# Task 13b: The page as a presentation — nine questions, one proof each

Author's direction (verbatim, translated): "still a billion charts — I would put questions
and then something like a presentation: here this happens, and this is why we know it";
"and how they do it elsewhere and why it works there (Norway)". Reader: an FA insights
person opening the link cold.

## Structure after this task (template `templates/report.html.j2`)

masthead (as is) → hero (as is, Task 11/12) → **nine slides** → "Explore the data"
(folded; today's chapters I–III material) → chapter IV Method (as is).

Each slide is `<section class="slide" id="q<N>">` with exactly four parts, in this order:
1. `h2.slide-q` — the question (EN/CS i18n key `slide.N.q`).
2. `p.slide-a` — the answer: one sentence with the headline number in `<strong>` (`slide.N.a`,
   all numbers as placeholders filled from the context — never typed).
3. `div.slide-proof` — **one** exhibit (listed per slide below), reusing today's markup/macros;
   nothing else.
4. `p.slide-how` — one line, sans small text, prefixed with a small-caps "How we know":
   the data + method + link to the methodology anchor (`slide.N.how`, EN/CS).

No other prose inside a slide. Slides are separated by a hairline and generous space;
on phones everything stacks. The Contents rail lists the nine questions (short forms via
`toc.q<N>` keys) and then "Explore" and "Method".

## The nine slides (numbers from the context; the values in parentheses are what the
current data give and are for orientation only — do not type them)

1. **Is the Czech pool thin?** — answer: rank {rank} of {n} at {pm} per million; {top}
   leads at {top_pm}. Proof: the per-capita rows (`.capita` block from chapter I).
   How: "Distinct players with ≥ {min} minutes on {season} rosters of the {topn}
   strongest leagues ÷ population (Eurostat 2024); every country counted the same way."
2. **Where exactly is it thin?** — answer: the largest cohort gap: {group} aged {cohort},
   {cze} Czech players vs a peer median of {peer}. Proof: the cohort gap list
   (`cohort_gaps`, top 5 rows as a compact table: group · cohort · CZE · peer median).
   How: "Age at season start; cohorts U22 / 23–25 / 26–29 / 30+; ≥ {min} minutes."
3. **Do young players get minutes at home?** — answer: U21 share of domestic-league
   minutes {cze_pct} % vs {best_name} {best_pct} % (best peer). Proof: exhibit A rows
   (youth exposure per country, bars). How: "Share of all league minutes played by
   players aged ≤ 21 at season start, {season}, per domestic top flight."
4. **Where do Czech players go when they leave?** — answer: {abroad} of {total} play
   abroad; {top9_pct} % in the {topn} strongest leagues, {sideways_pct} % moved sideways
   (to a league no stronger than the Czech one). Proof: exhibit E buckets (bars).
   How: "Destination league of every Czech-eligible player's {season} row; sideways =
   destination multiplier ≤ Czech league multiplier."
5. **How do they fare there?** — answer: Czech exports keep {cze} % of their club's
   minutes ({rank} of {n}). Proof: exhibit C rows. How: "Median share of club minutes
   for players abroad, per country of origin."
6. **What is the World Cup squad built from?** — answer: {cze_pct} % of the {event}
   squad plays in the {topn} strongest leagues; {best_name} {best_pct} %. Proof: the
   exhibit F stacked bars. How: "Wikipedia squad lists matched to {season} league rows;
   tier = league of the most-minutes row."
7. **When did the train leave?** — answer: Czech players with ≥ {min} minutes in the
   Big-5 leagues peaked at {peak_n} in {peak_season}, fell to {low_n} in {low_season},
   {last_n} in {last_season}. Proof: `outputs/big5_series.svg` (Task 13a; copy into
   `docs/` via `site/build.sh` like the other SVGs; add it to the `svg_labels.py` list
   only if it carries English labels that need CS — check). How: "FBref Big-5 player
   tables 2000/01 → {last_season}; peers on the same rule; the golden-generation
   names are the most-minutes Czech players of each peak season: {golden}."
8. **How do Norway and Denmark do it?** — a comparison table `table.peer-compare`,
   rows = the six numbers above (per million · U21 share · export age (recent) ·
   sideways % · exports' minutes share · WC squad top-9 %; plus Big-5 count now),
   columns = CZE · NOR · DEN (values from the same context objects; `peer_compare`
   built in `render.py::_build_peer_compare(countries=["CZE","NOR","DEN"])`). Answer
   sentence: "On the same six numbers Norway gives U21 players {nor_u21} % of domestic
   minutes against {cze_u21} % and sends {nor_top9} % of its squad to the {topn}
   strongest leagues against {cze_top9} %." (descriptive: what differs, not why in a
   causal sense; the "why it works there" is the reader's inference from the same
   metric — say so in the how-line). How: "Same definitions, same seasons; a comparison,
   not a causal claim."
9. **Who are the players?** — answer: {n} cards chosen by six rules. Proof: the roster
   tiles (Task 10) — rows and kickers as today; the rules fold stays.

## Explore the data (folded)
`<section class="explore" id="explore">` with `<details class="fold">` per block:
Benchmark heatmap · Cluster archetypes (atlases + accordion) · Trajectories (movers) ·
Pathways exhibits A–F in full (tables) · Historical analogs · Player index. Move today's
markup for these blocks inside; keep ids (`benchmark`, `observations`, `clusters`,
`trajectories`, `pathways`, `exhibit-f`, `analogs`, `players`) so deep links work.
`site/enrich_index.py` regexes that build cluster accordions / player index / analogs
folds must still match — run the build and fix `want`s honestly.

## Remove from the main flow
The "argument" list (its content is now slides 1–7; delete `findings.*`/`argument`
markup and keys), the "For a federation" section stays but moves **after** the slides
(before Explore). Observations (chapter I) go into Explore. The chapter dividers I–III
disappear; chapter IV keeps its divider and content.

## i18n
All `slide.N.q/a/how`, `toc.qN`, `explore.*` keys EN + CS; placeholders identical.
CS questions natural ("Je český fond tenký?", "Kde přesně?", "Dostávají mladí minuty
doma?", "Kam čeští hráči odcházejí?", "Jak se jim tam daří?", "Z čeho je postavená
nominace na MS?", "Kdy vlak odjel?", "Jak to dělají Norsko a Dánsko?", "Kdo to je?").

## Verify
`uv run pytest -q` green (update `SECTION_IDS`/TOC tests); render EN+CS; `./site/build.sh`
prints ok for both; screenshots (one tab, close it) at 1440 px of: hero + slide 1,
slides 6–8, Explore folded; and ≤ 600 px of slides 1–2. Commit plain message, no AI
trailer; add source/config/template/site/css/js/tests + rebuilt `docs/` html/css/js/svg;
never `data/`, `outputs/`.
