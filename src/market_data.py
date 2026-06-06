"""Public market data client.

CoinPilot reads public market data only. This module has no exchange account,
API secret, or order execution logic.

Automatic Market Radar scans use exchange-listed USDT pairs:
1. KuCoin all tickers + candles
2. Binance all tickers + candles fallback

CoinGecko is kept only for manual coin search and fallback single-coin history.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests
from requests import HTTPError, RequestException

from src.config import settings


COIN_ALIASES = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "sol": "solana",
    "avax": "avalanche-2",
    "bnb": "binancecoin",
    "doge": "dogecoin",
    "dot": "polkadot",
    "link": "chainlink",
    "matic": "polygon",
    "pol": "polygon-ecosystem-token",
    "pepe": "pepe",
    "shib": "shiba-inu",
    "xrp": "ripple",
    "ada": "cardano",
    "ltc": "litecoin",
    "bch": "bitcoin-cash",
    "xlm": "stellar",
    "uni": "uniswap",
    "near": "near",
    "apt": "aptos",
    "arb": "arbitrum",
    "op": "optimism",
    "atom": "cosmos",
    "fil": "filecoin",
    "etc": "ethereum-classic",
}

BINANCE_SYMBOLS = {
    "bitcoin": "BTCUSDT",
    "ethereum": "ETHUSDT",
    "solana": "SOLUSDT",
    "avalanche-2": "AVAXUSDT",
    "binancecoin": "BNBUSDT",
    "dogecoin": "DOGEUSDT",
    "polkadot": "DOTUSDT",
    "chainlink": "LINKUSDT",
    "ripple": "XRPUSDT",
    "cardano": "ADAUSDT",
    "litecoin": "LTCUSDT",
    "bitcoin-cash": "BCHUSDT",
    "stellar": "XLMUSDT",
    "uniswap": "UNIUSDT",
    "near": "NEARUSDT",
    "aptos": "APTUSDT",
    "arbitrum": "ARBUSDT",
    "optimism": "OPUSDT",
    "cosmos": "ATOMUSDT",
    "filecoin": "FILUSDT",
    "ethereum-classic": "ETCUSDT",
}

SEARCH_CACHE_SECONDS = 60 * 60
UNIVERSE_CACHE_SECONDS = 5 * 60
MARKET_CACHE_SECONDS = 10 * 60
STALE_MARKET_SECONDS = 6 * 60 * 60

EXCLUDED_BASES = {
    "USDT", "USDC", "FDUSD", "TUSD", "BUSD", "DAI", "USDP", "EUR", "TRY",
    "BRL", "AUD", "GBP", "PAXG", "WBTC", "USDE", "USTC",
}
EXCLUDED_KEYWORDS = ("UP", "DOWN", "BULL", "BEAR", "3L", "3S")


def normalize_coin_id(coin_id: str) -> str:
    cleaned = coin_id.strip().lower()
    if cleaned.startswith(("kucoin:", "binance:")):
        return cleaned
    if cleaned.endswith("usdt") and cleaned.replace("usdt", "").isalnum():
        return f"binance:{cleaned.upper()}"
    return COIN_ALIASES.get(cleaned, cleaned)


def cache_file(namespace: str, key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return settings.cache_path / namespace / f"{digest}.json"


def read_cache(namespace: str, key: str, max_age_seconds: int) -> dict | list | None:
    path = cache_file(namespace, key)
    if not path.exists():
        return None
    try:
        wrapper = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if time.time() - wrapper.get("saved_at", 0) > max_age_seconds:
        return None
    return wrapper.get("payload")


def write_cache(namespace: str, key: str, payload: dict | list) -> None:
    path = cache_file(namespace, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"saved_at": time.time(), "payload": payload}))


def get_json(url: str, params: dict, timeout: int, namespace: str, ttl: int, stale_ttl: int | None = None):
    key = json.dumps({"url": url, "params": params}, sort_keys=True)
    cached = read_cache(namespace, key, ttl)
    if cached is not None:
        return cached

    try:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        write_cache(namespace, key, payload)
        return payload
    except HTTPError as error:
        if error.response is not None and error.response.status_code == 429 and stale_ttl:
            stale = read_cache(namespace, key, stale_ttl)
            if stale is not None:
                return stale
        raise
    except RequestException:
        if stale_ttl:
            stale = read_cache(namespace, key, stale_ttl)
            if stale is not None:
                return stale
        raise


def search_coins(query: str, limit: int = 8) -> list[dict]:
    cleaned = query.strip().lower()
    if not cleaned:
        return []

    url = f"{settings.coingecko_base_url}/search"
    params = {"query": cleaned}
    try:
        payload = get_json(url, params, 15, "coingecko_search", SEARCH_CACHE_SECONDS, SEARCH_CACHE_SECONDS * 24)
    except HTTPError as error:
        if error.response is not None and error.response.status_code == 429:
            raise RuntimeError("CoinGecko search rate limit reached. Please wait a minute and try again.") from error
        raise RuntimeError("CoinGecko search returned an error. Please try again shortly.") from error
    except RequestException as error:
        raise RuntimeError("Could not connect to CoinGecko search. Check your internet connection and try again.") from error

    coins = payload.get("coins", [])
    return [
        {
            "id": coin.get("id", ""),
            "symbol": coin.get("symbol", ""),
            "name": coin.get("name", ""),
            "market_cap_rank": coin.get("market_cap_rank"),
        }
        for coin in coins[:limit]
        if coin.get("id")
    ]


def resolve_coin_id(query: str) -> str:
    cleaned = normalize_coin_id(query)
    if cleaned.startswith(("kucoin:", "binance:")):
        return cleaned
    if cleaned != query.strip().lower():
        return cleaned

    results = search_coins(cleaned, limit=10)
    if not results:
        return cleaned

    exact_id = next((coin for coin in results if coin["id"].lower() == cleaned), None)
    if exact_id:
        return exact_id["id"]

    exact_symbol = next((coin for coin in results if coin["symbol"].lower() == cleaned), None)
    if exact_symbol:
        return exact_symbol["id"]

    exact_name = next((coin for coin in results if coin["name"].lower() == cleaned), None)
    if exact_name:
        return exact_name["id"]

    ranked = sorted(results, key=lambda coin: coin["market_cap_rank"] or 999999)
    return ranked[0]["id"]


def fetch_market_universe(limit: int = 50, currency: str = "usd", rank_start: int = 1) -> list[dict]:
    """Fetch automatic scanner candidates from exchange tickers only."""
    try:
        kucoin = fetch_kucoin_universe(limit=limit, rank_start=rank_start)
        if kucoin:
            return kucoin
    except RuntimeError:
        pass

    return fetch_binance_universe(limit=limit, rank_start=rank_start)


def valid_base_symbol(base: str) -> bool:
    if base in EXCLUDED_BASES:
        return False
    return not any(base.endswith(keyword) for keyword in EXCLUDED_KEYWORDS)


def fetch_kucoin_universe(limit: int = 50, rank_start: int = 1) -> list[dict]:
    url = f"{settings.kucoin_base_url.rstrip('/')}/api/v1/market/allTickers"
    try:
        payload = get_json(url, {}, 20, "kucoin_tickers", UNIVERSE_CACHE_SECONDS, 60 * 60)
    except (HTTPError, RequestException) as error:
        raise RuntimeError("KuCoin could not return ticker data.") from error

    tickers = payload.get("data", {}).get("ticker", [])
    candidates: list[dict] = []
    for ticker in tickers:
        symbol = ticker.get("symbol", "")
        if not symbol.endswith("-USDT") or "-" not in symbol:
            continue
        base = symbol.split("-", 1)[0]
        if not valid_base_symbol(base):
            continue
        try:
            quote_volume = float(ticker.get("volValue") or 0)
            price_change = float(ticker.get("changeRate") or 0) * 100
        except (TypeError, ValueError):
            continue
        if quote_volume <= 0:
            continue
        candidates.append(
            {
                "id": f"kucoin:{symbol}",
                "symbol": base.lower(),
                "name": base,
                "market_cap_rank": 0,
                "total_volume": quote_volume,
                "price_change_percentage_24h": price_change,
            }
        )

    candidates.sort(key=lambda item: (item["total_volume"], abs(item["price_change_percentage_24h"])), reverse=True)
    for index, item in enumerate(candidates, start=1):
        item["market_cap_rank"] = index

    rank_start = max(1, rank_start)
    rank_end = rank_start + max(1, min(limit, 250)) - 1
    return [item for item in candidates if rank_start <= item["market_cap_rank"] <= rank_end][:limit]


def binance_base_urls() -> list[str]:
    urls = [settings.binance_global_base_url, settings.binance_base_url, "https://api.binance.com/api/v3"]
    unique: list[str] = []
    for url in urls:
        if url and url.rstrip("/") not in unique:
            unique.append(url.rstrip("/"))
    return unique


def fetch_binance_json(path: str, params: dict, timeout: int, namespace: str, ttl: int, stale_ttl: int | None = None):
    last_error: Exception | None = None
    for base_url in binance_base_urls():
        try:
            return get_json(f"{base_url}{path}", params, timeout, namespace, ttl, stale_ttl)
        except (HTTPError, RequestException, RuntimeError) as error:
            last_error = error
            continue
    if last_error:
        raise last_error
    raise RuntimeError("No Binance market data endpoint is configured.")


def fetch_binance_universe(limit: int = 50, rank_start: int = 1) -> list[dict]:
    try:
        tickers = fetch_binance_json("/ticker/24hr", {}, 20, "binance_tickers", UNIVERSE_CACHE_SECONDS, 60 * 60)
    except (HTTPError, RequestException, RuntimeError) as error:
        raise RuntimeError("Binance could not return ticker data.") from error

    candidates: list[dict] = []
    for ticker in tickers:
        symbol = ticker.get("symbol", "")
        if not symbol.endswith("USDT"):
            continue
        base = symbol[:-4]
        if not valid_base_symbol(base):
            continue
        try:
            quote_volume = float(ticker.get("quoteVolume") or 0)
            price_change = float(ticker.get("priceChangePercent") or 0)
        except (TypeError, ValueError):
            continue
        if quote_volume <= 0:
            continue
        candidates.append(
            {
                "id": f"binance:{symbol}",
                "symbol": base.lower(),
                "name": base,
                "market_cap_rank": 0,
                "total_volume": quote_volume,
                "price_change_percentage_24h": price_change,
            }
        )

    candidates.sort(key=lambda item: (item["total_volume"], abs(item["price_change_percentage_24h"])), reverse=True)
    for index, item in enumerate(candidates, start=1):
        item["market_cap_rank"] = index

    rank_start = max(1, rank_start)
    rank_end = rank_start + max(1, min(limit, 250)) - 1
    return [item for item in candidates if rank_start <= item["market_cap_rank"] <= rank_end][:limit]


def fetch_market_data(coin_id: str, days: int = 120, currency: str = "usd") -> pd.DataFrame:
    coin = normalize_coin_id(coin_id)

    if coin.startswith("kucoin:"):
        return fetch_kucoin_market_data(coin.removeprefix("kucoin:"), days=days)
    if coin.startswith("binance:"):
        return fetch_binance_symbol_market_data(coin.removeprefix("binance:"), days=days)

    if currency.lower() == "usd":
        try:
            return fetch_binance_market_data(coin, days=days)
        except (ValueError, RuntimeError):
            pass

    return fetch_coingecko_market_data(coin, days=days, currency=currency)


def fetch_kucoin_market_data(symbol: str, days: int = 120) -> pd.DataFrame:
    end_at = int(datetime.now(timezone.utc).timestamp())
    start_at = int((datetime.now(timezone.utc) - timedelta(days=days + 5)).timestamp())
    url = f"{settings.kucoin_base_url.rstrip('/')}/api/v1/market/candles"
    params = {"symbol": symbol.upper(), "type": "1day", "startAt": start_at, "endAt": end_at}
    try:
        payload = get_json(url, params, 15, "kucoin_candles", MARKET_CACHE_SECONDS, STALE_MARKET_SECONDS)
    except (HTTPError, RequestException) as error:
        raise RuntimeError("KuCoin could not return candle data.") from error

    rows = payload.get("data", [])
    if not rows:
        raise ValueError(f"No KuCoin candle data found for '{symbol}'.")

    frame = pd.DataFrame(rows, columns=["timestamp", "open", "close", "high", "low", "volume", "turnover"])
    frame["timestamp"] = pd.to_datetime(pd.to_numeric(frame["timestamp"], errors="coerce"), unit="s")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame["volume"] = pd.to_numeric(frame["turnover"], errors="coerce")
    frame = frame[["timestamp", "close", "volume"]].dropna().sort_values("timestamp")
    if len(frame) < 60:
        raise ValueError("KuCoin returned too little history to calculate the required indicators.")
    return frame.tail(days)


def fetch_binance_market_data(coin_id: str, days: int = 120) -> pd.DataFrame:
    symbol = BINANCE_SYMBOLS.get(coin_id)
    if not symbol:
        raise ValueError(f"No Binance candle mapping for '{coin_id}'.")
    return fetch_binance_symbol_market_data(symbol, days=days)


def fetch_binance_symbol_market_data(symbol: str, days: int = 120) -> pd.DataFrame:
    params = {"symbol": symbol.upper(), "interval": "1d", "limit": max(60, min(days, 1000))}
    try:
        candles = fetch_binance_json("/klines", params, 15, "binance_klines", MARKET_CACHE_SECONDS, STALE_MARKET_SECONDS)
    except HTTPError as error:
        if error.response is not None and error.response.status_code == 429:
            raise RuntimeError("Binance market-data rate limit reached.") from error
        raise RuntimeError("Binance could not return candle data.") from error
    except RequestException as error:
        raise RuntimeError("Could not connect to Binance market data.") from error

    if not candles:
        raise ValueError(f"No Binance candle data found for '{symbol}'.")

    frame = pd.DataFrame(
        candles,
        columns=[
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_volume",
            "trade_count",
            "taker_buy_base_volume",
            "taker_buy_quote_volume",
            "ignore",
        ],
    )
    frame = frame[["open_time", "close", "quote_volume"]].copy()
    frame["timestamp"] = pd.to_datetime(frame["open_time"], unit="ms")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame["volume"] = pd.to_numeric(frame["quote_volume"], errors="coerce")
    frame = frame[["timestamp", "close", "volume"]].dropna()
    if len(frame) < 60:
        raise ValueError("Binance returned too little history to calculate the required indicators.")
    return frame


def fetch_coingecko_market_data(coin_id: str, days: int = 120, currency: str = "usd") -> pd.DataFrame:
    url = f"{settings.coingecko_base_url}/coins/{coin_id}/market_chart"
    params = {"vs_currency": currency, "days": days, "interval": "daily"}
    try:
        payload = get_json(url, params, 20, "coingecko_market_chart", MARKET_CACHE_SECONDS, STALE_MARKET_SECONDS)
    except HTTPError as error:
        if error.response is not None and error.response.status_code == 429:
            raise RuntimeError("CoinGecko rate limit reached. Please wait a minute and try again.") from error
        if error.response is not None and error.response.status_code == 404:
            raise ValueError(f"Coin '{coin_id}' was not found. Try BTC, ETH, SOL, or a CoinGecko id.") from error
        raise RuntimeError("CoinGecko returned an error. Please try again shortly.") from error
    except RequestException as error:
        raise RuntimeError("Could not connect to CoinGecko. Check your internet connection and try again.") from error

    prices = payload.get("prices", [])
    volumes = payload.get("total_volumes", [])
    if not prices or not volumes:
        raise ValueError(f"No usable market data found for '{coin_id}'. Try another coin or try again later.")

    price_frame = pd.DataFrame(prices, columns=["timestamp", "close"])
    volume_frame = pd.DataFrame(volumes, columns=["timestamp", "volume"])
    frame = price_frame.merge(volume_frame, on="timestamp", how="inner")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms")
    frame = frame.dropna()
    if len(frame) < 60:
        raise ValueError("CoinGecko returned too little history to calculate the required indicators.")
    return frame
