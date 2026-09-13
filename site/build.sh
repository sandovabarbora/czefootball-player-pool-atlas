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
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
S="$ROOT/site"
D="$ROOT/docs"
O="$ROOT/outputs"
PY=${PYTHON:-python3}
if command -v uv >/dev/null 2>&1 && [ -f "$ROOT/pyproject.toml" ]; then PY="uv run --project $ROOT python"; fi

for f in index.html cs/index.html atlas_FW.svg atlas_MF.svg atlas_DF.svg intl_cohort_heatmap.svg style.css; do
  [ -f "$O/$f" ] || { echo "missing $O/$f — run \`make render\` first" >&2; exit 1; }
done

mkdir -p "$D/cs"
cp "$O/index.html" "$D/index.html"
cp "$O/cs/index.html" "$D/cs/index.html"
cp "$O/atlas_FW.svg" "$O/atlas_MF.svg" "$O/atlas_DF.svg" "$O/intl_cohort_heatmap.svg" "$O/style.css" "$D/"

${=PY} "$S/enrich_index.py" "$D/index.html" --lang en
${=PY} "$S/enrich_index.py" "$D/cs/index.html" --lang cs
${=PY} "$S/svg_labels.py" "$D" >/dev/null
${=PY} "$S/atlas_meta.py" "$D" >/dev/null
echo "built docs/index.html (en) + docs/cs/index.html (cs), docs/cs/*.svg, docs/atlas_meta.json"
