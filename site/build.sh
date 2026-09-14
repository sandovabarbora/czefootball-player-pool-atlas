#!/bin/zsh
# Build the published site from the two rendered pages (`make render`):
#   docs/index.html        English (outputs/index.html)
#   docs/cs/index.html     Czech   (outputs/cs/index.html, assets via ../)
#   docs/*.svg, style.css  copied from outputs/
#   docs/cs/*.svg          Czech figure labels (svg_labels.py)
#   docs/atlas_meta.json   interaction metadata for atlas.js (atlas_meta.py)
# enrich_index.py applies the site layer (top bar, photos, folds, search) to
# each page; every script asserts its match counts and fails loudly when the
# render changed under it.
#
# usage: site/build.sh [OUT_DIR]     (default: docs/ -- the published site)
# With another OUT_DIR the static assets that only live in docs/ (modern.css,
# atlas.js, CNAME, .nojekyll, img/) are copied there too, so a test can build
# a complete site into a temp dir without touching the committed docs/.
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
S="$ROOT/site"
D="${1:-$ROOT/docs}"
D=$(mkdir -p "$D" && cd "$D" && pwd)
O="$ROOT/outputs"
PY=${PYTHON:-python3}
if command -v uv >/dev/null 2>&1 && [ -f "$ROOT/pyproject.toml" ]; then PY="uv run --project $ROOT python"; fi

for f in index.html cs/index.html atlas_FW.svg atlas_MF.svg atlas_DF.svg intl_cohort_heatmap.svg big5_series.svg style.css; do
  [ -f "$O/$f" ] || { echo "missing $O/$f — run \`make render\` first (big5_series.svg: \`uv run python -m src.big5_series\`)" >&2; exit 1; }
done

mkdir -p "$D/cs"
if [ "$D" != "$ROOT/docs" ]; then
  for a in modern.css atlas.js CNAME .nojekyll; do [ -e "$ROOT/docs/$a" ] && cp "$ROOT/docs/$a" "$D/"; done
  [ -d "$ROOT/docs/img" ] && [ ! -e "$D/img" ] && cp -R "$ROOT/docs/img" "$D/img"
fi
cp "$O/index.html" "$D/index.html"
cp "$O/cs/index.html" "$D/cs/index.html"
cp "$O/atlas_FW.svg" "$O/atlas_MF.svg" "$O/atlas_DF.svg" "$O/intl_cohort_heatmap.svg" "$O/big5_series.svg" "$O/style.css" "$D/"

${=PY} "$S/enrich_index.py" "$D/index.html" --lang en
${=PY} "$S/enrich_index.py" "$D/cs/index.html" --lang cs
${=PY} "$S/svg_labels.py" "$D" >/dev/null
${=PY} "$S/atlas_meta.py" "$D" >/dev/null
echo "built $D/index.html (en) + $D/cs/index.html (cs), cs/*.svg, atlas_meta.json"
