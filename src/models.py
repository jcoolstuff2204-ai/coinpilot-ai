"""Shared request and response models for the backend and dashboard."""

from pydantic import BaseModel, Field, model_validator


class AnalysisRequest(BaseModel):
    coin_id: str = Field(..., min_length=1)
    account_size: float = Field(..., gt=0)
    risk_percent: float = Field(..., gt=0, le=5)


class ScanRequest(BaseModel):
    coin_ids: list[str] = Field(..., min_length=1, max_length=30)
    account_size: float = Field(..., gt=0)
    risk_percent: float = Field(..., gt=0, le=5)


class MarketScanRequest(BaseModel):
    account_size: float = Field(..., gt=0)
    risk_percent: float = Field(..., gt=0, le=5)
    universe_limit: int = Field(default=50, ge=10, le=250)
    deep_scan_limit: int = Field(default=25, ge=5, le=50)
    top_n: int = Field(default=10, ge=1, le=20)
    rank_start: int = Field(default=1, ge=1, le=2000)
    min_volume_usd: float = Field(default=1000000.0, ge=0)


class CoinSearchResult(BaseModel):
    id: str
    symbol: str
    name: str
    market_cap_rank: int | None = None


class AssistantRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    context: list["AnalysisResponse"] = Field(default_factory=list, max_length=12)


class SignalComponent(BaseModel):
    name: str
    value: str
    score: int
    note: str


class AnalysisResponse(BaseModel):
    coin_id: str
    decision: str
    recommendation: str
    market_bias: str
    trend_status: str
    reason: str
    confidence: int
    current_price: float
    ma_20: float
    ma_50: float
    rsi: float
    volume_change: float
    volume_vs_average: float
    support: float
    resistance: float
    key_levels: list[str]
    entry_zone: str
    stop_loss: float | None
    take_profit: float | None
    risk_reward_ratio: float | None
    position_size: float
    max_dollar_risk: float
    invalidation_point: float | None
    explanation: str
    safety_rules: list[str]

    # QuanTrade-style agent fields. They are deterministic enrichments derived
    # from the rule-based analysis, not invented by the LLM.
    strategy_version: str = "coinpilot-momentum-v2"
    data_source_status: str = "public market data"
    behavioral_state: str = ""
    opportunity_score: int = 0
    risk_score: int = 0
    manipulation_risk_score: int = 0
    counter_thesis: str = ""
    exit_warning: str = ""
    paper_trade_status: str = "manual_review_only"
    components: list[SignalComponent] = Field(default_factory=list)
    action_checklist: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def enrich_agent_fields(self) -> "AnalysisResponse":
        self.opportunity_score = self.opportunity_score or _opportunity_score(self)
        self.risk_score = self.risk_score or _risk_score(self)
        self.manipulation_risk_score = self.manipulation_risk_score or _manipulation_risk_score(self)
        self.behavioral_state = self.behavioral_state or _behavioral_state(self)
        self.counter_thesis = self.counter_thesis or _counter_thesis(self)
        self.exit_warning = self.exit_warning or _exit_warning(self)
        self.components = self.components or _components(self)
        self.action_checklist = self.action_checklist or _action_checklist(self)
        return self


class CoinAlert(BaseModel):
    coin_id: str
    severity: str
    recommendation: str
    confidence: int
    message: str


class ScanResponse(BaseModel):
    results: list[AnalysisResponse]
    errors: dict[str, str]
    alerts: list[CoinAlert]
    scanned_count: int = 0
    universe_count: int = 0


class AssistantResponse(BaseModel):
    answer: str
    safety_note: str


def _opportunity_score(item: AnalysisResponse) -> int:
    score = 0
    if item.current_price > item.ma_20:
        score += 20
    if item.ma_20 >= item.ma_50:
        score += 20
    if 42 <= item.rsi <= 68:
        score += 20
    elif 35 <= item.rsi <= 76:
        score += 10
    if item.volume_vs_average >= 100:
        score += 15
    if item.risk_reward_ratio and item.risk_reward_ratio >= 2:
        score += 15
    if item.decision == "Trade":
        score += 10
    return min(score, 100)


def _risk_score(item: AnalysisResponse) -> int:
    score = 20
    if item.rsi > 76:
        score += 25
    if item.rsi < 35:
        score += 25
    if item.current_price >= item.resistance * 0.995:
        score += 15
    if item.current_price < item.ma_20:
        score += 15
    if not item.stop_loss:
        score += 15
    if not item.risk_reward_ratio or item.risk_reward_ratio < 2:
        score += 10
    return min(score, 100)


def _manipulation_risk_score(item: AnalysisResponse) -> int:
    score = 10
    if item.volume_vs_average >= 160 and item.rsi >= 75:
        score += 35
    elif item.volume_vs_average >= 130:
        score += 15
    if item.current_price >= item.resistance * 0.995:
        score += 20
    if item.volume_change > 80:
        score += 20
    return min(score, 100)


def _behavioral_state(item: AnalysisResponse) -> str:
    if item.recommendation == "Buy Setup":
        return "Momentum Ignition"
    if item.recommendation == "Sell / Avoid":
        return "Breakdown / Distribution Risk"
    if item.rsi > 76 and item.volume_vs_average > 120:
        return "Crowded Continuation"
    if item.current_price > item.ma_20 and item.ma_20 >= item.ma_50:
        return "Developing Accumulation"
    return "Unclear / Wait"


def _counter_thesis(item: AnalysisResponse) -> str:
    if item.recommendation == "Buy Setup":
        return (
            "The setup weakens if price loses the 20-period average, volume fades, "
            "or price reaches resistance before you can enter with defined risk."
        )
    if item.recommendation == "Sell / Avoid":
        return "Avoiding is wrong only if buyers quickly reclaim MA20 with strong volume and a defined stop is available."
    return "The watch thesis improves only if trend, RSI, volume, and reward/risk align at the same time."


def _exit_warning(item: AnalysisResponse) -> str:
    if item.recommendation == "Buy Setup" and item.invalidation_point:
        return (
            f"Manual exit warning: review immediately if price loses ${item.ma_20:,.4f}, "
            f"RSI falls under 45, or price touches invalidation at ${item.invalidation_point:,.4f}."
        )
    if item.recommendation == "Sell / Avoid":
        return "Exit-risk warning: do not add new exposure; review any existing position manually."
    return "No active exit alert. Wait for a cleaner setup before acting."


def _components(item: AnalysisResponse) -> list[SignalComponent]:
    trend_score = 80 if item.current_price > item.ma_20 and item.ma_20 >= item.ma_50 else 35
    momentum_score = 80 if 42 <= item.rsi <= 68 else 45 if 35 <= item.rsi <= 76 else 20
    volume_score = min(100, max(0, int(item.volume_vs_average)))
    rr_score = 90 if item.risk_reward_ratio and item.risk_reward_ratio >= 2 else 25
    return [
        SignalComponent(name="Trend", value=item.trend_status, score=trend_score, note="Price relative to MA20 and MA50."),
        SignalComponent(name="Momentum", value=f"RSI {item.rsi:.1f}", score=momentum_score, note="Avoids weak and overheated readings."),
        SignalComponent(name="Volume", value=f"{item.volume_vs_average:.0f}% of average", score=volume_score, note="Checks participation behind the move."),
        SignalComponent(name="Risk Gate", value=f"1:{item.risk_reward_ratio:.2f}" if item.risk_reward_ratio else "N/A", score=rr_score, note="Requires stop-loss and 1:2+ reward/risk."),
    ]


def _action_checklist(item: AnalysisResponse) -> list[str]:
    if item.recommendation == "Buy Setup":
        return [
            f"Only consider a manual entry inside {item.entry_zone}.",
            f"Set the stop-loss first: ${item.stop_loss:,.4f}.",
            f"First take-profit area: ${item.take_profit:,.4f}.",
            "Skip the setup if price runs beyond the entry zone before you act.",
        ]
    if item.recommendation == "Sell / Avoid":
        return [
            "Do not open a new buy.",
            "If already holding, review whether the coin still fits your plan.",
            "Wait for price to reclaim MA20 with healthier RSI and volume.",
        ]
    return [
        "Do not chase.",
        "Wait for trend, momentum, volume, and 1:2 reward/risk to align.",
        "Run another scan later or set an alert.",
    ]
