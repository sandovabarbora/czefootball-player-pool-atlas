# Czech Football — Player Pool Atlas

Live at **[football.datasimply.eu](https://football.datasimply.eu)** (English) /
**[football.datasimply.eu/cs/](https://football.datasimply.eu/cs/)** (Czech).

## What it is

A public, reproducible report that maps the Czech professional football
player pool — how big and how deep it is against eight peer countries, and
where the structural gaps sit. It is a methodology showcase and planning
input, not a selection recommendation: no predictions, no coaching or
tactics commentary, public data only.

## Headline number

**1.65** top-9-league players per million inhabitants — 18 Czech players on
2025/26 rosters of Europe's nine strongest leagues (England, Italy, Spain,
Germany, France, Netherlands, Portugal, Belgium, Turkey), divided by a 2024
Eurostat population estimate of 10.9 M. That ranks Czechia 7th of 9 peer
countries: Croatia 10.36, Denmark 9.90, Norway 7.93, Austria 4.59,
Switzerland 4.46, Slovakia 2.58, **Czechia 1.65**, Hungary 1.46, Poland 0.87.

*Footnote (as shown on the page): numerator is players with the country's
FBref nationality on a 2025/26 roster of the 9 headline leagues; denominator
is Eurostat 2024 population. Every number in the report is computed from the
fetched data, not typed in by hand.*

## Run it

```bash
make install            # uv venv + deps
make all                # fetch -> pool -> photos -> features -> reduce -> benchmark
                        #   -> analogs -> sensitivity -> pathways -> render
make pages              # render, then build docs/index.html (en) + docs/cs/index.html (cs)
```

Each stage is its own target (`make fetch`, `make pool`, `make photos`,
`make features` — features + trajectory, `make reduce` — PCA/UMAP + KMeans,
`make benchmark`, `make analogs`, `make sensitivity`, `make pathways`,
`make render`); `make -n all` prints the full order.

### Rebuild from snapshot

`data/snapshot/` (committed) holds the processed parquet/json files, while
`data/processed/` is gitignored — so a clean clone rebuilds the report
without refetching anything:

```bash
uv sync && make restore-snapshot && make render && make pages
```

`make restore-snapshot` copies the snapshot into `data/processed/` without
overwriting a newer processed file. Plain `make render` also works on a
clean clone: every reader of a processed file falls back to the snapshot
copy when the processed one is missing, and the cohort heatmap is redrawn
from the tables when `outputs/intl_cohort_heatmap.svg` is absent.

`make fetch` (part of `make all`) opens a real Chrome window per FBref page
(`soccerdata`'s undetected-Chrome mode) and takes roughly an hour cold — only
needed to refresh the underlying data, not to rebuild the site from what's
already fetched.

## Data sources and access notes

- **FBref** (via `soccerdata`): player season tables for 17 fetched leagues
  plus the Czech First League and the Chance Liga — the nine headline
  leagues, the peer domestic top flights, and the German second tier — plus
  the "Players from Czechia" country page used for pool discovery. Free
  tier only: no expected goals, no progressive passing, no tackles, so the
  feature vector is limited to what the basic tables carry everywhere
  (non-penalty goals, assists, minutes share, age, cards). Slovakia's top
  flight is not on FBref at all, so its exhibits rest on players abroad.
- **UEFA association coefficients** (via Wikipedia): league-strength source
  for the quality multipliers. ClubElo was unreachable at run time (the API
  was down), so the multipliers fall back to UEFA's 5-year country
  coefficients, scaled to the strongest league = 1.00, with second-tier
  leagues set to 0.6× the first tier of the same country by stated
  assumption. Method and every multiplier are in
  `config/league_quality.yaml`.
- **Wikipedia**: national-team squad tables (EURO 2024, Nations League
  2024/25, 2026 World Cup qualification, 2026 World Cup, U21 EURO 2025) for
  the "called up since 2024" flag, matched on normalised name and birth
  year.
- **Wikidata / Wikimedia Commons**: player portraits (property P18),
  matched on name, citizenship and date of birth, occupation-filtered to
  association football players. 114 of the pool's players have a portrait
  used on the site; credits (photographer/file, licence link) are in the
  page footer.
- **Eurostat**: 2024 population estimates for the per-capita headline and
  benchmark.

The pool itself: 475 active Czech men found on FBref, of whom 199 have a
complete 2024/25 season (≥ 450 minutes) in a fetched league.

## Known gaps

Copied from the report's own Limitations section (`docs/index.html`
`#limitations`) so this list can't drift out of sync with what the page
says:

- **Leagues without metrics.** The pipeline fetches 19 competitions from
  FBref; the Czech second tier and the Slovak top flight are not on FBref at
  all. 120 of the 475 Czech professionals found on FBref's country page play
  in a league without season tables and carry no metrics; they are listed by
  name and club only. Slovakia's exhibits therefore rest on its players
  abroad.
- **Free-tier feature set.** Five basic columns per 90 minutes: non-penalty
  goals, assists, minutes share, age and cards — the same vector across
  every league in the corpus, because that's the only table available for
  all of them. Defensive and creative contributions beyond assists are
  invisible to the map.
- **National-team flag source.** Parsed from Wikipedia squad tables
  (2024–25 Nations League, 2026 World Cup, 2026 World Cup qualification,
  UEFA Euro 2024, UEFA U21 EURO 2025) and matched on normalised name plus
  birth year. 59 of the 199 mapped players carry it. A squad table edit or a
  name variant can drop a call-up; the flag is a tag, not a cap count.
- **Photo coverage.** 114 of the 475 pool players have a Wikimedia Commons
  portrait (matched on name, citizenship and birth date, occupation-filtered
  to association football player). Players without a portrait show initials.
- **Season split.** The headline per-capita count uses 2025/26 rosters;
  every metric, cohort table and atlas uses the complete 2024/25 season;
  trajectories run 2023/24 → 2024/25; the club on a card is the 2025/26
  club. A player who moved in summer appears with last season's numbers and
  this season's club.
- **League multipliers.** ClubElo was unreachable at run time, so the
  multipliers are UEFA association coefficients, and second-tier leagues
  are set to 0.6× the first tier of the same country by assumption. The
  club-strength proxy is the club's goals-scored percentile within its
  league, not an Elo rating. A sensitivity table shows how far a ±20% error
  in any one multiplier moves the Czech ranking.
- **Export origins from recent entrants only.** The origin league of an
  export is known only when the season before their first top-9 season was
  fetched (2020/21 onwards for the headline leagues, 2023/24 onwards for
  peer domestic leagues), so origin shares and recent export age cover only
  players whose first top-9 season is 2024/25 or 2025/26; earlier entrants
  count towards full export age but not the origin mix.
- **Player identity.** FBref's season tables carry no player id, so players
  are joined on normalised name plus birth year across leagues and seasons;
  two players sharing both would collapse into one. A mid-season transfer
  produces two club rows collapsed into one minutes-weighted row.
- **Women's entries and the -ová heuristic.** FBref's country page mixes
  men's and women's competitions. Entries whose surname ends in -ová were
  dropped from the pool; a woman with a different surname ending would
  survive the filter, and a man with that ending would not.
- **No market values, no scouting.** Transfer fees, market values, video
  and scouting reports are outside the public sources used here. The map
  describes statistical footprints and counts; selection and development
  decisions require the federation's own data and expertise, which this
  method does not have.

## How the site is built

`make pages` runs `site/build.sh` on top of `make render`'s two rendered
pages (`outputs/index.html` English, `outputs/cs/index.html` Czech):
copies them plus the SVG figures and stylesheet into `docs/` and
`docs/cs/`, then `site/enrich_index.py` applies the site layer (top bar,
photos, folds, search) to each one.

Translation is template-level, not page-level: `src/i18n.py` reads English
strings from the module and Czech strings/terms from `config/i18n/cs.yaml`,
and the Jinja2 template calls `t(key, ...)` / `term(label)` for every piece
of report text. **A Czech string or term missing from `config/i18n/cs.yaml`
fails the build loudly** rather than shipping an untranslated sentence —
there is no silent fallback to English in the Czech render.

Twelve showcase cards are picked by four rules; exhibits A–E live in the
"Where the train leaves" chapter. See `docs/superpowers/specs/` for the
full design and its "Deviations from the design" section for where the
shipped v1 departs from the original plan.

## Licence

Code: MIT, see [LICENSE](LICENSE). Player portraits: Wikimedia Commons,
each under its own CC licence — see the credit list in the page footer
(`#photo-credits`) for the licence of each individual photo.

## Contact

Barbora Šandová · barbora@datasimply.eu ·
[linkedin.com/in/barborasandova](https://linkedin.com/in/barborasandova)
