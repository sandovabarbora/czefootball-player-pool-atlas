# Czech Football Player Pool Atlas — design (v1)

Date: 2026-09-12. Author: Barbora Šandová (with Claude). Status: draft for review.

## 1. Purpose

A public, reproducible report that maps the Czech professional football player
pool the way `czehockey-player-pool-atlas` maps the hockey pool, framed for the
national-team context (FAČR), not for a club. It answers one question the
federation does not hold in one place: **how big and how deep is the Czech
pool compared with peer countries, and where are the structural gaps?**

Stance discipline carries over unchanged: no predictions, no selection
recommendations, public data only, every strong claim ends with `*` and a
mono footnote that backs it.

## 2. Scope

### In v1

- **Corpus.** Every Czech-eligible professional in a competition FBref covers
  (about forty leagues) plus the whole Chance Liga. Players in leagues FBref
  does not cover are listed by name, club and league (discovered from FBref's
  country page) but carry no metrics; the gap is stated in Limitations.
- **Headline.** Players on 2025/26 rosters of the UEFA top-10 leagues per
  million inhabitants, for nine countries: CZE, SVK, AUT, HUN, POL, HRV, DNK,
  CHE, NOR. Population constants: Eurostat 2024 estimates.
- **Cohort gaps.** Same four age cohorts as hockey (U22, 23–25, 26–29, 30+)
  by position group (FW, MF, DF), median non-penalty G+A per 90, for the nine
  countries.
- **Atlas.** Three two-panel PCA maps (FW, MF, DF): style (no league
  multipliers) and quality-adjusted. Goalkeepers excluded.
- **Trajectories.** 2023/24 → 2024/25 for players with ≥ 900 minutes in
  both seasons.
- **National-team flag.** "Called up since 2024-01-01" (A team: EURO 2024,
  Nations League 2024/25, 2026 WC qualifiers; U21: EURO 2025). Rings in the
  atlas, tag on cards — the football equivalent of the WC 24/25 rings.
- **Cards and analogs.** Six showcase players — per position group the highest
  quality-adjusted P/90 and the youngest NT-flagged player (a rule, not a pick) with photo, stats, cluster placement, trajectory and top-3
  historical analogs at the same age from the all-nationality FBref corpus.
- **Site.** `football.datasimply.eu`, English default, Czech under `/cs/`,
  built with the `site/` toolchain and `modern.css` / `atlas.js` inherited
  from the hockey repo.

### Out of v1 (v1.1 candidates)

- LLM scout briefs (needs `ANTHROPIC_API_KEY`; prompt ports from hockey).
- Video layer (link to `tactical-cz` instead of a new PoC).
- Media buzz index.
- Market values (Transfermarkt) as a fourth feature — fetcher exists, kept
  as enrichment only if the join rate on the Czech pool exceeds 90 %.

## 3. Seasons and the "current" problem

The 2025/26 season has just started (September), so:

| Use | Season |
|---|---|
| Headline per-capita counts | 2025/26 rosters (who is on a top-10 league roster now) |
| Player metrics, atlas, cohorts | 2024/25 (complete) |
| Trajectory | 2023/24 → 2024/25 |
| Current club on cards | 2025/26 |

The report states this split next to the headline.

## 4. Data sources

| Source | What | Access |
|---|---|---|
| FBref (via `soccerdata.FBref`, plus `fbref_direct.py` for pages soccerdata does not expose) | Player season stats per league (standard, shooting, playing time); country page "Players from Czechia" for discovery; nationality column for peer counts | Free tier is enough — the feature vector uses only basic columns. Cloudflare handled by soccerdata's Selenium reader; the sparta `auth.py` cookie path is optional. |
| Understat | npxG per 90 for Big-5 players | Enrichment only, shown on cards, not in PCA |
| ClubElo (`fetch_elo.py`) | League strength → league multipliers | Free CSV API |
| Wikipedia | National-team squad tables (A, U21) | Parsed with the same approach as hockey's `fetch_iihf.py` |
| Wikidata / Wikimedia Commons | Player photos (P18), matched on name + citizenship (Q213) + date of birth | SPARQL; CC-licensed; attribution list in the page footer |
| Eurostat | Population constants | Hard-coded with source line, like hockey |

Every fetcher caches raw HTML/JSON under `data/raw/` and is idempotent;
`data/raw` and `data/processed` are gitignored as before. **This time the
processed parquet files that the render needs are also committed to
`data/snapshot/`** (a few MB) so the site can be rebuilt without refetching —
the hockey repo lost that ability when the local clone was deleted.

## 5. Method

Mirrors hockey; differences are position-specific.

- **Feature vector** (per player-season, per 90 minutes): non-penalty goals,
  assists, minutes share of the club's season, age, cards. Defenders and
  midfielders additionally use progressive passes and tackles+interceptions
  only if the free tier returns them for the whole corpus; otherwise the
  vector stays at five features for all three groups. The rule is: one
  vector per group, identical across leagues, or the feature is dropped.
- **Shrinkage.** Empirical Bayes towards the league median, K = 10 "phantom
  matches" expressed in 90-minute units (900 minutes).
- **League multipliers.** Mean ClubElo of the league's clubs at season end,
  scaled so the strongest Big-5 league = 1.00. Table published; sensitivity
  analysis reruns the quality ranking at ±20 % per league and reports top-10
  churn, as in hockey.
- **Reduction and clustering.** PCA to 2 components per group and
  projection (style / quality), KMeans with k chosen by silhouette in 3..6,
  seed 42. UMAP retained only for the notebook, not the report.
- **Analogs.** For each showcase player, nearest 5 in (quality P/90, minutes,
  league quality) at the same age across the whole FBref corpus, with the
  following four seasons shown. Description, not prediction.

## 6. Repository

Fork of `czehockey-player-pool-atlas` (local clone, new origin
`sandovabarbora/czefootball-player-pool-atlas`, created after this spec is
approved). Kept: `site/`, `docs/modern.css`, `docs/atlas.js`, `Makefile`
targets, `templates/style.css`, test layout. Removed: hockey fetchers, goalie
features, MoneyPuck, IIHF, cover letter / first-call prep, hockey outputs.

```
src/
  config.py              leagues, peer countries, populations, seasons
  fetch_fbref.py         league player tables + country page  (from sparta fetch_players + fbref_direct)
  fetch_understat.py     Big-5 npxG                            (from sparta)
  fetch_elo.py           league multipliers                    (from sparta)
  fetch_squads.py        NT / U21 call-ups from Wikipedia      (from hockey fetch_iihf)
  fetch_photos.py        Wikidata P18 → docs/img/players/      (new)
  pool.py                Czech-eligible discovery + corpus assembly
  features.py            per-group feature vectors + shrinkage (from hockey features_*)
  reduce.py, cluster.py  unchanged
  trajectory.py          unchanged
  international_benchmark.py  per-capita + cohorts, 9 countries (from hockey)
  historical_analogs.py  unchanged
  sensitivity.py         unchanged
  render.py              report.html.j2 → outputs/index.html   (English source)
site/
  build.sh, enrich_index.py, translate_index.py (EN→CS pairs this time),
  svg_labels.py (labels EN→CS), atlas_meta.py, players.json (photo map)
```

The template is written in **English**; `translate_index.py` produces Czech
with the same exact-match/assert mechanism, so a changed sentence fails the
build instead of leaking untranslated.

## 7. Site

Same visual system as hockey (Space Grotesk, navy/cream/oxblood, square
exhibits, folds, carousel on phones). Differences: the Czech football brand is
also red — keep oxblood as accent; hero cut-out is the top showcase player;
the "cast" strip lists six profiles. Interactive atlases run on `atlas.js`
unchanged (three figures instead of two).

## 8. Risks and the spike that precedes the plan

Before the implementation plan is executed, a 30-minute spike checks:

1. `soccerdata.FBref` can read one league's player standard table today
   (Cloudflare changes since May).
2. FBref's country page for Czechia lists current club and competition.
3. Wikidata returns a P18 image for at least 7 of 10 sampled Czech
   internationals.

If (1) fails, fallback is `fbref_direct.py` with the Stathead cookie; if that
fails too, v1 narrows to Big-5 + Chance Liga via Understat + FBref basic
pages, and the spec is revised. If (3) is below 5/10, photos ship only for the
six showcase players (manually sourced with attribution).

## 9. Testing

Offline tests as in hockey: fetcher parsers on fixture HTML, feature and
shrinkage math on toy frames, benchmark counts on a synthetic roster, and the
site build asserting every translation pair hits exactly once. Live smoke is
a separate `make smoke`.

## 10. Definition of done (v1)

- `make all` from a clean clone (with `data/snapshot/` present) renders the
  report; `make pages` builds EN + CS.
- Headline number, cohort tables and league multipliers are computed, not
  typed; the hero footnote cites the computation.
- Limitations section lists: leagues without metrics, free-tier feature set,
  NT flag source, photo coverage, and the season split.
- `football.datasimply.eu` serves HTTPS with the EN/CS switch.
