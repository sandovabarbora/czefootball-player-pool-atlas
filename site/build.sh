#!/bin/zsh
# Build the published site from the two rendered pages (`make render`):
#   docs/index.html        English (outputs/<NATION>/index.html)
#   docs/cs/index.html     Czech   (outputs/<NATION>/cs/index.html, assets via ../)
#   docs/*.svg, style.css  copied from outputs/<NATION>/
#   docs/cs/*.svg          Czech figure labels (svg_labels.py)
#   docs/atlas_meta.json   interaction metadata for atlas.js (atlas_meta.py)
# enrich_index.py applies the site layer (top bar, photos, folds, search) to
# each page; every script asserts its match counts and fails loudly when the
# render changed under it.
#
# NATION (env var, default cze) picks the source run (outputs/$NATION/) and,
# when OUT_DIR isn't given explicitly, the default site output dir: docs/ for
# cze (the published site keeps its original, un-prefixed layout), docs/
# $NATION/ for any other nation.
#
# usage: site/build.sh [OUT_DIR]     (default: docs/ for cze, docs/$NATION/ otherwise)
#        NATION=eng site/build.sh    (build England into docs/eng/)
# With another OUT_DIR the static assets that only live in docs/ (modern.css,
# atlas.js, CNAME, .nojekyll, img/) are copied there too, so a test can build
# a complete site into a temp dir without touching the committed docs/.
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
S="$ROOT/site"
NATION="${NATION:-cze}"
export NATION
if [ -n "${1:-}" ]; then
  D="$1"
elif [ "$NATION" = "cze" ]; then
  D="$ROOT/docs"
else
  D="$ROOT/docs/$NATION"
fi
D=$(mkdir -p "$D" && cd "$D" && pwd)
O="$ROOT/outputs/$NATION"
PY=${PYTHON:-python3}
if command -v uv >/dev/null 2>&1 && [ -f "$ROOT/pyproject.toml" ]; then PY="uv run --project $ROOT python"; fi

for f in index.html atlas_FW.svg atlas_MF.svg atlas_DF.svg intl_cohort_heatmap.svg big5_series.svg \
         league_strength.svg league_strength_ppc.svg style.css; do
  [ -f "$O/$f" ] || { echo "missing $O/$f — run \`make render\` first (big5_series.svg: \`uv run python -m src.big5_series\`; league_strength*.svg: \`uv run python -m src.league_strength\`)" >&2; exit 1; }
done
if [ "$NATION" = "cze" ]; then
  [ -f "$O/cs/index.html" ] || { echo "missing $O/cs/index.html — run \`make render\` first" >&2; exit 1; }
fi

if [ "$D" != "$ROOT/docs" ]; then
  for a in modern.css atlas.js .nojekyll; do [ -e "$ROOT/docs/$a" ] && cp "$ROOT/docs/$a" "$D/"; done   # CNAME belongs to the root only
  [ -d "$ROOT/docs/img" ] && [ ! -e "$D/img" ] && cp -R "$ROOT/docs/img" "$D/img"
fi
cp "$O/index.html" "$D/index.html"
cp "$O/atlas_FW.svg" "$O/atlas_MF.svg" "$O/atlas_DF.svg" "$O/intl_cohort_heatmap.svg" "$O/big5_series.svg" \
   "$O/league_strength.svg" "$O/league_strength_ppc.svg" "$O/style.css" "$D/"

${=PY} "$S/enrich_index.py" "$D/index.html" --lang en
if [ "$NATION" = "cze" ]; then
  # CS pass: `src.render` writes a cs/index.html for every NATION (the
  # translator's cs_* placeholders work for any of them -- see
  # src/i18n.py's Task 14b auto-injection), but the *published* site is
  # Czech-only for the home nation this repository was written for; any
  # other NATION publishes English only (Task 14b brief).
  mkdir -p "$D/cs"
  cp "$O/cs/index.html" "$D/cs/index.html"
  ${=PY} "$S/enrich_index.py" "$D/cs/index.html" --lang cs
  ${=PY} "$S/svg_labels.py" "$D" >/dev/null
fi
${=PY} "$S/atlas_meta.py" "$D" >/dev/null
if [ "$NATION" = "cze" ]; then
  echo "built $D/index.html (en) + $D/cs/index.html (cs), cs/*.svg, atlas_meta.json"
else
  echo "built $D/index.html (en, NATION=$NATION), atlas_meta.json"
fi
