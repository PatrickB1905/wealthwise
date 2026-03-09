from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Any

log = logging.getLogger(__name__)


class MarketDataValidationError(Exception):
    pass


def _build_quotes_url(base_api_url: str, symbols: list[str]) -> str:
    base = base_api_url.rstrip("/")
    qs = urllib.parse.urlencode({"symbols": ",".join(symbols)})
    return f"{base}/quotes?{qs}"


def _build_instrument_search_url(base_api_url: str, query: str, *, limit: int = 10) -> str:
    base = base_api_url.rstrip("/")
    qs = urllib.parse.urlencode({"q": query, "limit": limit})
    return f"{base}/instruments/search?{qs}"


def _fetch_json(url: str) -> Any:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def fetch_quotes_from_market_data(base_api_url: str, symbols: list[str]) -> list[dict[str, Any]]:
    if not symbols:
        return []

    url = _build_quotes_url(base_api_url, symbols)

    try:
        data = _fetch_json(url)
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]
    except Exception as exc:
        log.warning("market-data quotes fetch failed: %s", exc)
        return []


def fetch_instruments_from_market_data(base_api_url: str, query: str) -> list[dict[str, Any]]:
    trimmed_query = query.strip()
    if not trimmed_query:
        return []

    url = _build_instrument_search_url(base_api_url, trimmed_query)

    try:
        data = _fetch_json(url)
    except Exception as exc:
        log.warning("market-data instrument search failed: %s", exc)
        raise MarketDataValidationError("Instrument validation is currently unavailable.") from exc

    if not isinstance(data, list):
        return []

    return [item for item in data if isinstance(item, dict)]


def ticker_exists_in_market_data(base_api_url: str, ticker: str) -> bool:
    symbol = ticker.strip().upper()
    if not symbol:
        return False

    results = fetch_instruments_from_market_data(base_api_url, symbol)

    for item in results:
        result_symbol = str(item.get("symbol") or "").strip().upper()
        if result_symbol == symbol:
            return True

    return False
