"""Plain-English reasoning layer.

OpenAI is optional. When no API key is configured, CoinPilot returns a simple
local explanation so the MVP remains usable.
"""

from openai import OpenAI, OpenAIError

from src.config import settings
from src.models import AnalysisResponse


def fallback_explanation(analysis: AnalysisResponse) -> str:
    return (
        f"CoinPilot's decision is {analysis.decision}, with a {analysis.recommendation} recommendation. "
        f"The current price is ${analysis.current_price:,.2f}. "
        f"The 20-period average is ${analysis.ma_20:,.2f}, the 50-period average is "
        f"${analysis.ma_50:,.2f}, and RSI is {analysis.rsi:.1f}. "
        f"Volume is {analysis.volume_vs_average:.1f}% of its 20-period average. "
        f"{analysis.reason} "
        f"Behavior notes: {' '.join(analysis.key_levels[-3:])}"
    )


def explain_analysis(analysis: AnalysisResponse) -> str:
    if not settings.openai_api_key:
        return fallback_explanation(analysis)

    try:
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Explain a rule-based crypto trade analysis in beginner-friendly language. "
                        "Do not add new recommendations beyond the structured recommendation. "
                        "Do not claim certainty. Do not suggest exchange actions or automatic trading. "
                        "Consider investor psychology from the supplied notes: FOMO, panic selling, "
                        "crowded volume, hesitation near resistance, and whether waiting is wiser. "
                        "Remind the user this is not financial advice."
                    ),
                },
                {
                    "role": "user",
                    "content": analysis.model_dump_json(),
                },
            ],
            temperature=0.2,
            max_tokens=220,
        )
        return response.choices[0].message.content or fallback_explanation(analysis)
    except OpenAIError:
        return fallback_explanation(analysis)


def chat_with_agent(message: str, context: list[AnalysisResponse]) -> str:
    if not context:
        return (
            "Run a single-coin analysis or scanner first, then ask me about the result. "
            "I can compare setups, explain risk, and help you decide what to watch next."
        )

    context_summary = "\n".join(
        (
            f"{item.coin_id}: {item.recommendation}, decision={item.decision}, "
            f"confidence={item.confidence}, price={item.current_price:.6f}, "
            f"RSI={item.rsi:.1f}, volume_vs_avg={item.volume_vs_average:.1f}%, "
            f"reason={item.reason}"
        )
        for item in context
    )

    if not settings.openai_api_key:
        return _fallback_chat_reply(message, context)

    try:
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are CoinPilot AI, a crypto decision-support assistant for one user. "
                        "Use only the provided analysis context. You may suggest Buy Setup, Hold, "
                        "or Sell / Avoid based on the structured data, but you must never imply "
                        "automatic trading, exchange execution, leverage, or guaranteed profit. "
                        "Also consider investor psychology: FOMO, panic, crowded volume, hesitation "
                        "near resistance, and whether waiting is the disciplined decision. "
                        "Be concise, practical, and safety-first."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Analysis context:\n{context_summary}\n\nUser question:\n{message}",
                },
            ],
            temperature=0.2,
            max_tokens=260,
        )
        return response.choices[0].message.content or _fallback_chat_reply(message, context)
    except OpenAIError:
        return _fallback_chat_reply(message, context)


def _fallback_chat_reply(message: str, context: list[AnalysisResponse]) -> str:
    buy_setups = [item for item in context if item.recommendation == "Buy Setup"]
    avoid_setups = [item for item in context if item.recommendation == "Sell / Avoid"]
    hold_setups = [item for item in context if item.recommendation == "Hold"]

    if buy_setups:
        top = sorted(buy_setups, key=lambda item: (item.confidence, item.risk_reward_ratio or 0), reverse=True)[0]
        return (
            f"The strongest current setup is {top.coin_id.upper()} with {top.confidence}% confidence. "
            f"It still requires manual confirmation: entry {top.entry_zone}, stop-loss "
            f"${top.stop_loss:,.2f}, and take-profit ${top.take_profit:,.2f}. "
            "Only consider it if the risk fits your plan."
        )

    if avoid_setups:
        coins = ", ".join(item.coin_id.upper() for item in avoid_setups[:4])
        return (
            f"I do not see a safe buy setup right now. {coins} are marked Sell / Avoid, "
            "which means avoid new buys or review existing holdings manually."
        )

    if hold_setups:
        coins = ", ".join(item.coin_id.upper() for item in hold_setups[:4])
        return f"{coins} are currently Hold. The safer move is to wait for trend, RSI, and risk/reward to improve."

    return "I do not see enough context to make a useful suggestion yet. Run the scanner first."
