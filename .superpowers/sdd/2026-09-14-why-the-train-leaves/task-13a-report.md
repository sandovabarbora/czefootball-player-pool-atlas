# Task 13a report: the 26-season Big-5 series module and figure

## Status
Done.

## Commit
`4a8003cabd6adb075bb2bfa6cfdc124fc6596b95` — "Add the 26-season Big-5 series module and figure (Task 13a)"

Branch v1.2, worktree `.worktrees/v1_2`. Files added/changed: `src/big5_series.py` (new),
`tests/test_big5_series.py` (new), `src/render.py` (modified — one line in `load_data`),
`Makefile` (modified — `fetch-big5` and `series` targets, `series` added to `all` and
`help`). No `data/`, `outputs/`, or `.superpowers/` files were staged. No AI attribution
trailer was added to the commit, per instruction.

## Tests
`uv run pytest -q` → **154 passed, 6 skipped**, 0 failed. The 6 skips are pre-existing
(unrelated to this change; not investigated further per task scope).

`uv run ruff check src/big5_series.py tests/test_big5_series.py src/render.py` →
all checks passed (ruff binary itself wasn't on PATH, so I ran it via
`uv run --with ruff ruff check ...`).

One benign `UserWarning: Glyph 8594 (\N{RIGHTWARDS ARROW}) missing from font(s) Georgia`
appears when rendering the SVG — the suptitle uses a literal "→" per the brief's exact
title text ("{first} → {last}"), and the serif font stack's first entries (Spectral,
Cambria, Georgia) don't carry that glyph. Matplotlib falls back and still draws the
character; this doesn't fail any test (no `-W error` in `pyproject.toml`) and is
cosmetically equivalent to how `international_benchmark.py` already runs (no such
character there, so this is the first module to hit it). Flagged under Concerns below.

## `uv run python -m src.big5_series` on real data

```
CZE peak 2007-2008 (26), low 2015-2016 (6), last 2025-2026 (10)
```

Golden generations (three seasons with the highest Czech `n`, three highest-minutes
Czech players that season — computed, not typed):

| Season | Players (by minutes, descending) |
|---|---|
| 2007-2008 (n=26, peak) | Jaroslav Drobný, Jaroslav Plašil, Radim Kučera |
| 2002-2003 (n=24) | Petr Čech, Jan Koller, David Jarolím |
| 2005-2006 (n=24) | David Rozehnal, Tomáš Ujfaluši, Petr Čech |

Both `outputs/big5_series.svg` and `data/processed/big5_series.json` were written and
exist on disk (gitignored, per the existing convention that `data/processed/` and
`outputs/` aren't tracked — confirmed via `git status` showing neither as untracked).

## Design notes / how I read the interface

- `n`: distinct `player_key` with `min >= min_minutes` (default 450) per peer nation
  per season, summed across all five Big-5 leagues in the history frame (a mid-season
  transfer between two Big-5 clubs is one player, counted once via `nunique`).
- `per_million`: `n / population_m`, rounded to 2 dp (matches `international_benchmark.py`'s
  `per_capita()` convention).
- `minutes_share`: nation's **total** minutes that season (no 450-minute floor — every
  minute a nation's players logged in the Big-5 counts) divided by all minutes logged by
  anyone (any nation) in the Big-5 that season. I read "the nation's minutes ÷ all
  minutes that season" literally as unfiltered, since the floor is specified only for
  `n`'s definition.
- `cze_peak` / `cze_low`: argmax/argmin of the Czech `n` list, ties broken to the
  earliest season in both directions (verified with an explicit index-based tie-break,
  not Python's default first-occurrence-on-equal-key behavior, which differs between
  `max` and `min`).
- `golden`: the three seasons with the highest Czech `n` (ties → earliest season, same
  convention as peak/low), ordered highest-`n`-first (so `golden[0]` is always the peak
  season, matching the brief's fixture assertion `golden[0]["season"] == "2000-2001"`
  when CZE n = [3, 2, 1]). Within each of those seasons, Czech rows are grouped by
  `player_key` (summing minutes across any mid-season transfer) and the top 3 by
  summed minutes are taken — no 450-minute floor applied here since the brief says
  "the three Czech players with the most minutes," full stop, and the top-3 by minutes
  will exceed 450 in every real season anyway.
- Figure: two stacked panels sharing the x-axis (season start year). Top panel: Czech
  `n` as a 2.6pt navy line, peak/low marked with oxblood dots + season-label:count
  annotations, last season marked in navy; the other eight peers as thin light-grey
  lines, with DEN and CRO drawn in the shared `MUTED` mid-tone and labelled at the
  right edge. Bottom panel: `per_million` for CZE (navy) vs DEN vs CRO (both muted),
  each labelled at the right edge. Title uses `season_label()` (e.g. "2000/01 →
  2025/26") per the brief's literal title text. All palette constants (`NAVY`,
  `OXBLOOD`, `CREAM`, `INK`, `MUTED`) and the serif suptitle convention are imported
  from `src/international_benchmark.py` rather than redefined.
- `main()` writes `data/processed/big5_series.json` (via `json.dumps(..., indent=1)`,
  matching `historical_analogs.py`/`squad_lens.py`/`pathways.py`'s existing JSON-write
  style) and `outputs/big5_series.svg`, then logs peak/low/last as required.
- `src/render.py`'s `load_data()` gained one line: `"big5_series": _load_json(p /
  "big5_series.json", {})` — uses the existing `_load_json` helper, which already
  tolerates a missing file by returning the given default (here `{}`), and already
  falls back to the snapshot copy via `resolve_processed`. No template/context wiring
  beyond this was requested by the brief (M4 is the exhibit only; the report template
  isn't touched).
- Makefile: added `fetch-big5: $(ACT) python -m src.fetch_big5_history` (not run, per
  instruction) and `series: $(ACT) python -m src.big5_series`, added `series` to the
  `all` chain right after `benchmark` (matches the module's dependency: it only reads
  `big5_history.parquet`, not `benchmark`'s outputs, but sits naturally in the same
  neighborhood of the pipeline), and added help-text lines for both new targets. Did
  **not** add `fetch-big5` to the `fetch` or `all` targets — the brief only specifies
  it as a Makefile target to add, and the task explicitly forbids running any fetcher;
  wiring it into `all` would make a future `make all` try to fetch again, which seems
  like the wrong default given `data/processed/big5_history.parquet` is meant to be
  fetched once and then treated as an input.

## Concerns

1. **Missing-glyph warning for "→"**: cosmetic only (SVG still renders; not a test
   failure), but worth a maintainer's eye if pixel-perfect glyph rendering in the title
   matters. An easy fix if flagged: swap the literal arrow for `plt.rcParams` set to a
   font family that carries U+2192 (e.g. move `DejaVu Serif` first), or fall back to an
   ASCII `->` — I kept the literal "→" to match the brief's title text exactly.
2. **`golden` player selection has no 450-minute floor** (see Design notes above) —
   this is a literal reading of the brief's wording ("the three Czech players with the
   most minutes"), distinct from the floor used for `n`. If the intent was actually to
   restrict to qualifying (≥450 min) players only, the real-data output is unaffected
   in practice (all six named players in the three golden seasons have well over 1000
   minutes), but it's worth confirming the reading is what was intended.
3. **`fetch-big5` not wired into `all`/`fetch`**: flagged above — a deliberate choice
   given the "don't fetch" instruction and the existing snapshot/processed-data
   pattern, but it means `make all` on a machine without `big5_history.parquet` already
   present will fail at the new `series` step (same class of dependency the rest of the
   pipeline already has on `make fetch` having been run first, so consistent with
   existing behavior, not a new risk).
