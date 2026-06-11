"""SQLite trade journal for saved analyses."""

import json
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
                explanation TEXT NOT NULL,
                behavioral_state TEXT NOT NULL DEFAULT '',
                opportunity_score INTEGER NOT NULL DEFAULT 0,
                risk_score INTEGER NOT NULL DEFAULT 0,
                manipulation_risk_score INTEGER NOT NULL DEFAULT 0,
                counter_thesis TEXT NOT NULL DEFAULT '',
                exit_warning TEXT NOT NULL DEFAULT '',
                components_json TEXT NOT NULL DEFAULT '[]',
                action_checklist_json TEXT NOT NULL DEFAULT '[]'
            )
            """
        )
        columns = {
            "recommendation": "TEXT NOT NULL DEFAULT ''",
            "market_bias": "TEXT NOT NULL DEFAULT ''",
            "behavioral_state": "TEXT NOT NULL DEFAULT ''",
            "opportunity_score": "INTEGER NOT NULL DEFAULT 0",
            "risk_score": "INTEGER NOT NULL DEFAULT 0",
            "manipulation_risk_score": "INTEGER NOT NULL DEFAULT 0",
            "counter_thesis": "TEXT NOT NULL DEFAULT ''",
            "exit_warning": "TEXT NOT NULL DEFAULT ''",
            "components_json": "TEXT NOT NULL DEFAULT '[]'",
            "action_checklist_json": "TEXT NOT NULL DEFAULT '[]'",
        }
        for column_name, column_type in columns.items():
            try:
                connection.execute(f"ALTER TABLE trade_journal ADD COLUMN {column_name} {column_type}")
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
                max_dollar_risk, reason, explanation, behavioral_state, opportunity_score,
                risk_score, manipulation_risk_score, counter_thesis, exit_warning,
                components_json, action_checklist_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                analysis.behavioral_state,
                analysis.opportunity_score,
                analysis.risk_score,
                analysis.manipulation_risk_score,
                analysis.counter_thesis,
                analysis.exit_warning,
                json.dumps([item.model_dump() for item in analysis.components]),
                json.dumps(analysis.action_checklist),
            ),
        )


def recent_entries(limit: int = 25) -> pd.DataFrame:
    initialize_journal()
    with sqlite3.connect(settings.database_path) as connection:
        return pd.read_sql_query(
            """
            SELECT created_at, coin_id, recommendation, decision, confidence,
                   opportunity_score, risk_score, manipulation_risk_score,
                   behavioral_state, current_price, risk_reward_ratio,
                   position_size, max_dollar_risk, reason
            FROM trade_journal
            ORDER BY id DESC
            LIMIT ?
            """,
            connection,
            params=(limit,),
        )
