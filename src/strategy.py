"""Rule-based trading analysis.

This module decides Trade or No Trade before any AI explanation is created.
The AI layer can explain the result, but it cannot override these safety rules.
"""

import pandas as pd

from src.models import AnalysisResponse
from src.risk_manager import calculate_position_size, calculate_risk_reward


SAFETY_RULES = [
    "Never show a trade plan without a stop-loss.",
    "Never risk more than the user's max risk setting.",
    "If risk/reward is below 1:2, mark as No Trade.",
    "If trend is unclear, mark as No Trade.",
    "No leverage, no shorting, and no real order execution.",
]



def psychology_profile(
    current_price: float,
    ma_20: float,
    ma_50: float,
    rsi: float,
    volume_vs_average: float,
    resistance: float,
) -> tuple[str, list[str], int]:
    """Estimate FOMO, panic, and crowded behavior from market data."""
    notes: list[str] = []
    penalty = 0
    price_extension = (current_price - ma_20) / current_price
    trend_extension = abs(ma_20 - ma_50) / current_price

    if rsi >= 75 and volume_vs_average >= 130:
        notes.append("FOMO risk: RSI is very high while volume is crowded.")
        penalty += 20
    elif rsi >= 68:
        notes.append("Chase risk: buyers may be late after a strong move.")
        penalty += 10

    if price_extension > 0.06:
        notes.append("Price is stretched above the 20-period average.")
        penalty += 10

    if current_price >= resistance * 0.98:
        notes.append("Price is close to resistance, where buyers often hesitate.")
        penalty += 10

    if rsi <= 35 and volume_vs_average >= 120:
        notes.append("Panic risk: selling pressure is elevated.")
        penalty += 15

    if trend_extension < 0.01:
        notes.append("Investor conviction looks mixed because the trend is not separated.")
        penalty += 10

    if not notes:
        notes.append("Investor behavior looks balanced; no obvious FOMO or panic signal.")

    label = "Calm" if penalty < 10 else "Cautious" if penalty < 25 else "Crowded / Emotional"
    return label, notes, penalty


def build_trade_analysis(
    coin_id: str,
    indicator_data: pd.DataFrame,
    account_size: float,
    risk_percent: float,
    explanation: str = "",
) -> AnalysisResponse:
    usable = indicator_data.dropna()
    if usable.empty:
        raise ValueError("Not enough market data to calculate indicators.")

    latest = usable.iloc[-1]
    current_price = float(latest["close"])
    ma_20 = float(latest["ma_20"])
    ma_50 = float(latest["ma_50"])
    rsi = float(latest["rsi"])
    volume_change = float(latest["volume_change"])
    volume_vs_average = float(latest["volume_vs_average"])
    support = float(latest["support"])
    resistance = float(latest["resistance"])

    trend_gap = abs(ma_20 - ma_50) / current_price
    bullish_trend = current_price > ma_20 > ma_50 and trend_gap >= 0.01
    bearish_trend = current_price < ma_20 < ma_50 and trend_gap >= 0.01
    healthy_buy_rsi = 45 <= rsi <= 65
    healthy_volume = volume_vs_average >= 85
    near_resistance = current_price >= resistance * 0.985
    weak_rsi = rsi < 40
    overbought_rsi = rsi > 72
    key_levels = [
        f"Support near ${support:,.2f}",
        f"Resistance near ${resistance:,.2f}",
        f"20-period average at ${ma_20:,.2f}",
        f"50-period average at ${ma_50:,.2f}",
    ]
    behavior_label, behavior_notes, behavior_penalty = psychology_profile(
        current_price=current_price,
        ma_20=ma_20,
        ma_50=ma_50,
        rsi=rsi,
        volume_vs_average=volume_vs_average,
        resistance=resistance,
    )
    key_levels.extend([f"Psychology: {behavior_label}", *behavior_notes])

    no_trade_base = {
        "coin_id": coin_id,
        "decision": "No Trade",
        "current_price": current_price,
        "ma_20": ma_20,
        "ma_50": ma_50,
        "rsi": rsi,
        "volume_change": volume_change,
        "volume_vs_average": volume_vs_average,
        "support": support,
        "resistance": resistance,
        "key_levels": key_levels,
        "entry_zone": "None",
        "stop_loss": None,
        "take_profit": None,
        "risk_reward_ratio": None,
        "position_size": 0,
        "max_dollar_risk": account_size * (risk_percent / 100),
        "invalidation_point": None,
        "explanation": explanation,
        "safety_rules": SAFETY_RULES,
    }

    if bearish_trend or weak_rsi:
        return AnalysisResponse(
            **no_trade_base,
            recommendation="Sell / Avoid",
            market_bias="Bearish",
            trend_status="Bearish",
            confidence=70 if bearish_trend else 55,
            reason=(
                "Downside risk is elevated. If you already hold this coin, review whether it still fits "
                "your plan. CoinPilot does not place sell orders for you."
            ),
        )

    if not bullish_trend:
        return AnalysisResponse(
            **no_trade_base,
            recommendation="Hold",
            market_bias="Neutral",
            trend_status="Unclear",
            confidence=40,
            reason="Trend is unclear because price, 20 MA, and 50 MA are not aligned upward.",
        )

    entry_price = current_price
    entry_low = current_price * 0.995
    entry_high = current_price * 1.005
    stop_loss = min(support * 0.99, current_price * 0.96)
    take_profit = current_price + ((current_price - stop_loss) * 2.5)
    risk_reward_ratio = calculate_risk_reward(entry_price, stop_loss, take_profit)

    if risk_reward_ratio < 2:
        return AnalysisResponse(
            **no_trade_base,
            recommendation="Hold",
            market_bias="Bullish but unsafe",
            trend_status="Bullish",
            confidence=40,
            reason="Risk/reward is below the required 1:2 minimum.",
        )

    if not healthy_buy_rsi or overbought_rsi:
        return AnalysisResponse(
            **no_trade_base,
            recommendation="Hold",
            market_bias="Bullish but extended",
            trend_status="Bullish",
            confidence=50,
            reason="Trend is clear, but RSI is not in a beginner-friendly buy range.",
        )

    if not healthy_volume:
        return AnalysisResponse(
            **no_trade_base,
            recommendation="Hold",
            market_bias="Bullish but low volume",
            trend_status="Bullish",
            confidence=50,
            reason="Trend is clear, but volume is below its 20-period average.",
        )

    if near_resistance:
        return AnalysisResponse(
            **no_trade_base,
            recommendation="Hold",
            market_bias="Bullish but near resistance",
            trend_status="Bullish",
            confidence=55,
            reason="Price is too close to recent resistance, so the setup does not offer enough room.",
        )

    if behavior_penalty >= 25:
        return AnalysisResponse(
            **no_trade_base,
            recommendation="Hold",
            market_bias="Bullish but emotionally crowded",
            trend_status="Bullish",
            confidence=45,
            reason="The trend is positive, but investor behavior looks crowded or emotional. Avoid chasing.",
        )

    position_plan = calculate_position_size(
        account_size=account_size,
        risk_percent=risk_percent,
        entry_price=entry_price,
        stop_loss=stop_loss,
    )

    confidence = 75
    if volume_change > 10:
        confidence += 5
    if volume_vs_average > 120:
        confidence += 5
    if current_price < resistance * 0.95:
        confidence += 5

    confidence = max(50, confidence - behavior_penalty)

    return AnalysisResponse(
        coin_id=coin_id,
        decision="Trade",
        recommendation="Buy Setup",
        market_bias="Bullish",
        trend_status="Bullish",
        reason=(
            "Trend is clear, RSI is acceptable, risk/reward passes the safety rules, "
            f"and psychology is {behavior_label.lower()}."
        ),
        confidence=min(confidence, 90),
        current_price=current_price,
        ma_20=ma_20,
        ma_50=ma_50,
        rsi=rsi,
        volume_change=volume_change,
        volume_vs_average=volume_vs_average,
        support=support,
        resistance=resistance,
        key_levels=key_levels,
        entry_zone=f"${entry_low:,.2f} - ${entry_high:,.2f}",
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_reward_ratio=risk_reward_ratio,
        position_size=position_plan.position_size,
        max_dollar_risk=position_plan.max_dollar_risk,
        invalidation_point=stop_loss,
        explanation=explanation,
        safety_rules=SAFETY_RULES,
    )
