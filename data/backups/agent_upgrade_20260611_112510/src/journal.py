"""SQLite trade journal for saved analyses."""

import sqlite3

import pandas as pd

from src.config import settings
from src.models import AnalysisResponse


def initialize_journal() -> None:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(settings.database_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS trade_journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                coin_id TEXT NOT NULL,
                decision TEXT NOT NULL,
                recommendation TEXT NOT NULL DEFAULT '',
                market_bias TEXT NOT NULL DEFAULT '',
                confidence INTEGER NOT NULL,
                current_price REAL NOT NULL,
                entry_zone TEXT NOT NULL,
                stop_loss REAL,
                take_profit REAL,
                risk_reward_ratio REAL,
                position_size REAL NOT NULL,
                max_dollar_risk REAL NOT NULL,
                reason TEXT NOT NULL,
                explanation TEXT NOT NULL
            )
            """
        )
        for column_name in ["recommendation", "market_bias"]:
            try:
                connection.execute(f"ALTER TABLE trade_journal ADD COLUMN {column_name} TEXT NOT NULL DEFAULT ''")
            except sqlite3.OperationalError:
                pass


def save_analysis(analysis: AnalysisResponse) -> None:
    initialize_journal()
    with sqlite3.connect(settings.database_path) as connection:
        connection.execute(
            """
            INSERT INTO trade_journal (
                coin_id, decision, recommendation, market_bias, confidence, current_price, entry_zone,
                stop_loss, take_profit, risk_reward_ratio, position_size,
                max_dollar_risk, reason, explanation
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                analysis.coin_id,
                analysis.decision,
                analysis.recommendation,
                analysis.market_bias,
                analysis.confidence,
                analysis.current_price,
                analysis.entry_zone,
                analysis.stop_loss,
                analysis.take_profit,
                analysis.risk_reward_ratio,
                analysis.position_size,
                analysis.max_dollar_risk,
                analysis.reason,
                analysis.explanation,
            ),
        )


def recent_entries(limit: int = 25) -> pd.DataFrame:
    initialize_journal()
    with sqlite3.connect(settings.database_path) as connection:
        return pd.read_sql_query(
            """
            SELECT created_at, coin_id, decision, confidence, current_price,
                   recommendation, market_bias, risk_reward_ratio, position_size, max_dollar_risk, reason
            FROM trade_journal
            ORDER BY id DESC
            LIMIT ?
            """,
            connection,
            params=(limit,),
        )
