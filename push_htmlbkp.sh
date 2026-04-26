#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="$SCRIPT_DIR/trade_analysis.html"
TEMP="$HOME/temp-nidhi-report"
REPO="https://github.com/nidhi4test4/sudarshan-report"

echo ""
echo "📤 Pushing trade_analysis.html to GitHub..."

rm -rf "$TEMP"
git clone "$REPO" "$TEMP" 2>/dev/null
cp "$SRC" "$TEMP/index.html"

cd "$TEMP"
git add index.html
git commit -m "Manual update - $(date '+%Y-%m-%d %H:%M')"
git push origin main

cd "$SCRIPT_DIR"
rm -rf "$TEMP"

echo ""
echo "✅ Done! View at: https://nidhi4test4.github.io/sudarshan-report/"
echo "   (GitHub Pages refreshes in ~1 min)"
