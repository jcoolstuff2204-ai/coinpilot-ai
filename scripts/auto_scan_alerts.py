"""Scheduled CoinPilot scanner.

Use locally:
    python scripts/auto_scan_alerts.py --once

Use in GitHub Actions:
    The workflow runs this file on a cron schedule and sends Telegram/email alerts.
"""

from __future__ import annotations

import argparse
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run CoinPilot AI market scans and send alerts.")
    parser.add_argument("--account-size", type=float, default=float(os.getenv("COINPILOT_ACCOUNT_SIZE", "1000")))
    parser.add_argument("--risk-percent", type=float, default=float(os.getenv("COINPILOT_RISK_PERCENT", "1")))
    parser.add_argument("--universe-limit", type=int, default=int(os.getenv("COINPILOT_UNIVERSE_LIMIT", "100")))
    parser.add_argument("--deep-scan-limit", type=int, default=int(os.getenv("COINPILOT_DEEP_SCAN_LIMIT", "20")))
    parser.add_argument("--top-n", type=int, default=int(os.getenv("COINPILOT_TOP_N", "10")))
    parser.add_argument("--rank-start", type=int, default=int(os.getenv("COINPILOT_RANK_START", "1")))
    parser.add_argument("--min-volume-usd", type=float, default=float(os.getenv("COINPILOT_MIN_VOLUME_USD", "300000")))
    parser.add_argument("--interval-minutes", type=int, default=int(os.getenv("COINPILOT_INTERVAL_MINUTES", "30")))
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--send-empty", action="store_true", default=os.getenv("COINPILOT_SEND_EMPTY", "false").lower() == "true")
    return parser.parse_args()


def score_line(index: int, item: dict) -> str:
    rr = f"1:{item['risk_reward_ratio']:.2f}" if item.get("risk_reward_ratio") else "N/A"
    return (
        f"{index}. {item['coin_id'].upper()} | {item['recommendation']} | "
        f"{item['confidence']}% | RSI {item['rsi']:.1f} | Vol {item['volume_vs_average']:.0f}% | RR {rr}"
    )


def build_message(scan: dict) -> tuple[str, str, bool]:
    results = scan.get("results", [])
    alerts = scan.get("alerts", [])
    buy_candidates = [
        item
        for item in results
        if item.get("recommendation") in {"Buy Setup", "Potential Buy", "Watch for Entry"}
    ]
    exit_risks = [item for item in results if item.get("recommendation") == "Sell / Avoid"]

    urgent = any(item.get("recommendation") in {"Buy Setup", "Potential Buy"} for item in results) or bool(exit_risks)
    subject = "CoinPilot AI Alert" if urgent else "CoinPilot AI Market Scan"

    lines = ["CoinPilot AI Market Radar", ""]
    if buy_candidates:
        lines.append("Buy / Watch Candidates")
        for index, item in enumerate(buy_candidates[:10], start=1):
            lines.append(score_line(index, item))
            lines.append(f"   {item['reason']}")
        lines.append("")
    else:
        lines.append("No buy candidates passed the current filters.")
        lines.append("")

    if exit_risks:
        lines.append("Exit / Avoid Risks")
        for item in exit_risks[:5]:
            lines.append(f"- {item['coin_id'].upper()}: {item['reason']}")
        lines.append("")

    lines.append("Top Ranked Scan")
    for index, item in enumerate(results[:10], start=1):
        lines.append(score_line(index, item))

    if scan.get("errors"):
        lines.append("")
        lines.append(f"Skipped coins: {len(scan['errors'])}")

    lines.append("")
    lines.append("Manual review only. CoinPilot does not auto-buy or auto-sell.")
    return subject, "\n".join(lines), urgent


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

    subject, body, urgent = build_message(scan)
    if urgent or args.send_empty:
        channels = send_notification(subject, body)
        print(f"Sent {subject} via {', '.join(channels)}.")
    else:
        print("Scan completed. No urgent buy/exit alert to send.")
        print(body)


def main() -> None:
    args = parse_args()
    while True:
        run_once(args)
        if args.once:
            break
        time.sleep(max(1, args.interval_minutes) * 60)


if __name__ == "__main__":
    main()
