#!/usr/bin/env python3
"""
update_report.py — Parse an EOD trade log, add the day to trade_analysis.html, push to GitHub.

Usage:
  python update_report.py              # today's date
  python update_report.py 2026-03-24   # specific date
"""

import os, re, sys, stat, shutil, subprocess
from datetime import date as Date
from pathlib import Path

# Config
BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = Path(
    os.getenv(
        "REPORT_LOGS_DIR",
        "/home/azureuser/sudarshan_saas/clients/79b9280a-b75e-44af-9797-c83e46baf934/logs",
    )
)
HTML_FILE = Path(os.getenv("REPORT_HTML_FILE", str(BASE_DIR / "trade_analysis.html")))
FIVE_MIN_LOGS_DIR = Path(
    os.getenv("REPORT_5M_LOGS_DIR", str(BASE_DIR.parent / "logs"))
)
GITHUB_URL = "git@github.com:nidhi4test4/sudarshan-report.git"
PAGES_URL = "https://nidhi4test4.github.io/sudarshan-report/"
TEMP_DIR = Path(os.getenv("REPORT_TEMP_DIR", str(Path.home() / "temp-nidhi-report")))

ARRAY_CLOSE_MARKER = "// ═══════════════════════════ KPI STRIP"
FIFTEEN_START = "const fifteenDays = ["
FIVE_START = "const fiveDays = ["
DATASETS_START = "const datasets = {"

def find_log(date_str: str) -> Path | None:
    bot = LOGS_DIR / "bot.log"

    # 1) If bot.log has the exact date EOD block, use it first
    if bot.exists() and has_eod_for_date(bot, date_str):
        return bot

    # 2) Then check dated files (cloud first + legacy)
    for pattern in [
        f"Dashboard_{date_str}.txt",
        f"Nidhi-Sudarshan-Pro-Final_{date_str}.log",
        f"JP-Sudarshan-Pro-Final_{date_str}.log",
        f"Nidhi-Sudarshan-final_{date_str}.log",
        f"Nidhi-Sudarshan-Pro-Final-Websocket_{date_str}.log",
    ]:
        p = LOGS_DIR / pattern
        if p.exists() and has_eod_for_date(p, date_str):
            return p

    # 3) Final fallback: return any existing dated file
    for pattern in [
        f"Dashboard_{date_str}.txt",
        f"Nidhi-Sudarshan-Pro-Final_{date_str}.log",
        f"JP-Sudarshan-Pro-Final_{date_str}.log",
        f"Nidhi-Sudarshan-final_{date_str}.log",
        f"Nidhi-Sudarshan-Pro-Final-Websocket_{date_str}.log",
    ]:
        p = LOGS_DIR / pattern
        if p.exists():
            return p

    return None

def to_eod_label(date_str: str) -> str:
    # 2026-04-07 -> 07-Apr-2026
    d = Date.fromisoformat(date_str)
    return d.strftime("%d-%b-%Y")

def has_eod_for_date(path: Path, date_str: str) -> bool:
    try:
        txt = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    return f"EOD PERFORMANCE REPORT | {to_eod_label(date_str)}" in txt

# ── 2. Parse the EOD performance report ───────────────────────────────────────
def parse_log(log_path: Path, target_date: Date):
    text = log_path.read_text(encoding="utf-8", errors="ignore")

    if "EOD PERFORMANCE REPORT" not in text:
        return None, "No EOD PERFORMANCE REPORT found in log."

    # If the file contains multiple days, isolate only the requested day's EOD block.
    target_label = target_date.strftime("%d-%b-%Y")
    report_re = re.compile(
        r"(?m)^(?P<ts>\d{4}-\d{2}-\d{2} (?P<hm>\d{2}:\d{2}):\d{2},\d{3}) - INFO - "
        r"EOD PERFORMANCE REPORT \| (?P<label>\d{2}-[A-Za-z]{3}-\d{4})\s*$"
    )
    reports = list(report_re.finditer(text))

    block = text
    report_match = None
    if reports:
        for i, m in enumerate(reports):
            if m.group("label") != target_label:
                continue
            report_match = m
            start = m.start()
            end = reports[i + 1].start() if i + 1 < len(reports) else len(text)
            block = text[start:end]

    if reports and report_match is None:
        return None, f"No EOD PERFORMANCE REPORT found for {target_label}."

    # Parse individual trade rows
    trade_re = re.compile(
        r"INFO -\s+(\w+)\s+(BUY|SELL)\s+(\d{2}:\d{2})/(\d{2}:\d{2})\s+"
        r"(\d+)\s+([\d.]+)\s+([\d.]+)\s+(-?[\d.]+)"
    )
    trades = [
        dict(sym=m[1], side=m[2], entry=m[3], exit=m[4],
             qty=int(m[5]), ep=float(m[6]), xp=float(m[7]), pnl=float(m[8]))
        for m in trade_re.finditer(block)
    ]

    # Parse summary line
    sm = re.search(r"GROSS:\s*(-?[\d.]+)\s*\|\s*CHARGES:\s*([\d.]+)\s*\|\s*NET:\s*(-?[\d.]+)", block)
    if not sm:
        return None, "GROSS/CHARGES/NET summary line not found."

    # Determine session end time
    eod_m = re.search(r"(\d{2}:\d{2}):\d{2}.*?EOD SQUARE OFF INITIATED", block)
    if eod_m:
        session_end = eod_m.group(1) + " ✅"
        anomaly = ""
    elif report_match:
        session_end = report_match.group("hm") + " ✅"
        anomaly = ""
    else:
        all_times = re.findall(r"\d{4}-\d{2}-\d{2} (\d{2}:\d{2}):\d{2}", block)
        last_t = all_times[-1] if all_times else "??"
        session_end = last_t + " ⚠️"
        anomaly = f"Session ended early at {last_t}"

    # Detect common anomalies
    if "403 Forbidden" in block:
        anomaly = "; ".join(filter(None, [anomaly, "Token expired (403)"]))
    if re.search(r"started.{0,40}late|LATE.{0,20}START", block, re.I):
        anomaly = "; ".join(filter(None, [anomaly, "Late start"]))

    return {
        "trades":      trades,
        "gross":       float(sm.group(1)),
        "charges":     float(sm.group(2)),
        "net":         float(sm.group(3)),
        "session_end": session_end,
        "anomaly":     anomaly,
    }, None

def parse_5m_log(log_path: Path):
    text = log_path.read_text(encoding="utf-8", errors="ignore")
    if "FINAL TRADE SUMMARY" not in text:
        return None

    try:
        d = Date.fromisoformat(log_path.stem.split("_")[-1])
    except Exception:
        return None

    trade_re = re.compile(
        r"INFO -\s+\d+\.\s+(NSE:[^|]+)\s+\|\s+(BUY|SELL)\s+\|\s+Qty\s+(\d+)\s+\|\s+"
        r"Entry\s+([\d.]+)\s+\|\s+Exit\s+([\d.]+)\s+\|\s+PnL\s+(-?[\d.]+)\s+\|\s+"
        r"In\s+(\d{2}:\d{2}):\d{2}\s+\|\s+Out\s+(\d{2}:\d{2}):\d{2}\s+\|\s+Reason\s+(.*)"
    )
    trades = [
        dict(
            sym=m[1].replace("NSE:", "").replace("-EQ", "").strip(),
            side=m[2],
            entry=m[7],
            exit=m[8],
            qty=int(m[3]),
            ep=float(m[4]),
            xp=float(m[5]),
            pnl=float(m[6]),
        )
        for m in trade_re.finditer(text)
    ]

    closed_re = re.search(
        r"Closed Trades:\s*(\d+)\s*\|\s*Wins:\s*(\d+)\s*\|\s*Losses:\s*(\d+)\s*\|\s*Breakeven:\s*(\d+)\s*\|\s*Realized PnL:\s*(-?[\d.]+)",
        text,
    )
    net_re = re.search(r"Net PnL:\s*(-?[\d.]+)", text)
    if not net_re:
        return None

    gross = float(closed_re.group(5)) if closed_re else float(net_re.group(1))
    charges = round(sum(estimate_intraday_equity_charges(t) for t in trades), 2)
    net = round(gross - charges, 2)

    anomaly = []
    if text.count("Authenticating with Fyers...") > 1:
        anomaly.append("Restarted intraday")
    if "Shutdown requested: SIGINT received" in text:
        anomaly.append("Manual interrupt/restart")

    session_end = "15:10 ✅" if "Reached SQUARE_OFF_TIME" in text else "15:11 ✅"
    bias = "MIXED"
    if "STRONG BEARISH" in text and "STRONG BULLISH" not in text:
        bias = "BEARISH"
    elif "STRONG BULLISH" in text and "STRONG BEARISH" not in text:
        bias = "BULLISH"

    return {
        "date": f"{d.day:02d} {d.strftime('%b')}",
        "day": d.strftime("%a"),
        "bias": bias,
        "sessionEnd": session_end,
        "anomaly": "; ".join(anomaly),
        "gross": gross,
        "charges": charges,
        "net": net,
        "trades": trades,
    }

def estimate_intraday_equity_charges(trade: dict) -> float:
    entry = float(trade["ep"])
    exit_p = float(trade["xp"])
    qty = int(trade["qty"])
    side = str(trade["side"]).upper()

    buy_val = entry * qty if side == "BUY" else exit_p * qty
    sell_val = exit_p * qty if side == "BUY" else entry * qty
    turnover = buy_val + sell_val

    brok_buy = min(20, buy_val * 0.0003)
    brok_sell = min(20, sell_val * 0.0003)
    brokerage = brok_buy + brok_sell
    stt = sell_val * 0.00025
    txn_charge = turnover * 0.0000325
    stamp_duty = buy_val * 0.00003
    sebi_fees = turnover * 0.000001
    gst = (brokerage + txn_charge + sebi_fees) * 0.18

    return round(brokerage + stt + txn_charge + stamp_duty + sebi_fees + gst, 2)

# ── 3. Determine market bias from Dashboard snapshot file ─────────────────────
def get_bias(date_str: str) -> str:
    dash = LOGS_DIR / f"Dashboard_{date_str}.txt"
    if not dash.exists():
        return "NEUTRAL"
    text = dash.read_text(errors="ignore")
    b, u, n = text.count("BEARISH"), text.count("BULLISH"), text.count("NEUTRAL")
    if b > u and b > n: return "BEARISH"
    if u > b and u > n: return "BULLISH"
    return "NEUTRAL"

def _render_trades_js(trades: list[dict]) -> str:
    return "\n".join(
        f'      {{ sym:"{t["sym"]}", side:"{t["side"]}", entry:"{t["entry"]}", exit:"{t["exit"]}", qty:{t["qty"]}, ep:{t["ep"]}, xp:{t["xp"]}, pnl:{t["pnl"]} }},'
        for t in trades
    )

def _render_day_entry_js(day: dict) -> str:
    trade_lines = _render_trades_js(day["trades"])
    return (
        f'  {{\n'
        f'    date: "{day["date"]}", day: "{day["day"]}", bias: "{day["bias"]}",\n'
        f'    sessionEnd: "{day["sessionEnd"]}", anomaly: "{day["anomaly"]}",\n'
        f'    gross: {day["gross"]}, charges: {day["charges"]}, net: {day["net"]},\n'
        f'    trades: [\n{trade_lines}\n    ]\n'
        f'  }},\n'
    )

def _extract_array_content(content: str, start_marker: str, end_marker: str) -> tuple[str, int, int, int]:
    start = content.index(start_marker)
    after_start = start + len(start_marker)
    next_section = content.index(end_marker, after_start)
    array_end = content.rfind("];", after_start, next_section)
    if array_end == -1:
        raise ValueError(f"Could not locate closing array token before {end_marker}")
    return content[after_start:array_end], start, array_end, next_section

def _replace_array_section(content: str, start_marker: str, end_marker: str, new_inner: str) -> str:
    _, start, array_end, _ = _extract_array_content(content, start_marker, end_marker)
    return content[: start + len(start_marker)] + "\n" + new_inner.rstrip() + "\n" + content[array_end:]

# ── 4. Inject the new day entry into HTML ─────────────────────────────────────
def update_html(d: Date, data: dict, bias: str) -> bool:
    date_display = d.strftime("%d %b").lstrip("0") if d.day > 9 else d.strftime("%d %b")
    # Consistent format: "02 Mar" for single-digit days, "23 Mar" for double
    date_display = f"{d.day:02d} {d.strftime('%b')}"
    day_name     = d.strftime("%a")

    content = HTML_FILE.read_text(encoding="utf-8", errors="ignore")

    fifteen_inner, _, _, _ = _extract_array_content(content, FIFTEEN_START, FIVE_START)
    new_entry = _render_day_entry_js({
        "date": date_display,
        "day": day_name,
        "bias": bias,
        "sessionEnd": data["session_end"],
        "anomaly": data["anomaly"],
        "gross": data["gross"],
        "charges": data["charges"],
        "net": data["net"],
        "trades": data["trades"],
    })
    date_obj_re = re.compile(
        rf'  \{{\n\s*date: "{re.escape(date_display)}".*?\n  \}},\n',
        re.S,
    )
    if date_obj_re.search(fifteen_inner):
        fifteen_inner = date_obj_re.sub(new_entry, fifteen_inner, count=1)
        print(f"  ♻️  Replaced existing 15m entry for {date_display}.")
    else:
        fifteen_inner = fifteen_inner.rstrip() + "\n" + new_entry
    content = _replace_array_section(content, FIFTEEN_START, FIVE_START, fifteen_inner)

    five_days = []
    for path in sorted(FIVE_MIN_LOGS_DIR.glob("JP_intraday_final_5mints_*.log")):
      parsed = parse_5m_log(path)
      if parsed:
          five_days.append(parsed)
    five_inner = "".join(_render_day_entry_js(day) for day in five_days)
    content = _replace_array_section(content, FIVE_START, DATASETS_START, five_inner)

    # Update title and period header; supports month rollovers (e.g., 01 Apr)
    title_end = f"{d.strftime('%b')} {d.day}"
    period_end = f"{d.day} {d.strftime('%B')} {d.year}"
    content = re.sub(
        r"(<title>Sudarshan Bot 15M — Trade Analysis Report \().*(\)</title>)",
        rf"\g<1>Mar 2–{title_end}, {d.year}\g<2>",
        content,
        count=1,
    )
    content = re.sub(
        r"Period:\s*[^<]*?&nbsp;\|&nbsp;",
        f"Period: 2 March 2026 – {period_end} &nbsp;|&nbsp;",
        content,
        count=1,
    )

    HTML_FILE.write_text(content, encoding="utf-8")
    print(f"  ✅ HTML updated with 15m {date_display} ({day_name}) | Bias: {bias} | NET: ₹{data['net']:.2f}")
    return True

# ── Helper: force-delete a directory tree (handles Windows read-only files) ───
def rmtree_force(path):
    def _on_error(func, p, _):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onexc=_on_error)

# ── 5. Clone, commit, push ────────────────────────────────────────────────────
def push_to_github(date_display: str, net: float):
    if TEMP_DIR.exists():
        rmtree_force(TEMP_DIR)

    print("  📦 Cloning repo ...")
    subprocess.run(["git", "clone", GITHUB_URL, str(TEMP_DIR)], check=True,
                   capture_output=True)

    shutil.copy(HTML_FILE, TEMP_DIR / "index.html")

    sign = "+" if net >= 0 else ""
    msg = (
        f"Add {date_display} trade data (NET: {sign}₹{net:.2f})\n\n"
        f"Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
    )
    subprocess.run(["git", "add", "index.html"], cwd=TEMP_DIR, check=True)
    result = subprocess.run(["git", "commit", "-m", msg], cwd=TEMP_DIR,
                            capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ⚠️  Nothing to commit: {result.stdout.strip()}")
        rmtree_force(TEMP_DIR)
        return

    subprocess.run(["git", "push", "origin", "main"], cwd=TEMP_DIR, check=True)
    rmtree_force(TEMP_DIR)
    print(f"  🚀 Pushed! View at: {PAGES_URL}")

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) > 1:
        try:
            d = Date.fromisoformat(sys.argv[1])
        except ValueError:
            print("❌ Invalid date. Use YYYY-MM-DD (e.g. 2026-03-24)")
            sys.exit(1)
    else:
        d = Date.today()

    date_str     = d.strftime("%Y-%m-%d")
    date_display = f"{d.day:02d} {d.strftime('%b')}"

    print(f"\n🗓️  Date       : {date_str}")

    log_file = find_log(date_str)
    if not log_file:
        print(f"❌ No log file found for {date_str} in {LOGS_DIR}")
        sys.exit(1)
    print(f"📄 Log file   : {log_file.name}")

    data, err = parse_log(log_file, d)
    if err:
        print(f"❌ Parse error: {err}")
        sys.exit(1)

    bias = get_bias(date_str)
    print(f"📊 Summary    : GROSS=₹{data['gross']}  CHARGES=₹{data['charges']}  NET=₹{data['net']}")
    print(f"📈 Trades     : {len(data['trades'])}  |  Bias: {bias}  |  Session end: {data['session_end']}")
    if data["anomaly"]:
        print(f"⚠️  Anomaly    : {data['anomaly']}")

    updated = update_html(d, data, bias)
    if updated:
        push_to_github(date_display, data["net"])

    print()

if __name__ == "__main__":
    main()
