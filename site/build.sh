#!/bin/zsh
# Build the published site from the two rendered pages (`make render`):
#   docs/index.html        English (outputs/<NATION>/index.html)
#   docs/*.svg, style.css  copied from outputs/<NATION>/
#   docs/atlas_meta.json   interaction metadata for atlas.js (atlas_meta.py)
#   docs/atlas/index.html  the player atlas (build_atlas.py + atlas.app.js)
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
         league_strength.svg league_strength_ppc.svg model_comparison.svg series_model.svg eda_distributions.svg \
         eda_shrinkage.svg gk_export_age.svg youth_panel.svg gap_decomposition.svg export_age_model.svg \
         fare_dots.svg pathway_slope.svg why_funnel.svg style.css; do
  [ -f "$O/$f" ] || { echo "missing $O/$f — run \`make render\` first (big5_series.svg: \`uv run python -m src.big5_series\`; league_strength*.svg: \`uv run python -m src.league_strength\`; model_comparison.svg: \`uv run python -m src.model_comparison\`; series_model.svg: \`uv run python -m src.series_model\`; eda_*.svg: \`uv run python -m src.feature_eda\`; gk_export_age.svg: \`uv run python -m src.goalkeepers\`; youth_panel.svg: \`uv run python -m src.youth_panel\`; gap_decomposition.svg: \`uv run python -m src.gap_decomposition\`; export_age_model.svg: \`uv run python -m src.export_age_model\`; fare_dots.svg/pathway_slope.svg/why_funnel.svg: \`uv run python -m src.render\`)" >&2; exit 1; }
done

if [ "$D" != "$ROOT/docs" ]; then
  for a in modern.css atlas.js charts.js atlas.app.js .nojekyll; do [ -e "$ROOT/docs/$a" ] && cp "$ROOT/docs/$a" "$D/"; done   # CNAME belongs to the root only
  # images live once in docs/img; another site dir gets the grain and, below,
  # only the portraits its pages reference (not the whole folder)
  mkdir -p "$D/img/players"
  [ -e "$ROOT/docs/img/grain.png" ] && cp -n "$ROOT/docs/img/grain.png" "$D/img/" 2>/dev/null || true
fi
cp "$O/index.html" "$D/index.html"
cp "$O/atlas_FW.svg" "$O/atlas_MF.svg" "$O/atlas_DF.svg" "$O/intl_cohort_heatmap.svg" "$O/big5_series.svg" \
   "$O/league_strength.svg" "$O/league_strength_ppc.svg" "$O/model_comparison.svg" "$O/series_model.svg" \
   "$O/eda_distributions.svg" "$O/eda_shrinkage.svg" "$O/gk_export_age.svg" "$O/youth_panel.svg" \
   "$O/gap_decomposition.svg" "$O/export_age_model.svg" "$O/fare_dots.svg" "$O/pathway_slope.svg" \
   "$O/why_funnel.svg" "$O/style.css" "$D/"

# interactive-chart data (src.charts_export), if it was written for this run
if [ -d "$O/charts" ]; then mkdir -p "$D/charts" && cp "$O/charts/"*.json "$D/charts/"; fi
${=PY} "$S/enrich_index.py" "$D/index.html" --lang en
${=PY} "$S/atlas_meta.py" "$D" >/dev/null
${=PY} "$S/svg_theme.py" "$D" >/dev/null   # legacy-palette figures into the theme (idempotent)
# the player atlas (docs/atlas/): needs charts/careers.json (src.careers_export)
if [ -f "$D/charts/careers.json" ]; then ${=PY} "$S/build_atlas.py" "$D"; else echo "no charts/careers.json -- \`uv run python -m src.careers_export\` for the player atlas" >&2; fi
# portraits and cut-outs (src.fetch_photos*, site/cutouts.py) are made once
# into docs/img/players/; another site dir gets only the ones its pages
# reference, not the whole folder
if [ "$D" != "$ROOT/docs" ]; then
  for f in $(grep -oh 'img/players/[A-Za-z0-9_-]*\.\(jpg\|png\)' "$D/index.html" "$D/charts/careers.json" 2>/dev/null | sort -u); do
    [ -e "$D/$f" ] || { [ -e "$ROOT/docs/$f" ] && cp "$ROOT/docs/$f" "$D/$f"; }
  done
fi
echo "built $D/index.html (en, NATION=$NATION), atlas_meta.json"
