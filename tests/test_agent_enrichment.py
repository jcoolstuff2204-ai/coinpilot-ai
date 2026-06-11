from src.models import AnalysisResponse


def build_response(**overrides):
    data = {
        "coin_id": "test",
        "decision": "Trade",
        "recommendation": "Buy Setup",
        "market_bias": "Bullish",
        "trend_status": "Bullish",
        "reason": "Trend and risk rules passed.",
        "confidence": 75,
        "current_price": 100.0,
        "ma_20": 95.0,
        "ma_50": 90.0,
        "rsi": 55.0,
        "volume_change": 12.0,
        "volume_vs_average": 120.0,
        "support": 92.0,
        "resistance": 115.0,
        "key_levels": [],
        "entry_zone": "$99.50 - $100.50",
        "stop_loss": 94.0,
        "take_profit": 115.0,
        "risk_reward_ratio": 2.5,
        "position_size": 1.5,
        "max_dollar_risk": 10.0,
        "invalidation_point": 94.0,
        "explanation": "",
        "safety_rules": [],
    }
    data.update(overrides)
    return AnalysisResponse(**data)


def test_buy_setup_gets_agent_scores_and_checklist():
    item = build_response()

    assert item.opportunity_score > item.risk_score
    assert item.behavioral_state == "Momentum Ignition"
    assert item.counter_thesis
    assert item.exit_warning
    assert item.components
    assert item.action_checklist


def test_no_stop_increases_risk_and_blocks_trade_context():
    item = build_response(
        decision="No Trade",
        recommendation="Hold",
        stop_loss=None,
        take_profit=None,
        risk_reward_ratio=None,
        invalidation_point=None,
    )

    assert item.risk_score >= 45
    assert item.behavioral_state in {"Developing Accumulation", "Unclear / Wait"}
