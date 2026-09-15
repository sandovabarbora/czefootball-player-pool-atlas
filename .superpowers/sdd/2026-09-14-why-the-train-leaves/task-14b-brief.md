# Task 14b: Copy and site per nation — the report reads correctly for England

After Task 14a the pipeline runs per nation, but the copy still says "Czech" and the
cluster reads name Czech players by hand. After this task the *same* templates render
a correct English-language page for any nation; the Czech pages stay unchanged
(golden test + a text-diff check of the rendered EN/CS HTML for cze against HEAD).

## A. Nation words become placeholders (EN and CS)
- `Translator` (`src/i18n.py`) auto-injects `nation`, `adj`, `code`, `home_league`
  into every `t()`/`raw()` call from `config.nation()` (name, adjective, code,
  domestic league display name). In the CS file the Czech forms differ by case; add
  per-nation CS forms to `config/nations/<code>.yaml`: `cs: {name: Česko, adj_m: český,
  adj_f: česká, adj_n: české, adj_pl: čeští, gen: Česka, players: čeští hráči}` — the
  CS strings use these keys (`{cs_adj_m}`, …). For England: `cs: {name: Anglie,
  adj_m: anglický, adj_f: anglická, adj_n: anglické, adj_pl: angličtí, gen: Anglie}`.
- Replace all 61 EN "Czech"/"Czechia" and 42 CS "česk*/Česk*" occurrences in
  `src/i18n.py` / `config/i18n/cs.yaml` with the placeholders (keep capitalisation
  helpers: `{Adj}` capitalised variant available). The masthead title
  `mast.title` "Czech Football Atlas" → "{adj} Football Atlas". `site/enrich_index.py`'s
  three "Czech" strings and the one in `templates/report.html.j2` likewise.
- Idioms that only make sense for Czechia ("Where the train leaves" / "Kde nám ujíždí
  vlak") stay — they are the report's title idiom, not a nation word. Slide 8's question
  names the two `compare` countries from config ("How do {a} and {b} do it?").
- Test: render cze EN and CS HTML before and after → identical text (allowing the
  build stamp), plus `NATION=eng` render produces no "Czech" anywhere (grep) and no
  missing placeholder.

## B. Cluster reads: computed examples
`config/cluster_labels.yaml` tactical reads carry hand-typed Czech names in
parentheses. Strip the "(Name, Name)" tails from every `en`/`cs` read (the text before
stays), and let `render.py::_build_clusters` append the examples: the three
home-eligible players with the most metrics-season minutes in the cluster, surnames,
as "(Schick, Patrák, Chorý)" — computed, so they are right for any nation and any
refit. Labels file also gets a per-nation override hook: `config/nations/<code>.yaml`
may carry `cluster_labels: config/cluster_labels.<code>.yaml`; default is the shared
file (the fit is on the all-nationality corpus, so archetypes are nation-independent).

## C. Site per nation
- `site/build.sh NATION=eng` → `docs/eng/index.html` (+ `docs/eng/*.svg`,
  `atlas_meta.json`); **English only** for non-cze nations (skip the CS pass);
  `docs/eng/CNAME` not needed (same domain, subpath). Top bar gets an atlas switch
  next to EN/CS: "CZE · ENG" linking `/` ↔ `/eng/` (site-layer, `site/enrich_index.py`,
  `docs/modern.css`); on the eng page the CS toggle is hidden.
- `docs/img/players/` shared; `site/players.eng.json` written by the eng photo run.
- The hero stamp / masthead credibility line take the nation's numbers automatically.

## D. Copy that must change meaning for England (descriptive, config-driven)
- Slide 4 ("Where do players go when they leave?") and slide 5 use "abroad" = outside
  the domestic league; for England the domestic league is itself in the top-9 set —
  the how-line must say so: add `{home_league}` to `slide.4.how`/`slide.5.how` ("…
  outside {home_league}; for a home league inside the top-{topn}, 'abroad' means the
  other {topn_minus_1}").
- Slide 7 title stays; the series highlights the home nation.
- Exhibit F peers: from config (`peer_squads`).

## Verify
`uv run pytest -q -p no:warnings`; `NATION=cze` render + build → `docs/index.html` and
`docs/cs/index.html` text-identical to HEAD's (diff the tag-stripped text; report any
line that differs); `NATION=eng` render must succeed on the **snapshot-restored cze
data copied into `data/processed/eng/`** as a smoke test (numbers will be Czech, copy
English-nation — that is expected; do not commit that output). Commit plain message,
no AI trailer; never `data/`, `outputs/`; `docs/` only if cze rebuilt identical.
