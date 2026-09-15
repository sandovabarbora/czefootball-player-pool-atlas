# Task 13b report: the page as a presentation — nine slides

## Status
Done.

## Commit
`06f4d2f` — "Restructure the report as nine question/answer/proof slides (Task 13b)"

Branch `v1.2`, worktree `.worktrees/v1_2`. 24 files changed. Source/config/template/
site/css/js/tests changed, plus the rebuilt `docs/` html/css/js/svg (including two new
files, `docs/big5_series.svg` and `docs/cs/big5_series.svg`). No `data/` or `outputs/`
files staged; `.superpowers/` left untracked (pre-existing, unrelated to this task). No
AI attribution trailer on the commit, per instruction — verified with
`git log -1 --format="%B"`.

Files touched:
- `src/render.py` — deleted `_build_findings`; added `_build_big5`,
  `_country_sideways_share`, `_build_peer_compare`; wired `big5`/`peer_compare` into
  `build_context` and `build_context_from_fixtures`.
- `src/i18n.py` + `config/i18n/cs.yaml` — removed `findings.*`/`finding.N.*` and other
  keys that lost every call site in the restructure (`toc.summary`, `toc.observations`,
  `toc.cards_chapter`, `toc.cards`, `toc.short.cards`, `toc.short.analogs`, `ch1.framing`,
  `ch1.capita.h4`, `ch1.capita.note`, `ch1.continue`, `ch2.aria/title/synopsis`,
  `ch2.a.cze`, `ch2.c.cze`, `ch2.c.h4.min/goals`, `ch2.e.buckets`, `ch3.aria/title/synopsis`,
  `ch3.cards.h2/framing`); added `slide.how_label`, `slide.1..9.q/a/how`, `slide.7.alt`,
  `cohortgap.th.*`, `peer_compare.*`, `explore.h2`, `toc.q1..q9`, `toc.explore`.
- `templates/report.html.j2` — nine `<section class="slide" id="qN">` blocks between
  the hero and "For a federation"; `card_article` macro hoisted to the top-level macro
  block (used by slide 9, needed before its old location); "Explore the data"
  (`id="explore"`) with six top-level `<details class="fold">` blocks carrying the old
  `benchmark`/`observations`/`clusters`/`trajectories`/`pathways`/`exhibit-f`/`analogs`/
  `players` ids; TOC (sticky + mobile) rebuilt as q1..q9 + Explore + Method; chapter
  dividers II and III removed (IV unchanged).
- `templates/style.css` — `.slide`/`.slide-q`/`.slide-a`/`.slide-proof`/`.slide-how`/
  `.slide-how-label`, `table.peer-compare` right-alignment, `.explore`/`.explore-block`.
- `site/build.sh` — added `big5_series.svg` to the required-file check and the copy step.
- `site/svg_labels.py` — added `big5_series.svg` to `FILES`; T entries for its three
  axis labels; a dynamic pattern for its suptitle (mirrors the PCA caption pattern);
  extended `KEEP` for the `"YYYY/YY: N"` point annotations; **fixed a pre-existing gap**
  in the text-node regex that only handled `translate(...) scale(...)` transforms — the
  Big-5 figure's y-axis labels use `translate(...) rotate(-90) scale(...)` (matplotlib's
  rotated-ylabel form), which nothing in the codebase had exercised before. Generalised
  the regex and added a `transform="rotate(...)"` on the output `<text>`.
- `site/enrich_index.py` — CS `<img src="../...">` → same-dir rewrite regex extended to
  `big5_series.svg` (count 4 → 5); top-bar nav's dead `#cards` link (the heading it
  pointed at no longer exists) repointed to `#q9`; clamp-candidate selector excludes
  `.slide-a`/`.slide-how` so the short one-sentence slide text never gets a spurious
  "More" toggle.
- `tests/test_render.py` — rewrote `SECTION_IDS`, the TOC test, and every
  findings/argument test; added tests for the nine slides' q/a/proof/how structure and
  order, "For a federation" sitting after the slides and before Explore, Explore's six
  folds keeping the old ids, `peer_compare`'s shape, and `big5`'s peak/low/last/golden.
- `tests/test_site_build.py` — `big5_series.svg` added to the Czech-figure-translation
  check.

## The brief/data conflict I resolved (not a NEDS_CONTEXT case)

Slide 8's brief asks for a CZE/NOR/DEN table with "sideways %" as one of six numbers,
"values from the same context objects." But `pathways.json`'s `destinations` exhibit —
the only place "sideways %" exists — is computed **only for Czechia**
(`src/pathways.py::destinations()` filters on the `czech_eligible` column, which is
Czech-specific by construction). There is no NOR/DEN sideways number anywhere in the
data.

I judged this resolvable rather than a genuine standoff: the features frames
(`features_{FW,MF,DF}.parquet`, already loaded by `load_data()`) carry a `nation`
column and everything `destinations()` needs (league, minutes, multiplier), so the
same rule generalises to any country with a domestic league on file in
`config/leagues.yaml`'s `peer_domestic` map. `_country_sideways_share` reapplies it
(same `MIN_MINUTES_DESTINATIONS` floor, same dedupe, same "destination multiplier ≤
domestic multiplier" test) for NOR (0.22) and reproduces the existing CZE number
(0.185) exactly as a sanity check. This runs inside `src.render` — no other pipeline
stage was invoked. Denmark has no row in `squad_lens.json` at all (not in the fetched
2026 World Cup squad tables), so that one cell renders "—", same convention as every
other missing-data cell on the page (cohort table, exhibit F detail table).

## Tests

`uv run pytest -q -p no:warnings` → **142 passed, 0 failed** (offline, no network,
`data/processed/` present so the real-context tests ran too, not skipped).

`uv run --with ruff ruff check src/render.py src/i18n.py site/svg_labels.py
site/enrich_index.py tests/test_render.py tests/test_site_build.py templates/` → 4
pre-existing findings, none in code I touched (E402 import order in `svg_labels.py`'s
`sys.path.insert` preamble, an unsorted import block and an ambiguous `l` loop variable
in a `test_render.py` function I didn't modify). Not fixed — out of scope, pre-dates
this task.

## Render + build

`uv run python -m src.render` → wrote `outputs/index.html` (358 944 bytes) and
`outputs/cs/index.html` (366 280 bytes) cleanly, both languages. `./site/build.sh` →
`ok (en): 17 cards, 10 with portraits` / `ok (cs): 17 cards, 10 with portraits`, no
`FAILED:` lines from either `enrich_index.py` run or `svg_labels.py`.

Verified with ad-hoc scripts (not part of the suite, sanity checks only):
- Both languages render with no `{{`/`{%` leakage, no visible `None`/`nan`.
- The template tolerates `pathways.destinations = None` and `squad_lens = {}` (slides 4
  and 6 render their heading/how-line with an empty proof, matching the pre-existing
  "missing source renders nothing extra" convention).
- `check_complete()` / `check_placeholders()` on `cs.yaml` both clean (the only
  placeholder-drop warnings, `hero.sublead.gap`'s `s` and `obs.2.body`'s `plural`/`s`,
  are pre-existing English pluralisation markers Czech doesn't need — not from this task).

## The nine rendered EN answer sentences (real data, 2025/26 metrics)

1. **Is the Czech pool thin?** — Czechia ranks **7th of 9** countries at 2.39 per
   million; Denmark leads at 12.58.
2. **Where exactly is it thin?** — The largest cohort gap: **Midfielders aged 23-25**,
   2 Czech players vs a peer median of 6.
3. **Do young players get minutes at home?** — U21 share of domestic-league minutes
   **6.4 %** vs Denmark 15.3 % (best peer).
4. **Where do Czech players go when they leave?** — **27 of 192** play abroad; 63 % in
   the 9 strongest leagues, 18 % moved sideways (to a league no stronger than the
   Czech one).
5. **How do they fare there?** — Czech exports keep **50 %** of their club's minutes
   (3rd of 9).
6. **What is the World Cup squad built from?** — **35 %** of the 2026 FIFA World Cup
   squad plays in the 9 strongest leagues; Switzerland 88 %.
7. **When did the train leave?** — Czech players with ≥ 450 minutes in the Big-5
   leagues peaked at **26** in 2007/08, fell to 6 in 2015/16, 10 in 2025/26.
8. **How do Norway and Denmark do it?** — On the same six numbers Norway gives U21
   players **12 %** of domestic minutes against 6 % and sends 65 % of its squad to the
   9 strongest leagues against 35 %.
9. **Who are the players?** — **17 cards** chosen by six rules.

(Czech render carries the same numbers with decimal commas and natural CS phrasing,
e.g. slide 1: "Česko je 7. z 9 zemí s 2,39 na milion; Dánsko vede s 12,58." — spot-checked
all nine, including a phrasing fix on slide 3 where a first draft used the wrong case
after "proti" — "proti Dánsko" → rewritten as "nejlépe Dánsko 15,3 %" to avoid the
declension error entirely.)

## Screenshots

One tab (`http://127.0.0.1:<port>/index.html` — the browser extension can't open
`file://` URLs, so I served `docs/` locally with `python3 -m http.server` for the
screenshot pass only; the server was killed and the tab closed afterward, nothing
persisted). All paths below are local to this machine, not committed:

- 1440 px, masthead:
  `/var/folders/ls/40_y__c56qnfsnm055rhsxsc0000gp/T/claude-chrome-screenshots-KY5dGS/screenshot-1789397931501-90.jpg`
- 1440 px, hero (navy band, headline "2.39" figure, cast strip):
  `/var/folders/ls/40_y__c56qnfsnm055rhsxsc0000gp/T/claude-chrome-screenshots-KY5dGS/screenshot-1789398303524-104.jpg`
- 1440 px, hero tail → slide 1 (question, answer, per-capita bars):
  `/var/folders/ls/40_y__c56qnfsnm055rhsxsc0000gp/T/claude-chrome-screenshots-KY5dGS/screenshot-1789398309721-106.jpg`
- 1440 px, slide 3 (youth exposure bars):
  `/var/folders/ls/40_y__c56qnfsnm055rhsxsc0000gp/T/claude-chrome-screenshots-KY5dGS/screenshot-1789397971305-97.jpg`
- 1440 px, slide 6 (World Cup squad tier bars):
  `/var/folders/ls/40_y__c56qnfsnm055rhsxsc0000gp/T/claude-chrome-screenshots-KY5dGS/screenshot-1789398000327-103.jpg`
- 1440 px, slide 6 tail + slide 7 (Big-5 line chart):
  `/var/folders/ls/40_y__c56qnfsnm055rhsxsc0000gp/T/claude-chrome-screenshots-KY5dGS/screenshot-1789397943884-93.jpg`
- 1440 px, slide 8 (CZE/NOR/DEN `table.peer-compare`, DEN's WC-squad cell showing "—"):
  `/var/folders/ls/40_y__c56qnfsnm055rhsxsc0000gp/T/claude-chrome-screenshots-KY5dGS/screenshot-1789398357590-110.jpg`
- 1440 px, "Explore the data" folded (six closed `<details>`: Benchmark vs peer
  countries, Cluster archetypes, Trajectories, Why does the train leave?, Historical
  analogs, Player index):
  `/var/folders/ls/40_y__c56qnfsnm055rhsxsc0000gp/T/claude-chrome-screenshots-KY5dGS/screenshot-1789397977971-99.jpg`
- 390×844 (narrowest tested width), slide 1:
  `/var/folders/ls/40_y__c56qnfsnm055rhsxsc0000gp/T/claude-chrome-screenshots-KY5dGS/screenshot-1789397985711-100.jpg`
- 390×844, slide 2 (compact cohort-gap table, one column, no horizontal scroll):
  `/var/folders/ls/40_y__c56qnfsnm055rhsxsc0000gp/T/claude-chrome-screenshots-KY5dGS/screenshot-1789397991088-101.jpg`

All confirm: one column at phone width, no horizontal scroll; navy/cream/oxblood intact;
the CZE row/column highlighted consistently; the TOC scroll-spy updates against the new
q1..q9 ids.

## Design decisions worth flagging

- **What moved into a slide vs. stayed in Explore.** Each slide's proof is the exhibit
  *moved* out of its old chapter location, not duplicated — e.g. the per-capita bars
  live only in slide 1; Explore's "Benchmark vs peer countries" fold has the heatmap
  and full cohort tables but not the bars again. Exhibit C's two bar charts split: the
  minutes-share bars (slide 5's proof) vs. the goals-percentile bars (stayed in
  Explore, since slide 5 only claims one number). Same pattern for exhibit A (bars →
  slide 3, note stays in Explore) and exhibit E/F (bars → slides 4/6, prose/detail
  table/examples stay in Explore).
- **Observations** nests inside the "Benchmark vs peer countries" fold (its own
  pre-existing `<details>`, unchanged) rather than getting a seventh top-level fold —
  the brief lists six top-level blocks and separately says "Observations (chapter I)
  go into Explore," which this satisfies without adding a block not in the list.
- **`for-federation` tile hrefs** updated: "Benchmark" → `#q1` (was `#benchmark`,
  which now points at folded content), "Tournament squad lens" → `#q6` (was
  `#exhibit-f`, likewise now folded); "Pathways" stays `#pathways` and "Models,
  validated" stays `#methodology` since those already point at full-breadth or
  unchanged content.
- **Dead i18n keys**: cleaned up beyond just `findings.*`/`finding.N.*` — every key
  whose only call site disappeared in the restructure (chapter dividers II/III,
  `ch1.framing`, the old `ch2.a.cze`/`ch2.c.cze`/`ch2.e.buckets` answer sentences the
  slides replaced, etc.) was removed from both `src/i18n.py` and `config/i18n/cs.yaml`
  together, verified with `check_complete()`. Left `toc.data_quality`/`toc.how_built`
  alone — those were already intentionally-unlinked-but-present before this task (a
  pre-existing test asserts their ids remain without a TOC link).

## Concerns

- The "How we know" mono lines currently render inside the folded closed-by-default
  Explore blocks for a reader following an old `#benchmark`/`#exhibit-f`/etc. deep
  link — the anchor still resolves to a real element (satisfies "so deep links work"
  literally), but a closed `<details>` doesn't auto-expand on `:target` in this
  codebase's CSS/JS (no such rule existed before either). Left as-is; flagging in case
  a follow-up wants `:target` auto-expand for folded sections generally.
- `_country_sideways_share` is new logic parallel to (not sharing code with)
  `src/pathways.py::destinations()`/`_summarize_destinations()`. I chose not to
  refactor `pathways.py` itself to take a nation parameter — that would touch a module
  outside this task's file list and risk the "never run pathways" pipeline-stage
  constraint in spirit even though the function itself is pure. If a future task wants
  one canonical implementation, `_country_sideways_share` in `render.py` is the
  generalised version to promote.
