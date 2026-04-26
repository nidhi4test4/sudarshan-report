#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/azureuser/sudarshan_saas/reporting"
PY="/home/azureuser/sudarshan_saas/venv/bin/python3"

IST date for update_report.py argument
DATE_IST=$(TZ=Asia/Kolkata date +%F)

Skip Indian public holidays
IS_HOLIDAY=$($PY - <<'PY'
from datetime import datetime
from zoneinfo import ZoneInfo
import holidays

d = datetime.now(ZoneInfo("Asia/Kolkata")).date()
print("1" if d in holidays.India(years=d.year) else "0")
PY
)

if [ "$IS_HOLIDAY" = "1" ]; then
echo "$(date -Is) India holiday, skipped."
exit 0
fi
cd "$ROOT"
"$PY" update_report.py "$DATE_IST"
