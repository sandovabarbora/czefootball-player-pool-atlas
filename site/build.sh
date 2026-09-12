#!/bin/zsh
# Build the published site from the Czech render:
#   docs/index.html     English (default)
#   docs/cs/index.html  Czech
#   docs/atlas_meta.json  interaction metadata for atlas.js
# Source of truth for content: site/source/index.cs.html (= outputs/index.html
# from `make render`). Layout/photos/i18n/formulas are applied by the scripts
# here; translation is exact-match so a re-rendered source will fail loudly
# where the copy changed (fix the pair in translate_index.py).
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
S="$ROOT/site"
D="$ROOT/docs"
cp "$S/source/index.cs.html" "$D/index.html"
python3 "$S/enrich_index.py" "$D/index.html"
mkdir -p "$D/cs"
cp "$D/index.html" "$D/cs/index.html"
sed -i '' -e 's|href="style.css"|href="../style.css"|' -e 's|href="modern.css"|href="../modern.css"|' \
          -e 's|src="video_poc_|src="../video_poc_|g' -e 's|src="atlas.js"|src="../atlas.js"|' "$D/cs/index.html"
python3 "$S/translate_index.py" "$D/index.html"
python3 "$S/svg_labels.py" "$D" >/dev/null
python3 "$S/atlas_meta.py" "$D" >/dev/null
echo "built docs/index.html (en) + docs/cs/index.html (cs)"
