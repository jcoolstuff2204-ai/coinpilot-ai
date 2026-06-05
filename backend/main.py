"""FastAPI backend for CoinPilot AI.

This module exposes API endpoints for the Streamlit dashboard. It only
returns decision-support analysis. It does not contain exchange order logic.
"""

from fastapi import FastAPI, HTTPException

from src.analysis_service import analyze_coin, ask_agent, find_coins, scan_coins, scan_market
from src.journal import recent_entries
from src.models import (
    AnalysisRequest,
    AnalysisResponse,
    AssistantRequest,
    AssistantResponse,
    CoinSearchResult,
    MarketScanRequest,
    ScanRequest,
    ScanResponse,
)


app = FastAPI(title="CoinPilot AI API")


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalysisResponse)
def analyze(request: AnalysisRequest) -> AnalysisResponse:
    try:
        return analyze_coin(request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        message = str(error)
        status_code = 429 if "rate limit" in message.lower() else 503
        raise HTTPException(status_code=status_code, detail=message) from error


@app.post("/scan", response_model=ScanResponse)
def scan(request: ScanRequest) -> ScanResponse:
    result = scan_coins(request)
    if not result.results and result.errors:
        raise HTTPException(status_code=400, detail=result.errors)
    return result


@app.post("/scan/market", response_model=ScanResponse)
def market_scan(request: MarketScanRequest) -> ScanResponse:
    try:
        return scan_market(request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        message = str(error)
        status_code = 429 if "rate limit" in message.lower() else 503
        raise HTTPException(status_code=status_code, detail=message) from error


@app.post("/agent/chat", response_model=AssistantResponse)
def agent_chat(request: AssistantRequest) -> AssistantResponse:
    return ask_agent(request)


@app.get("/coins/search", response_model=list[CoinSearchResult])
def coin_search(q: str) -> list[CoinSearchResult]:
    try:
        return find_coins(q)
    except RuntimeError as error:
        message = str(error)
        status_code = 429 if "rate limit" in message.lower() else 503
        raise HTTPException(status_code=status_code, detail=message) from error


@app.get("/journal")
def journal(limit: int = 25) -> list[dict]:
    return recent_entries(limit=limit).to_dict(orient="records")
