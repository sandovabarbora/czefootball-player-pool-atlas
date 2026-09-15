# Task 14b report: the report's copy and site become nation-aware

## Status: DONE

## Commit
- `c77f41f` — "Report copy and site become nation-aware (Task 14b)" (18 files, 648 insertions / 296 deletions). No `Co-Authored-By` / `Claude-Session` trailer, per the hard rule. Parent: `a6b96a9` (Task 14a).

## What changed

### A. Nation words become placeholders
- `src/i18n.py`: `Translator` now computes `self.auto` at construction from
  `config.nation()` — `nation`, `adj`, `Adj` (English forms; `Adj` = `adj`,
  since English nationality adjectives are always capitalised), `code`, and
  one `cs_<key>`/`cs_<Key>` pair (lower + capitalised-first-letter) per entry
  in the nation's new `cs:` block. Both `raw()` and `__call__` merge
  `self.auto` under any explicit `**params`, so every string gets these for
  free. `check_placeholders` now treats any of these names (`_is_auto_name`)
  as exempt from the EN/CS placeholder-subset check in either direction —
  a CS string may use `{cs_adj_m}` that no EN string has, and vice versa for
  `{adj}`/`{code}`/`{home_league}`, without tripping "drops a placeholder."
- `config/nations/cze.yaml` / `eng.yaml` gained `home_league` (EN display
  name: "Czech First League" / "Premier League") and a `cs:` block (`name`,
  `gen`, `adj_m`, `adj_f`, `adj_n`, `adj_pl`, `players`, `home_league` —
  see cze.yaml's comment for what each is for). `TERMS_EN`/`cs.yaml`'s
  `terms:` gained the 8 England-side peer countries (England, France,
  Germany, Spain, Italy, Netherlands, Portugal, Belgium) alongside the
  existing 9 Czech ones, so either NATION's per-capita/cohort/squad tables
  can `term()`-translate every country name they show.
- Replaced the ~65 "Czech"/"Czechia" occurrences in `src/i18n.py`'s `EN`
  dict and the matching ~45 "česk*/Česk*" ones in `config/i18n/cs.yaml`
  with `{adj}`/`{Adj}`/`{nation}`/`{code}`/`{home_league}` (EN) and
  `{cs_adj_m/f/n/pl}`/`{cs_Adj_*}`/`{cs_name}`/`{cs_gen}`/`{cs_home_league}`
  (CS). Left alone (deliberately, judgment calls — see below): the two
  peer-specific mentions "a Danish one" (hero.sublead.export) and the
  cluster-tactical-read prose bodies' two "Czech forwards"/"Czech midfield
  group" phrases (config/cluster_labels.yaml — see B); the author's own bio
  fact "Czech football" in `lim.tracking.body` (tactical-cz is genuinely
  about Czech football regardless of which NATION this atlas renders for);
  and every place "Czech"/"Czech language" refers to the *translator's*
  language, not the home nation (docstrings, `check_complete`'s error
  message, `localize_html_numbers`'s docstring, `svg_labels.py`'s `czech()`
  helper name).
- Where the original Czech text needed an oblique case (genitive/
  instrumental) a bare `{cs_adj_*}` (nominative only) can't produce
  correctly, I rephrased around it with `{cs_gen}` (genitive of the nation
  *noun*, e.g. "Česka"/"Anglie", invariant) as a postpositive modifier —
  "hráčů {cs_gen}" ("players of Czechia") instead of declining "český"
  through cases the four given forms don't cover. This is grammatical but
  reads slightly more like a translated construction than the original's
  native "s českou příslušností" in a few spots (`ch1.atlas.alt/caption`,
  `pi.framing`, `obs.2.body`, `obs.3.body`, `ch4.sens.p`, `dq.*.what`,
  `lim.leagues.body`) — documented in code comments, not silently accepted.
  "Chance Liga"/"Chance Ligy"/"Chance Ligu" (the Czech First League's media
  name, declined three different ways in the original) became `{cs_home_
  league}` left undeclined behind "ligy"/"ligu" (apposition, e.g. "z ligy
  Chance Liga") — grammatical, slightly redundant-sounding ("ligy... Liga").
- `templates/report.html.j2`'s comment header and `site/enrich_index.py`'s
  brand string + two comments (its three "Czech" occurrences) are generic
  now; the brand reads `{ADJ_EN} Football <span>Atlas</span>` /
  `{ADJ_CS} fotbal <span>Atlas</span>`, read directly from
  `config/nations/<NATION>.yaml` since this script runs standalone
  (no `src.config` import, per its own docstring).
- **New, not in the brief's literal list but required for the eng smoke
  render to mean anything**: every hardcoded `'CZE'` literal in
  `report.html.j2` (14 occurrences — `selectattr`/`rejectattr`/`==`
  comparisons that pick out and highlight the home country's row in every
  per-country table/list) now compares against a new `home_code` context
  var (`config.HOME`). Also genericised the matplotlib chart copy that
  Task 14a's report explicitly deferred here: `render.py::_render_atlas`'s
  `fig.suptitle`/caption ("Czech football · …", "Czech-eligible players"),
  `big5_series.py`'s `fig.suptitle` ("Czech players in the Big-5 …"), and
  `site/svg_labels.py`'s English-side match patterns for the Czech-label
  SVG pass (so the pass still finds and translates the (now nation-aware)
  chart titles it's looking for).

### B. Cluster reads: computed examples
- `config/cluster_labels.yaml`: stripped the trailing `" (Name, Name)."`
  from all 36 `tactical.<group>.<cluster>.{en,cs}` strings (regex-verified:
  exactly 36 stripped, 18 clusters × 2 languages).
- `src/render.py`: new `_cluster_top_surnames(coords, season, style_id, n=3)`
  (the `n` home-eligible players with the most metrics-season minutes in
  one style cluster, by surname via the existing `_last_name`; degrades to
  `[]` — not a `KeyError` — when the input frame lacks the needed columns,
  so a minimal test fixture doesn't need to carry `home_eligible`) and
  `_with_tactical_examples(base, examples)` (appends `" (A, B, C)."`, or
  just `"."` with no examples, or `""` for an empty base). `_build_clusters`
  reuses its own already-computed `cz` (home-eligible members sorted by
  minutes) for this; `_build_cards` calls `_cluster_top_surnames` fresh
  since a card's cluster may not be the one `_build_clusters` is currently
  iterating.
- `config.cluster_labels()` (new, `src/config.py`) is the per-nation
  override hook the brief asked for: `nation()["cluster_labels"]` (a path
  like `"config/cluster_labels.eng.yaml"`) overrides the shared default
  `config/cluster_labels.yaml`. Neither `cze.yaml` nor `eng.yaml` sets it —
  the fit is on the all-nationality corpus, so the archetypes are
  nation-independent; the hook exists for a future nation that wants a
  different editorial read. `render.py::load_data` now calls
  `config.cluster_labels()` instead of `config.load_yaml("cluster_labels.yaml")`
  directly.
- Computed examples differ from the author's hand-picked ones in most
  clusters — different members, different spelling in a few cases (FBref's
  raw name field vs. the author's editorially-corrected diacritics, e.g.
  "Patrák" hand-typed vs. "Patrak" as FBref actually has it) — this is the
  expected, intended effect of B (computed, not hand-picked), and is the
  dominant category of difference in the identity check below.

### C. Site per nation
- `site/build.sh`: the `index.html`/`atlas_*.svg`/… existence check no
  longer requires `cs/index.html` unconditionally (only for `NATION=cze`);
  the whole CS pass — `mkdir cs/`, copy `outputs/$NATION/cs/index.html`,
  `enrich_index.py --lang cs`, `svg_labels.py` — is now gated on
  `NATION = cze`. `NATION=eng site/build.sh` (no explicit `OUT_DIR`) writes
  into `docs/eng/` per 14a's existing default-`OUT_DIR` logic; confirmed by
  running it (see Verify).
- `site/enrich_index.py`: top bar gains `<div class="atlas-switch">` next
  to the EN/CS toggle — "CZE · ENG" (`ATLAS_ROOTS = {"cze": "/", "eng":
  "/eng/"}`, root-relative so it works from any page depth), current
  nation plain, the other linking out. The EN/CS toggle itself collapses to
  EN-only (`<span aria-current="page">EN</span>`, no CS `<a>`) whenever
  `NATION != "cze"` — there is no `cs/` directory to link to there.
  `PLAYERS` (site/players.<NATION>.json) now tolerates a missing file
  (`{}` — every `photo()` lookup already degrades to initials-only), for a
  nation without a photo run yet (this repo has no `site/players.eng.json`
  and none was created — see Verify).
- `docs/modern.css`: `.atlas-switch` styled identically to `.lang-switch`
  (flat border, mono, `aria-current` highlight); `margin-left: auto` moved
  from `.lang-switch` to `.atlas-switch` (the first of the pair now claims
  the push-right), `.lang-switch` gets a small `0.4rem` gap instead. Hidden
  entirely under 719px (`.atlas-switch { display: none; }`) to keep the
  phone top bar exactly as before — brand + Contents button + EN/CS only;
  reasoned this is the safer reading of "phone width unchanged" than
  cramming a third top-bar element into ~400px alongside the others.
- `docs/img/players/` unchanged (shared); no `site/players.eng.json` was
  written (no fetcher ran, per the brief's constraint) — `enrich_index.py`
  handles that gracefully rather than needing a placeholder file.
- Hero stamp / masthead credibility line already took the nation's numbers
  automatically from `config`/the processed data (Task 14a's job); nothing
  further needed here.

### D. Copy that changes meaning for England
- `slide.4.how`/`slide.5.how` gained a `{home_note}` placeholder, empty by
  default (identical text to before for Czechia, whose domestic league is
  *not* in the top-N set — the report's whole premise). The template
  computes it conditionally: `{% if domestic_league_code in headline_leagues %}`
  (both new context vars — `config.DOMESTIC_LEAGUE`, the existing
  `headline_leagues`), formats a new key `slide.home_note` ("{home_league}
  is itself one of Europe's top-{topn} leagues; here 'abroad' means the
  other {topn_minus_1}.") and passes it in; for cze this is always `''`,
  verified empty in the identity check. For eng (Premier League *is* inside
  the top-9), it renders — confirmed in the smoke render (see Verify).
- Slide 7's title/idiom ("When did the train leave?" / "Kde vlak odjel?")
  is untouched, as instructed — it's the report's title idiom, not a nation
  word. The Big-5 chart's lower-panel contrast countries (`series_contrast`
  in `config/nations/<NATION>.yaml`) are now named generically in
  `slide.7.alt` and `peer_compare.aria`/`slide.8.q`/`slide.8.a` name the
  two `compare` countries from config ("How do {a} and {b} do it?") instead
  of hardcoding "Norway and Denmark" — for cze these resolve to exactly
  "Norway"/"Denmark" (unchanged text), for eng to "France"/"Spain" (its
  `compare: [FRA, ESP]`).
- Exhibit F peers (`ch2.f.p`'s `{peers}`) were already sourced from
  `config.squads()["peer_squads"]` before this task (14a's report notes
  `squads` moved into `config/nations/<NATION>.yaml` verbatim) — no new
  change needed here beyond the general placeholder work in A.

## A judgment call I could not resolve from the brief alone (documented, not blocking)

The Context section's text-identity-check instruction says "Allowed
differences: none except the render timestamp." Task B (cluster examples
now computed, not hand-picked) and Task A (new placeholders whose value
for cze equals the old literal text — e.g. `{code}` = "CZE", `{adj}` =
"Czech" — so most lines really are byte-identical) are each individually
capable of producing a real difference beyond the timestamp; B's computed
examples visibly do, in ~30 lines. The Verify section's own final wording
— "diff the tag-stripped text; report any line that differs" — reads as
the authoritative instruction (report the diff, don't require it empty),
so I read the Context section's "none except timestamp" as describing the
*intent* (Task A's placeholder substitution must be invisible for cze, and
it is — every difference below traces to B, D's new atlas-switch markup,
or the test count, never to a mistranslated `{adj}`/`{code}`/`{nation}`),
not a literal zero-diff bar once B and the site-layer UI addition are also
in scope. I did not treat this as `NEEDS_CONTEXT` since it's resolvable
from the brief's own two instructions taken together, not a brief-vs-code
disagreement — but flagging it since it's a real interpretive choice.

## Identity check (cze)

Baseline: `git stash`'d back to HEAD (`a6b96a9`), ran `NATION=cze make
render` + `site/build.sh`, tag-stripped `docs/index.html`/`docs/cs/
index.html` with Python's `html.parser` (text nodes only, one per line,
blank lines dropped) to scratch. Restored my changes, repeated the same
render+build+strip, diffed.

Every line that differs falls into exactly one of these four buckets (verified by grep — no line in either diff falls outside them):

1. **`CZE · ENG` atlas-switch line** (1 new line in each page) — Task C, expected.
2. **Test count**, `148` → `155` in the masthead facts and "How this was
   built" (`n_tests` is computed live via `_count_tests()`, and I added
   7 tests — see Tests below) — expected, not a copy bug.
3. **Cluster tactical read example names** (~15 lines × 2 languages = ~30) —
   Task B, expected; computed top-3-by-minutes instead of the author's
   hand-picked list, sometimes with different spelling (FBref's raw
   diacritics vs. the author's corrected ones).
4. **`Rendered: <timestamp>`** — allowed per the brief.

No line traces to a mistranslated placeholder, a dropped nation word, or
an accidental content change outside A/B/D's stated scope. Both `docs/
index.html` and `docs/cs/index.html` were re-built one final time after
all fixes and are what's committed.

## NATION=eng smoke render

`data/processed/cze/*` copied to `data/processed/eng/` (untracked,
gitignored, not committed). `NATION=eng uv run python -m src.render`
initially crashed three times on data/config mismatches inherent to using
cze-labelled data under `NATION=eng` (no fetcher was run, so the copied
tables are keyed by CZE-side country codes throughout) — none of these are
copy bugs; each was a lookup that assumed "the home country's own row is
always present in this per-country table," true for any real single-nation
run, false only in this synthetic smoke-test setup:
1. `per_capita` has no `ENG` row → new `_home_per_capita_row()` fallback
   (zero-count placeholder, logged warning) used by both call sites.
2. `big5_series["countries"]` has no `ENG` key → guarded with `.get()` +
   fallback to 0.
3. `squad_lens.rows` has no `ENG` row → template's `ch2.f.p` call falls
   back to `0` rather than erroring on `Undefined.n`.
4. (Found while checking output, not a crash) `names` dict was scoped to
   `config.peers_meta()` (eng's own peer set) — any leftover cze-side
   country code from the copied pathways/squad data (e.g. `SVK`) had no
   name to resolve, so it fell back to the raw code, which `term()`
   correctly rejected (codes aren't registered terms) → `names` now bases
   on the full `countries.yaml` registry with the nation-scoped set
   overriding, so every code in the *global* registry resolves regardless
   of which nation's peer set is "official" for this run.

After these four fixes, `NATION=eng uv run python -m src.render` wrote
both `outputs/eng/index.html` (345,376 bytes) and `outputs/eng/cs/
index.html` (352,917 bytes) cleanly — `LANGS = ("en", "cs")` means
`src.render` always writes both regardless of NATION; publishing is what's
English-only (see C). `NATION=eng uv run python -m src.big5_series` filled
in the one missing figure. `NATION=eng site/build.sh` (no `OUT_DIR`)
wrote `docs/eng/index.html` + assets, **no** `docs/eng/cs/` — confirmed
absent. Not committed (`docs/eng/` is untracked, deliberately left off the
`git add` list).

Five sample EN sentences from the eng render (`docs/eng/index.html`, numbers are Czech per the brief — copy is the point of this check):
1. "Is the English pool thin?"
2. "Where do English players go when they leave?" / "Destination league of every English-eligible player's 2025/26 row; sideways = destination multiplier ≤ English league multiplier. Premier League is itself one of Europe's top-9 leagues; here 'abroad' means the other 8." (the D-bullet conditional, firing correctly because England's domestic league *is* in the top-9)
3. "How do France and Spain do it?" (from `compare: [FRA, ESP]`)
4. "FBref (via soccerdata): player season tables (standard, playing time) for the 9 headline leagues, the Premier League, the peer domestic leagues and the German second tier; the country page \"Players from England\" for pool discovery; the nationality column for peer counts"
5. "The pipeline fetches 19 competitions from FBref; the English second tier and the Slovak top flight are not on FBref at all. 125 of the 440 English professionals found on FBref's country page play in a league without season tables and carry no metrics; they are listed by name and club only."

Matplotlib chart title (`outputs/eng/atlas_FW.svg`): `English football · Forwards 2025/26` (was `Czech football · Forwards 2025/26` for cze — text unchanged there, since `adj="Czech"`).

## Tests

Added 7 tests (148 → 155):
- `tests/test_config.py`: `test_nation_carries_home_league_and_cs_forms` (both nations' `home_league` + `cs` block present and non-empty), `test_cluster_labels_defaults_to_the_shared_file`.
- `tests/test_i18n.py`: `test_auto_injected_nation_words_fill_in_without_an_explicit_param` (values, and that an explicit param still overrides an auto one), `test_check_placeholders_allows_auto_names_in_either_language_only`, `test_terms_cover_both_configured_nations_peer_countries`.
- `tests/test_render.py`: `test_cluster_top_surnames_are_computed_not_hand_typed` (sorted by minutes, foreign/other-cluster players excluded, missing-columns fixture degrades to `[]` not `KeyError`), `test_slide4_and_5_how_gain_a_home_league_note_only_when_it_is_inside_the_topn` (renders the fixture context both as-is — home league outside top-N, note absent — and with `domestic_league_code`/`headline_leagues` overridden to put it inside — note present).

Two pre-existing-pattern bugs I found and fixed while writing these (not
copy bugs, but would have caused real breakage the first time anyone hit
them): `_cluster_top_surnames`'s column-presence guard checked
`coords.columns` *after* already calling `_metrics_rows` (which itself
does `.sort_values("min", ...)` — `KeyError` before the guard could run)
— reordered to check first. My first `check_placeholders` test asserted
the wrong thing (mixed a genuine mismatch into the auto-name probe) —
fixed to only vary auto names.

## Verify (all run)

- `uv run pytest -q -p no:warnings` → **155 passed**, no skips (offline
  pipeline output present under `data/processed/cze/`).
- `NATION=cze` render + build → identity check above.
- `NATION=eng` render (smoke test against cze's copied processed data) →
  succeeds after the four fixes above; site build into `docs/eng/`
  succeeds, English-only, not committed.
- `git status` after commit: clean except `.superpowers/` (this task's own
  planning docs, pre-existing, not part of this task's deliverable) and
  `docs/eng/` (deliberately untracked).

## Concerns / judgment calls (flagged for visibility, none blocking)

1. The interpretive tension between the Context section's "none except
   timestamp" and the Verify section's "report any line that differs" —
   resolved as described above (identity check section).
2. CS grammar for oblique cases beyond the four given nominative forms
   (`{cs_gen}` postpositive-genitive rephrase) — grammatical but
   occasionally less native-sounding than the original hand-written Czech
   in ~13 strings; documented in the "A" section above with the exact keys.
   Since the published site is Czech-only for `cze` (never for a
   hypothetical future nation, per C), this only affects the one language
   variant that was already hand-written prose to begin with, not a
   made-up translation for a nation nobody speaks Czech about.
3. Left the two "Czech forwards"/"largest Czech midfield group" mentions
   inside `config/cluster_labels.yaml`'s tactical-read *prose bodies*
   (not the stripped example-name tails) untouched — that text passes
   through unformatted (no `.format()` call on it at all, by design, since
   it's free-form author prose), so a `{placeholder}` there would render
   literally as `{adj}` rather than substituting. Fixing this would mean
   either running these specific strings through `.format()` (a special
   case for exactly two strings) or rewriting the sentences to avoid
   naming the nation at all; given the brief's B section scopes this task
   to "strip the parenthetical tails" only, I left the prose as descriptive
   editorial content, matching the "Danish"/"tactical-cz" precedent
   elsewhere in A.
4. `.superpowers/` is untracked but I did not investigate or touch it —
   out of scope, and it predates this session.

No `NEEDS_CONTEXT` was needed.
