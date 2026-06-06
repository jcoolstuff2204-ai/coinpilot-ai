"""Shared request and response models for the backend and dashboard."""

from pydantic import BaseModel, Field


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
