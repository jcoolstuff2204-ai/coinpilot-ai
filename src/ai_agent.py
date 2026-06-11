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
        f"Behavioral state: {analysis.behavioral_state}. "
        f"Opportunity score {analysis.opportunity_score}/100, risk score {analysis.risk_score}/100, "
        f"manipulation risk {analysis.manipulation_risk_score}/100. "
        f"The current price is ${analysis.current_price:,.2f}; MA20 is ${analysis.ma_20:,.2f}, "
        f"MA50 is ${analysis.ma_50:,.2f}, RSI is {analysis.rsi:.1f}, and volume is "
        f"{analysis.volume_vs_average:.1f}% of its 20-period average. {analysis.reason} "
        f"Counter-thesis: {analysis.counter_thesis}"
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
                        "Explain a deterministic crypto decision-support analysis in beginner-friendly language. "
                        "Use only the provided structured evidence. Do not invent prices, scores, entries, stops, "
                        "targets, or market conditions. Do not claim certainty. Do not suggest automatic trading, "
                        "exchange execution, leverage, or guaranteed profit. Emphasize behavioral state, "
                        "counter-thesis, risk, and what would invalidate the setup."
                    ),
                },
                {"role": "user", "content": analysis.model_dump_json()},
            ],
            temperature=0.2,
            max_tokens=280,
        )
        return response.choices[0].message.content or fallback_explanation(analysis)
    except OpenAIError:
        return fallback_explanation(analysis)


def chat_with_agent(message: str, context: list[AnalysisResponse]) -> str:
    if not context:
        return (
            "Run Market Radar or Coin Deep Dive first. Then I can compare setups, explain what to buy, "
            "watch, sell/avoid, and what would invalidate each idea."
        )

    context_summary = "\n".join(
        (
            f"{item.coin_id}: recommendation={item.recommendation}, decision={item.decision}, "
            f"confidence={item.confidence}, opportunity={item.opportunity_score}, risk={item.risk_score}, "
            f"manipulation={item.manipulation_risk_score}, behavioral_state={item.behavioral_state}, "
            f"price={item.current_price:.6f}, RSI={item.rsi:.1f}, volume_vs_avg={item.volume_vs_average:.1f}%, "
            f"reason={item.reason}, counter_thesis={item.counter_thesis}, exit_warning={item.exit_warning}"
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
                        "You are CoinPilot AI, a personal crypto decision-support agent. "
                        "Use only the supplied structured scan context. You may say which coins are Buy Setup, "
                        "Watch for Entry, Hold, or Sell / Avoid, but you must never imply automatic trading, "
                        "exchange execution, leverage, or guaranteed profit. Explain investor psychology, "
                        "counter-thesis, invalidation, and risk-first next steps. Be concise and practical."
                    ),
                },
                {"role": "user", "content": f"Analysis context:\n{context_summary}\n\nUser question:\n{message}"},
            ],
            temperature=0.2,
            max_tokens=340,
        )
        return response.choices[0].message.content or _fallback_chat_reply(message, context)
    except OpenAIError:
        return _fallback_chat_reply(message, context)


def _fallback_chat_reply(message: str, context: list[AnalysisResponse]) -> str:
    buy_setups = [item for item in context if item.recommendation == "Buy Setup"]
    watch_setups = [item for item in context if item.recommendation == "Watch for Entry"]
    avoid_setups = [item for item in context if item.recommendation == "Sell / Avoid"]

    if buy_setups:
        top = sorted(buy_setups, key=lambda item: (item.opportunity_score, item.confidence), reverse=True)[0]
        return (
            f"The strongest current setup is {top.coin_id.upper()} with opportunity {top.opportunity_score}/100 "
            f"and risk {top.risk_score}/100. Manual plan: entry {top.entry_zone}, stop-loss "
            f"${top.stop_loss:,.4f}, target ${top.take_profit:,.4f}. Counter-thesis: {top.counter_thesis}"
        )

    if watch_setups:
        top = sorted(watch_setups, key=lambda item: item.opportunity_score, reverse=True)[0]
        return (
            f"No clean buy setup yet. The best watch candidate is {top.coin_id.upper()} "
            f"({top.behavioral_state}). Wait for the safety rules to align before considering a manual trade."
        )

    if avoid_setups:
        coins = ", ".join(item.coin_id.upper() for item in avoid_setups[:4])
        return f"I do not see a safe buy setup right now. {coins} are marked Sell / Avoid. Protect capital and wait."

    return "I do not see enough quality evidence for a buy setup. Waiting is a valid decision."
