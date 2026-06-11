"""Paper-trade lifecycle tracking.

This module simulates positions for learning and review only. It never submits
orders and never connects to an exchange account.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import pandas as pd

from src.config import settings
from src.market_data import fetch_market_data


ACTIVE_STATUSES = {"Active", "Target Hit", "Stopped", "Invalidated"}


def initialize_paper_trades() -> None:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(settings.database_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS paper_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                closed_at TEXT,
                coin_id TEXT NOT NULL,
                status TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                entry_zone TEXT NOT NULL,
                entry_price REAL NOT NULL,
                latest_price REAL NOT NULL,
                stop_loss REAL NOT NULL,
                take_profit REAL NOT NULL,
                invalidation_point REAL NOT NULL,
                quantity REAL NOT NULL,
                max_dollar_risk REAL NOT NULL,
                realized_pnl REAL NOT NULL DEFAULT 0,
                unrealized_pnl REAL NOT NULL DEFAULT 0,
                close_reason TEXT NOT NULL DEFAULT '',
                thesis TEXT NOT NULL,
                counter_thesis TEXT NOT NULL,
                exit_warning TEXT NOT NULL,
                snapshot_json TEXT NOT NULL
            )
            """
        )


def open_paper_trade(analysis: dict) -> int:
    """Save a Trade decision as a paper position."""

    if analysis.get("decision") != "Trade":
        raise ValueError("Only Trade decisions can be tracked as paper positions.")
    required = ["stop_loss", "take_profit", "invalidation_point", "position_size"]
    if any(analysis.get(key) in (None, 0) for key in required):
        raise ValueError("Paper trade requires stop, target, invalidation, and position size.")

    initialize_paper_trades()
    entry_price = float(analysis["current_price"])
    quantity = float(analysis["position_size"])
    with sqlite3.connect(settings.database_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO paper_positions (
                coin_id, status, recommendation, entry_zone, entry_price, latest_price,
                stop_loss, take_profit, invalidation_point, quantity, max_dollar_risk,
                unrealized_pnl, thesis, counter_thesis, exit_warning, snapshot_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                analysis["coin_id"],
                "Active",
                analysis["recommendation"],
                analysis["entry_zone"],
                entry_price,
                entry_price,
                float(analysis["stop_loss"]),
                float(analysis["take_profit"]),
                float(analysis["invalidation_point"]),
                quantity,
                float(analysis["max_dollar_risk"]),
                0.0,
                analysis.get("reason", ""),
                analysis.get("counter_thesis", ""),
                analysis.get("exit_warning", ""),
                json.dumps(analysis),
            ),
        )
        return int(cursor.lastrowid)


def list_paper_positions(active_only: bool = False, limit: int = 100) -> pd.DataFrame:
    initialize_paper_trades()
    where = "WHERE status = 'Active'" if active_only else ""
    with sqlite3.connect(settings.database_path) as connection:
        return pd.read_sql_query(
            f"""
            SELECT id, created_at, updated_at, closed_at, coin_id, status,
                   entry_price, latest_price, stop_loss, take_profit,
                   invalidation_point, quantity, max_dollar_risk,
                   unrealized_pnl, realized_pnl, close_reason,
                   thesis, counter_thesis, exit_warning
            FROM paper_positions
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            connection,
            params=(limit,),
        )


def close_paper_trade(position_id: int, reason: str = "Closed manually") -> None:
    initialize_paper_trades()
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(settings.database_path) as connection:
        row = connection.execute(
            "SELECT unrealized_pnl FROM paper_positions WHERE id = ?",
            (position_id,),
        ).fetchone()
        if not row:
            raise ValueError("Paper position not found.")
        connection.execute(
            """
            UPDATE paper_positions
            SET status = 'Closed Manually',
                realized_pnl = ?,
                closed_at = ?,
                updated_at = ?,
                close_reason = ?
            WHERE id = ?
            """,
            (float(row[0]), now, now, reason, position_id),
        )


def refresh_paper_positions() -> dict[str, str]:
    """Refresh active positions with latest public candle close."""

    initialize_paper_trades()
    messages: dict[str, str] = {}
    now = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(settings.database_path) as connection:
        rows = connection.execute(
            """
            SELECT id, coin_id, entry_price, stop_loss, take_profit,
                   invalidation_point, quantity
            FROM paper_positions
            WHERE status = 'Active'
            """
        ).fetchall()

        for row in rows:
            position_id, coin_id, entry_price, stop_loss, take_profit, invalidation_point, quantity = row
            try:
                market_data = fetch_market_data(coin_id)
                latest_price = float(market_data.dropna().iloc[-1]["close"])
            except Exception as error:
                messages[str(position_id)] = f"{coin_id}: could not refresh price ({error})"
                continue

            unrealized_pnl = (latest_price - float(entry_price)) * float(quantity)
            status = "Active"
            close_reason = ""
            realized_pnl = 0.0
            closed_at = None

            if latest_price <= float(stop_loss):
                status = "Stopped"
                close_reason = "Stop-loss touched in paper tracking."
                realized_pnl = unrealized_pnl
                closed_at = now
            elif latest_price <= float(invalidation_point):
                status = "Invalidated"
                close_reason = "Invalidation level touched in paper tracking."
                realized_pnl = unrealized_pnl
                closed_at = now
            elif latest_price >= float(take_profit):
                status = "Target Hit"
                close_reason = "Take-profit touched in paper tracking."
                realized_pnl = unrealized_pnl
                closed_at = now

            connection.execute(
                """
                UPDATE paper_positions
                SET latest_price = ?,
                    unrealized_pnl = ?,
                    realized_pnl = ?,
                    status = ?,
                    close_reason = ?,
                    closed_at = COALESCE(?, closed_at),
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    latest_price,
                    unrealized_pnl,
                    realized_pnl,
                    status,
                    close_reason,
                    closed_at,
                    now,
                    position_id,
                ),
            )
            messages[str(position_id)] = f"{coin_id}: {status} at ${latest_price:,.6g}"

    return messages
