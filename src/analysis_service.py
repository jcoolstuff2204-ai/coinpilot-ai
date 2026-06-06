"""Application service that connects data, indicators, strategy, AI, and journal."""

from src.ai_agent import chat_with_agent, explain_analysis
from src.indicators import add_indicators
from src.journal import save_analysis
from src.market_data import fetch_market_data, fetch_market_universe, resolve_coin_id, search_coins
from src.models import (
    AnalysisRequest,
    AnalysisResponse,
    AssistantRequest,
    AssistantResponse,
    CoinAlert,
    CoinSearchResult,
    MarketScanRequest,
    ScanRequest,
    ScanResponse,
)
from src.strategy import build_trade_analysis


STABLECOIN_IDS = {
    "tether",
    "usd-coin",
    "dai",
    "first-digital-usd",
    "usds",
    "ethena-usde",
    "paypal-usd",
    "frax",
    "true-usd",
    "paxos-standard",
    "binance-usd",
}


def analyze_coin(request: AnalysisRequest) -> AnalysisResponse:
    coin_id = resolve_coin_id(request.coin_id)
    return analyze_resolved_coin(
        coin_id=coin_id,
        account_size=request.account_size,
        risk_percent=request.risk_percent,
    )


def analyze_resolved_coin(coin_id: str, account_size: float, risk_percent: float) -> AnalysisResponse:
    """Analyze a known CoinGecko/Binance id without calling search again."""
    market_data = fetch_market_data(coin_id)
    indicator_data = add_indicators(market_data)

    analysis = build_trade_analysis(
        coin_id=coin_id,
        indicator_data=indicator_data,
        account_size=account_size,
        risk_percent=risk_percent,
    )

    explanation = explain_analysis(analysis)
    final_analysis = analysis.model_copy(update={"explanation": explanation})
    save_analysis(final_analysis)
    return final_analysis


def scan_coins(request: ScanRequest) -> ScanResponse:
    results: list[AnalysisResponse] = []
    errors: dict[str, str] = {}

    for raw_coin_id in request.coin_ids:
        coin_id = raw_coin_id.strip()
        if not coin_id:
            continue

        try:
            resolved_coin_id = resolve_coin_id(coin_id)
            result = analyze_coin(
                AnalysisRequest(
                    coin_id=resolved_coin_id,
                    account_size=request.account_size,
                    risk_percent=request.risk_percent,
                )
            )
            results.append(result)
        except Exception as error:
            errors[coin_id] = str(error)

    results.sort(key=_scan_rank, reverse=True)
    return ScanResponse(
        results=results,
        errors=errors,
        alerts=_build_alerts(results),
        scanned_count=len(results),
        universe_count=len(request.coin_ids),
    )


def scan_market(request: MarketScanRequest) -> ScanResponse:
    universe = fetch_market_universe(limit=request.universe_limit, rank_start=request.rank_start)
    candidate_ids = [
        item["id"]
        for item in universe
        if item.get("id", "").startswith("binance:")
        and item.get("symbol", "").lower() not in {"usdt", "usdc", "dai"}
        and float(item.get("total_volume") or 0) >= request.min_volume_usd
    ]
    if len(candidate_ids) < request.deep_scan_limit:
        relaxed_floor = max(100000.0, request.min_volume_usd * 0.2)
        candidate_ids = [
            item["id"]
            for item in universe
            if item.get("id", "").startswith("binance:")
            and item.get("symbol", "").lower() not in {"usdt", "usdc", "dai"}
            and float(item.get("total_volume") or 0) >= relaxed_floor
        ]
    candidate_ids = candidate_ids[: request.deep_scan_limit]
    results: list[AnalysisResponse] = []
    errors: dict[str, str] = {}

    for coin_id in candidate_ids:
        try:
            results.append(
                analyze_resolved_coin(
                    coin_id=coin_id,
                    account_size=request.account_size,
                    risk_percent=request.risk_percent,
                )
            )
        except Exception as error:
            errors[coin_id] = str(error)

    results.sort(key=_scan_rank, reverse=True)
    top_results = results[: request.top_n]
    return ScanResponse(
        results=top_results,
        errors=errors,
        alerts=_build_alerts(top_results),
        scanned_count=len(results),
        universe_count=len(universe),
    )


def ask_agent(request: AssistantRequest) -> AssistantResponse:
    answer = chat_with_agent(request.message, request.context)
    return AssistantResponse(
        answer=answer,
        safety_note="Decision support only. CoinPilot does not place trades or connect to an exchange.",
    )


def find_coins(query: str) -> list[CoinSearchResult]:
    return [CoinSearchResult(**coin) for coin in search_coins(query, limit=8)]


def _scan_rank(analysis: AnalysisResponse) -> tuple[int, int, float]:
    recommendation_score = {
        "Buy Setup": 4,
        "Watch for Entry": 3,
        "Hold": 2,
        "Sell / Avoid": 1,
    }.get(analysis.recommendation, 0)
    trade_score = 1 if analysis.decision == "Trade" else 0
    risk_reward = analysis.risk_reward_ratio or 0
    return (recommendation_score, trade_score, analysis.confidence, risk_reward)


def _build_alerts(results: list[AnalysisResponse]) -> list[CoinAlert]:
    alerts: list[CoinAlert] = []
    for item in results:
        if item.recommendation == "Buy Setup":
            alerts.append(
                CoinAlert(
                    coin_id=item.coin_id,
                    severity="opportunity",
                    recommendation=item.recommendation,
                    confidence=item.confidence,
                    message=(
                        f"{item.coin_id.upper()} has a paper buy setup. Review entry {item.entry_zone}, "
                        f"stop-loss ${item.stop_loss:,.2f}, and risk/reward 1:{item.risk_reward_ratio:.2f}."
                    ),
                )
            )
        elif item.recommendation == "Watch for Entry":
            alerts.append(
                CoinAlert(
                    coin_id=item.coin_id,
                    severity="watch",
                    recommendation=item.recommendation,
                    confidence=item.confidence,
                    message=(
                        f"{item.coin_id.upper()} is a watch-for-entry candidate. "
                        f"{item.reason}"
                    ),
                )
            )
        elif item.recommendation == "Sell / Avoid":
            alerts.append(
                CoinAlert(
                    coin_id=item.coin_id,
                    severity="risk",
                    recommendation=item.recommendation,
                    confidence=item.confidence,
                    message=(
                        f"{item.coin_id.upper()} shows elevated downside risk. Avoid new buys or review "
                        "any existing holding manually."
                    ),
                )
            )
        elif item.confidence >= 55:
            alerts.append(
                CoinAlert(
                    coin_id=item.coin_id,
                    severity="watch",
                    recommendation=item.recommendation,
                    confidence=item.confidence,
                    message=f"{item.coin_id.upper()} is worth watching, but the safety rules do not permit a trade setup yet.",
                )
            )
    return alerts
