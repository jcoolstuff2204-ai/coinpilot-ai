"""Risk calculations and hard guardrails.

The risk manager sizes a paper position only. It caps risk by the user's max
risk setting and caps notional value to avoid leverage.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PositionPlan:
    position_size: float
    max_dollar_risk: float
    risk_per_coin: float
    position_value: float


def calculate_position_size(
    account_size: float,
    risk_percent: float,
    entry_price: float,
    stop_loss: float,
) -> PositionPlan:
    if account_size <= 0:
        raise ValueError("Account size must be greater than 0.")
    if risk_percent <= 0 or risk_percent > 5:
        raise ValueError("Risk percent must be greater than 0 and no more than 5.")
    if entry_price <= 0:
        raise ValueError("Entry price must be greater than 0.")
    if stop_loss <= 0:
        raise ValueError("A stop-loss is required and must be greater than 0.")

    risk_per_coin = abs(entry_price - stop_loss)
    if risk_per_coin == 0:
        raise ValueError("Entry price and stop-loss cannot be the same.")

    max_dollar_risk = account_size * (risk_percent / 100)
    risk_based_size = max_dollar_risk / risk_per_coin
    cash_based_size = account_size / entry_price
    position_size = min(risk_based_size, cash_based_size)

    return PositionPlan(
        position_size=position_size,
        max_dollar_risk=max_dollar_risk,
        risk_per_coin=risk_per_coin,
        position_value=position_size * entry_price,
    )


def calculate_risk_reward(entry_price: float, stop_loss: float, take_profit: float) -> float:
    risk = abs(entry_price - stop_loss)
    reward = abs(take_profit - entry_price)
    if risk == 0:
        raise ValueError("Risk cannot be zero.")
    return reward / risk
