"""Public market data client.

CoinPilot uses CoinGecko public endpoints only. There is no exchange account,
API secret, or order execution in this module.
"""

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
    "pepe": "pepe",
    "shib": "shiba-inu",
    "xrp": "ripple",
}


def normalize_coin_id(coin_id: str) -> str:
    cleaned = coin_id.strip().lower()
    return COIN_ALIASES.get(cleaned, cleaned)


def search_coins(query: str, limit: int = 8) -> list[dict]:
    cleaned = query.strip().lower()
    if not cleaned:
        return []

    url = f"{settings.coingecko_base_url}/search"
    try:
        response = requests.get(url, params={"query": cleaned}, timeout=15)
        response.raise_for_status()
    except HTTPError as error:
        if error.response is not None and error.response.status_code == 429:
            raise RuntimeError("CoinGecko rate limit reached. Please wait a minute and try again.") from error
        raise RuntimeError("CoinGecko search returned an error. Please try again shortly.") from error
    except RequestException as error:
        raise RuntimeError("Could not connect to CoinGecko search. Check your internet connection and try again.") from error

    coins = response.json().get("coins", [])
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


def fetch_market_universe(limit: int = 50, currency: str = "usd") -> list[dict]:
    url = f"{settings.coingecko_base_url}/coins/markets"
    per_page = max(1, min(limit, 250))
    try:
        response = requests.get(
            url,
            params={
                "vs_currency": currency,
                "order": "market_cap_desc",
                "per_page": per_page,
                "page": 1,
                "sparkline": "false",
                "price_change_percentage": "24h,7d",
            },
            timeout=20,
        )
        response.raise_for_status()
    except HTTPError as error:
        if error.response is not None and error.response.status_code == 429:
            raise RuntimeError("CoinGecko rate limit reached. Please wait a minute and try again.") from error
        raise RuntimeError("CoinGecko could not return the market list. Please try again shortly.") from error
    except RequestException as error:
        raise RuntimeError("Could not connect to CoinGecko. Check your internet connection and try again.") from error

    markets = response.json()
    if not markets:
        raise ValueError("CoinGecko returned no market list data.")
    return markets


def fetch_market_data(coin_id: str, days: int = 120, currency: str = "usd") -> pd.DataFrame:
    coin = normalize_coin_id(coin_id)
    url = f"{settings.coingecko_base_url}/coins/{coin}/market_chart"
    try:
        response = requests.get(
            url,
            params={"vs_currency": currency, "days": days, "interval": "daily"},
            timeout=20,
        )
        response.raise_for_status()
    except HTTPError as error:
        if error.response is not None and error.response.status_code == 429:
            raise RuntimeError("CoinGecko rate limit reached. Please wait a minute and try again.") from error
        if error.response is not None and error.response.status_code == 404:
            raise ValueError(f"Coin '{coin_id}' was not found. Try BTC, ETH, SOL, or a CoinGecko id.") from error
        raise RuntimeError("CoinGecko returned an error. Please try again shortly.") from error
    except RequestException as error:
        raise RuntimeError("Could not connect to CoinGecko. Check your internet connection and try again.") from error

    payload = response.json()

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
