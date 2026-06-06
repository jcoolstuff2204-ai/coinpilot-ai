"""Scheduled CoinPilot scanner with alert quality controls.

The scanner sends high-signal decision-support alerts only. It never places
orders, connects to an exchange account, auto-buys, or auto-sells.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.analysis_service import scan_market
from src.models import MarketScanRequest
from src.notifier import send_notification


STATE_PATH = PROJECT_ROOT / "data" / "alert_state.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run CoinPilot AI market scans and send high-signal alerts.")
    parser.add_argument("--account-size", type=float, default=float(os.getenv("COINPILOT_ACCOUNT_SIZE", "1000")))
    parser.add_argument("--risk-percent", type=float, default=float(os.getenv("COINPILOT_RISK_PERCENT", "1")))
    parser.add_argument("--universe-limit", type=int, default=int(os.getenv("COINPILOT_UNIVERSE_LIMIT", "100")))
    parser.add_argument("--deep-scan-limit", type=int, default=int(os.getenv("COINPILOT_DEEP_SCAN_LIMIT", "20")))
    parser.add_argument("--top-n", type=int, default=int(os.getenv("COINPILOT_TOP_N", "10")))
    parser.add_argument("--rank-start", type=int, default=int(os.getenv("COINPILOT_RANK_START", "1")))
    parser.add_argument("--min-volume-usd", type=float, default=float(os.getenv("COINPILOT_MIN_VOLUME_USD", "300000")))
    parser.add_argument("--interval-minutes", type=int, default=int(os.getenv("COINPILOT_INTERVAL_MINUTES", "30")))
    parser.add_argument("--cooldown-hours", type=float, default=float(os.getenv("COINPILOT_ALERT_COOLDOWN_HOURS", "6")))
    parser.add_argument("--min-buy-confidence", type=int, default=int(os.getenv("COINPILOT_MIN_BUY_CONFIDENCE", "55")))
    parser.add_argument("--min-exit-confidence", type=int, default=int(os.getenv("COINPILOT_MIN_EXIT_CONFIDENCE", "65")))
    parser.add_argument("--alert-watch", action="store_true", default=os.getenv("COINPILOT_ALERT_WATCH", "false").lower() == "true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--send-empty", action="store_true", default=os.getenv("COINPILOT_SEND_EMPTY", "false").lower() == "true")
    return parser.parse_args()


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"sent": {}}
    try:
        return json.loads(STATE_PATH.read_text())
    except json.JSONDecodeError:
        return {"sent": {}}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True))


def alert_key(item: dict) -> str:
    return f"{item['coin_id']}|{item['recommendation']}"


def is_new_alert(item: dict, state: dict, cooldown_hours: float) -> bool:
    last_sent = float(state.get("sent", {}).get(alert_key(item), 0))
    return time.time() - last_sent >= cooldown_hours * 3600


def mark_sent(items: list[dict], state: dict) -> None:
    state.setdefault("sent", {})
    now = time.time()
    for item in items:
        state["sent"][alert_key(item)] = now


def rr_text(item: dict) -> str:
    if item.get("risk_reward_ratio"):
        return f"1:{item['risk_reward_ratio']:.2f}"
    return "N/A"


def price_text(value) -> str:
    if value is None:
        return "N/A"
    return f"${float(value):,.6g}"


def signal_line(index: int, item: dict) -> str:
    return (
        f"{index}. {item['coin_id'].upper()} | {item['recommendation']} | "
        f"{item['confidence']}% | RSI {item['rsi']:.1f} | Vol {item['volume_vs_average']:.0f}% | RR {rr_text(item)}"
    )


def classify_alerts(results: list[dict], args: argparse.Namespace) -> tuple[list[dict], list[dict], list[dict]]:
    buy = [
        item
        for item in results
        if item.get("recommendation") in {"Buy Setup", "Potential Buy"}
        and int(item.get("confidence") or 0) >= args.min_buy_confidence
    ]
    watch = [
        item
        for item in results
        if args.alert_watch
        and item.get("recommendation") == "Watch for Entry"
        and int(item.get("confidence") or 0) >= args.min_buy_confidence
    ]
    exit_risk = [
        item
        for item in results
        if item.get("recommendation") == "Sell / Avoid"
        and int(item.get("confidence") or 0) >= args.min_exit_confidence
    ]
    return buy, watch, exit_risk


def build_message(scan: dict, new_buy: list[dict], new_watch: list[dict], new_exit: list[dict]) -> tuple[str, str]:
    results = scan.get("results", [])
    subject = "CoinPilot AI Alert"
    lines = ["CoinPilot AI Alert", ""]

    if new_buy:
        lines.append("Buy Candidates")
        for index, item in enumerate(new_buy[:5], start=1):
            lines.append(signal_line(index, item))
            lines.append(f"   Entry: {item.get('entry_zone', 'Manual review')}")
            lines.append(f"   Stop: {price_text(item.get('stop_loss'))} | Target: {price_text(item.get('take_profit'))}")
            lines.append(f"   Why: {item['reason']}")
        lines.append("")

    if new_watch:
        lines.append("Watch for Entry")
        for index, item in enumerate(new_watch[:5], start=1):
            lines.append(signal_line(index, item))
            lines.append(f"   Trigger to watch: pullback/volume confirmation near support or MA20.")
            lines.append(f"   Why: {item['reason']}")
        lines.append("")

    if new_exit:
        lines.append("Exit / Avoid Risks")
        for item in new_exit[:5]:
            lines.append(f"- {item['coin_id'].upper()} | {item['confidence']}% | RSI {item['rsi']:.1f}")
            lines.append(f"  Why: {item['reason']}")
        lines.append("")

    lines.append("Top 5 Context")
    for index, item in enumerate(results[:5], start=1):
        lines.append(signal_line(index, item))

    if scan.get("errors"):
        lines.append("")
        lines.append(f"Skipped coins: {len(scan['errors'])}")

    lines.append("")
    lines.append("Manual review only. CoinPilot does not auto-buy or auto-sell.")
    return subject, "\n".join(lines)


def build_empty_summary(scan: dict) -> tuple[str, str]:
    lines = ["CoinPilot AI Market Scan", "", "No new high-signal alerts after cooldown filtering.", ""]
    for index, item in enumerate(scan.get("results", [])[:10], start=1):
        lines.append(signal_line(index, item))
    lines.append("")
    lines.append("Manual review only. CoinPilot does not auto-buy or auto-sell.")
    return "CoinPilot AI Market Scan", "\n".join(lines)


def run_once(args: argparse.Namespace) -> None:
    scan = scan_market(
        MarketScanRequest(
            account_size=args.account_size,
            risk_percent=args.risk_percent,
            universe_limit=args.universe_limit,
            deep_scan_limit=args.deep_scan_limit,
            top_n=args.top_n,
            rank_start=args.rank_start,
            min_volume_usd=args.min_volume_usd,
        )
    ).model_dump()

    state = load_state()
    buy, watch, exit_risk = classify_alerts(scan.get("results", []), args)
    new_buy = [item for item in buy if is_new_alert(item, state, args.cooldown_hours)]
    new_watch = [item for item in watch if is_new_alert(item, state, args.cooldown_hours)]
    new_exit = [item for item in exit_risk if is_new_alert(item, state, args.cooldown_hours)]
    new_alerts = new_buy + new_watch + new_exit

    if new_alerts:
        subject, body = build_message(scan, new_buy, new_watch, new_exit)
        channels = send_notification(subject, body)
        mark_sent(new_alerts, state)
        save_state(state)
        print(f"Sent {len(new_alerts)} new alert(s) via {', '.join(channels)}.")
    elif args.send_empty:
        subject, body = build_empty_summary(scan)
        channels = send_notification(subject, body)
        print(f"Sent empty scan summary via {', '.join(channels)}.")
    else:
        print("Scan completed. No new high-signal alerts after cooldown filtering.")
        print(build_empty_summary(scan)[1])


def main() -> None:
    args = parse_args()
    while True:
        run_once(args)
        if args.once:
            break
        time.sleep(max(1, args.interval_minutes) * 60)


if __name__ == "__main__":
    main()
