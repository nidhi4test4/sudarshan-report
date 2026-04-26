#!/bin/bash
set -euo pipefail

SCRIPT_DIR="
(
𝑐
𝑑
"
(cd"(dirname "$0")" && pwd)"
SRC="$SCRIPT_DIR/trade_analysis.html"
TEMP="$HOME/temp-nidhi-report"
REPO="https://github.com/nidhi4test4/sudarshan-report"

echo ""
echo "Pushing trade_analysis.html to GitHub..."

rm -rf "$TEMP"
git clone "$REPO" "$TEMP"

cp "$SRC" "$TEMP/index.html"

cd "$TEMP"

if git diff --quiet -- index.html; then
echo "No changes in index.html, skipping commit."
cd "$SCRIPT_DIR"
rm -rf "$TEMP"
exit 0
fi

git add index.html
git commit -m "Auto update - $(date '+%Y-%m-%d %H:%M')"
git push origin main
cd "$SCRIPT_DIR"
rm -rf "$TEMP"

echo ""
echo "Done. View at: https://nidhi4test4.github.io/sudarshan-report/"
echo "GitHub Pages refreshes in about 1 minute."
