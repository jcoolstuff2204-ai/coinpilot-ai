"""Public market data client.

CoinPilot reads public market data only. This module has no exchange account,
API secret, or order execution logic.

Provider strategy:
- Binance.US candles first for major USD/USDT pairs because it is efficient for indicators.
- CoinGecko for broad market discovery and fallback.
- Local JSON cache to reduce repeated API calls and avoid rate limits.
"""

from __future__ import annotations

import hashlib
import json
import time
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
UNIVERSE_CACHE_SECONDS = 45 * 60
MARKET_CACHE_SECONDS = 10 * 60
STALE_MARKET_SECONDS = 6 * 60 * 60

BINANCE_EXCLUDED_BASES = {
    "USDT", "USDC", "FDUSD", "TUSD", "BUSD", "DAI", "USDP", "EUR", "TRY",
    "BRL", "AUD", "GBP", "PAXG", "WBTC", "USDE",
}
BINANCE_EXCLUDED_KEYWORDS = ("UP", "DOWN", "BULL", "BEAR")


def normalize_coin_id(coin_id: str) -> str:
    cleaned = coin_id.strip().lower()
    if cleaned.startswith("binance:"):
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


def read_stale_cache(namespace: str, key: str, max_age_seconds: int) -> dict | list | None:
    return read_cache(namespace, key, max_age_seconds)


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
            stale = read_stale_cache(namespace, key, stale_ttl)
            if stale is not None:
                return stale
        raise
    except RequestException:
        if stale_ttl:
            stale = read_stale_cache(namespace, key, stale_ttl)
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
    if cleaned.startswith("binance:"):
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
    """Fetch scanner candidates from exchange-listed pairs.

    Automatic market scans avoid CoinGecko per-coin history calls because those
    quickly hit rate limits. CoinGecko stays available for manual single-coin
    lookup, but Market Radar uses Binance USDT pairs for tradable candidates.
    """
    return fetch_binance_universe(limit=limit, rank_start=rank_start)



def binance_base_urls() -> list[str]:
    urls = [settings.binance_global_base_url, settings.binance_base_url, "https://api.binance.com/api/v3"]
    unique: list[str] = []
    for url in urls:
        if url and url not in unique:
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
        tickers = fetch_binance_json("/ticker/24hr", {}, 20, "binance_tickers", 3 * 60, 60 * 60)
    except HTTPError as error:
        if error.response is not None and error.response.status_code == 429:
            raise RuntimeError("Binance ticker rate limit reached.") from error
        raise RuntimeError("Binance could not return ticker data.") from error
    except RequestException as error:
        raise RuntimeError("Could not connect to Binance ticker data.") from error

    candidates: list[dict] = []
    for ticker in tickers:
        symbol = ticker.get("symbol", "")
        if not symbol.endswith("USDT"):
            continue
        base = symbol[:-4]
        if base in BINANCE_EXCLUDED_BASES:
            continue
        if any(base.endswith(keyword) for keyword in BINANCE_EXCLUDED_KEYWORDS):
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


def fetch_coingecko_market_universe(limit: int = 50, currency: str = "usd", rank_start: int = 1) -> list[dict]:
    per_page = 250
    rank_start = max(1, rank_start)
    limit = max(1, min(limit, 250))
    rank_end = rank_start + limit - 1
    start_page = ((rank_start - 1) // per_page) + 1
    end_page = ((rank_end - 1) // per_page) + 1

    markets: list[dict] = []
    url = f"{settings.coingecko_base_url}/coins/markets"

    try:
        for page in range(start_page, end_page + 1):
            params = {
                "vs_currency": currency,
                "order": "market_cap_desc",
                "per_page": per_page,
                "page": page,
                "sparkline": "false",
                "price_change_percentage": "24h,7d",
            }
            markets.extend(
                get_json(url, params, 20, "market_universe", UNIVERSE_CACHE_SECONDS, UNIVERSE_CACHE_SECONDS * 24)
            )
    except HTTPError as error:
        if error.response is not None and error.response.status_code == 429:
            raise RuntimeError("CoinGecko market-list rate limit reached. Try Binance mode again soon.") from error
        raise RuntimeError("CoinGecko could not return the market list. Please try again shortly.") from error
    except RequestException as error:
        raise RuntimeError("Could not connect to CoinGecko. Check your internet connection and try again.") from error

    if not markets:
        raise ValueError("CoinGecko returned no market list data.")

    segment = [
        item
        for item in markets
        if rank_start <= int(item.get("market_cap_rank") or 999999) <= rank_end
    ]
    return segment[:limit]

def fetch_market_data(coin_id: str, days: int = 120, currency: str = "usd") -> pd.DataFrame:
    coin = normalize_coin_id(coin_id)

    if coin.startswith("binance:"):
        return fetch_binance_symbol_market_data(coin.removeprefix("binance:"), days=days)

    if currency.lower() == "usd":
        try:
            return fetch_binance_market_data(coin, days=days)
        except ValueError:
            pass
        except RuntimeError:
            pass

    return fetch_coingecko_market_data(coin, days=days, currency=currency)


def fetch_binance_market_data(coin_id: str, days: int = 120) -> pd.DataFrame:
    symbol = BINANCE_SYMBOLS.get(coin_id)
    if not symbol:
        raise ValueError(f"No Binance candle mapping for '{coin_id}'.")
    return fetch_binance_symbol_market_data(symbol, days=days)


def fetch_binance_symbol_market_data(symbol: str, days: int = 120) -> pd.DataFrame:
    symbol = symbol.upper()
    params = {"symbol": symbol, "interval": "1d", "limit": max(60, min(days, 1000))}
    try:
        candles = fetch_binance_json("/klines", params, 15, "binance_klines", MARKET_CACHE_SECONDS, STALE_MARKET_SECONDS)
    except HTTPError as error:
        if error.response is not None and error.response.status_code == 429:
            raise RuntimeError("Binance market-data rate limit reached.") from error
        raise RuntimeError("Binance could not return candle data.") from error
    except RequestException as error:
        raise RuntimeError("Could not connect to Binance market data.") from error

    if not candles:
        raise ValueError(f"No Binance candle data found for '{coin_id}'.")

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
    frame = frame[["open_time", "close", "volume"]].copy()
    frame["timestamp"] = pd.to_datetime(frame["open_time"], unit="ms")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce")
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
