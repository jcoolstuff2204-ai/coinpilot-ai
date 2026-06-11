from pathlib import Path

from src import paper_trading


def test_open_and_list_paper_trade(tmp_path, monkeypatch):
    test_db = tmp_path / "coinpilot_test.db"
    monkeypatch.setattr(paper_trading.settings, "database_path", test_db)

    analysis = {
        "coin_id": "bitcoin",
        "decision": "Trade",
        "recommendation": "Buy Setup",
        "entry_zone": "$99.50 - $100.50",
        "current_price": 100.0,
        "stop_loss": 94.0,
        "take_profit": 115.0,
        "invalidation_point": 94.0,
        "position_size": 1.5,
        "max_dollar_risk": 10.0,
        "reason": "Test setup.",
        "counter_thesis": "Test counter.",
        "exit_warning": "Test exit.",
    }

    position_id = paper_trading.open_paper_trade(analysis)
    rows = paper_trading.list_paper_positions()

    assert position_id == 1
    assert len(rows) == 1
    assert rows.iloc[0]["status"] == "Active"
    assert rows.iloc[0]["coin_id"] == "bitcoin"
