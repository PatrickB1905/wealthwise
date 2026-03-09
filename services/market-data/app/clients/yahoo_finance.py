from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from urllib.parse import quote, urlparse

import yfinance as yf

from app.core.config import settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class QuoteData:
    symbol: str
    current_price: float
    daily_change_percent: float
    logo_url: str


@dataclass(frozen=True)
class InstrumentSearchResultData:
    symbol: str
    name: str
    exchange: str
    asset_type: str
    currency: str
    logo_url: str


@dataclass(frozen=True)
class InstrumentMetadata:
    logo_url: str


_METADATA_CACHE: dict[str, InstrumentMetadata] = {}
_METADATA_CACHE_TS: dict[str, float] = {}
_METADATA_CACHE_TTL_SECONDS = 60.0 * 60.0


def _normalize_domain_from_website(website: str) -> str:
    parsed = urlparse(website.strip())
    domain = parsed.netloc.strip().lower()

    if domain.startswith("www."):
        domain = domain[4:]

    return domain


def _build_logo_dev_url(domain: str) -> str:
    if not domain or not settings.logo_dev_token:
        return ""

    encoded_domain = quote(domain, safe="")
    encoded_token = quote(settings.logo_dev_token, safe="")
    base_url = settings.logo_dev_base_url.rstrip("/")

    return f"{base_url}/{encoded_domain}?token={encoded_token}"


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _normalize_symbol(value: object) -> str:
    return _normalize_text(value).upper()


def _resolve_logo_url_from_info(info: dict[str, object]) -> str:
    website = _normalize_text(info.get("website") or info.get("websiteUrl") or info.get("homepage"))
    raw_logo_url = _normalize_text(info.get("logo_url") or info.get("logoUrl"))

    if website:
        domain = _normalize_domain_from_website(website)
        built_logo = _build_logo_dev_url(domain)
        if built_logo:
            return built_logo

    return raw_logo_url


def _extract_logo_url(raw: dict[str, object]) -> str:
    return _resolve_logo_url_from_info(raw)


def _build_instrument_result(raw: dict[str, object]) -> InstrumentSearchResultData | None:
    symbol = _normalize_symbol(raw.get("symbol"))
    if not symbol:
        return None

    name = _normalize_text(
        raw.get("shortname") or raw.get("longname") or raw.get("name") or raw.get("displayName")
    )
    if not name:
        return None

    exchange = _normalize_text(
        raw.get("exchange")
        or raw.get("fullExchangeName")
        or raw.get("exchangeName")
        or raw.get("exchDisp")
    )

    asset_type = _normalize_text(
        raw.get("quoteType") or raw.get("typeDisp") or raw.get("quoteSourceName")
    )

    currency = _normalize_text(raw.get("currency"))

    return InstrumentSearchResultData(
        symbol=symbol,
        name=name,
        exchange=exchange,
        asset_type=asset_type,
        currency=currency,
        logo_url=_extract_logo_url(raw),
    )


def _cache_put_metadata(symbol: str, metadata: InstrumentMetadata, *, now: float) -> None:
    _METADATA_CACHE[symbol] = metadata
    _METADATA_CACHE_TS[symbol] = now


def _cache_get_metadata(symbol: str, *, now: float) -> InstrumentMetadata | None:
    cached = _METADATA_CACHE.get(symbol)
    if cached is None:
        return None

    ts = _METADATA_CACHE_TS.get(symbol, 0.0)
    age = now - ts
    if age > _METADATA_CACHE_TTL_SECONDS:
        _METADATA_CACHE.pop(symbol, None)
        _METADATA_CACHE_TS.pop(symbol, None)
        return None

    return cached


def _normalize_exchange(value: str) -> str:
    compact = value.replace(" ", "").replace("-", "").upper()
    if compact in {"NMS", "NAS", "NASDAQGS", "NASDAQGM", "NASDAQCM", "NASDAQ"}:
        return "NASDAQ"
    if compact in {"NYQ", "NYSE"}:
        return "NYSE"
    return value.strip().upper()


def _normalize_asset_type(value: str) -> str:
    return value.strip().upper()


def _is_supported_us_equity(item: InstrumentSearchResultData) -> bool:
    allowed_exchanges = {"NYSE", "NASDAQ"}
    allowed_asset_types = {"EQUITY"}

    normalized_exchange = _normalize_exchange(item.exchange)
    normalized_asset_type = _normalize_asset_type(item.asset_type)

    return normalized_exchange in allowed_exchanges and normalized_asset_type in allowed_asset_types


def _sort_key_for_query(item: InstrumentSearchResultData, query_upper: str) -> tuple[int, int, str]:
    symbol = item.symbol.upper()
    name = item.name.upper()

    exact_symbol = 0 if symbol == query_upper else 1
    symbol_prefix = 0 if symbol.startswith(query_upper) else 1
    name_prefix = 0 if name.startswith(query_upper) else 1

    return (exact_symbol, symbol_prefix + name_prefix, symbol)


class YahooFinanceClient:
    """
    Small wrapper so we can unit test without real network calls.
    """

    def _fetch_info(self, symbol: str) -> dict[str, object]:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
        if not isinstance(info, dict):
            return {}
        return info

    def _get_instrument_metadata(self, symbol: str) -> InstrumentMetadata:
        sym = symbol.strip().upper()
        if not sym:
            return InstrumentMetadata(logo_url="")

        now = time.time()
        cached = _cache_get_metadata(sym, now=now)
        if cached is not None:
            return cached

        logo_url = ""
        try:
            info = self._fetch_info(sym)
            logo_url = _resolve_logo_url_from_info(info)
        except Exception:
            log.exception("Failed to fetch instrument metadata for %s", sym)

        metadata = InstrumentMetadata(logo_url=logo_url)
        _cache_put_metadata(sym, metadata, now=now)
        return metadata

    def fetch_quote(self, symbol: str) -> QuoteData | None:
        sym = symbol.strip().upper()
        if not sym:
            return None

        try:
            ticker = yf.Ticker(sym)
            info = ticker.info or {}
            if not isinstance(info, dict):
                info = {}

            logo_url = _resolve_logo_url_from_info(info)

            hist = ticker.history(period="2d", actions=False)
            if hist is None or len(hist) < 2:
                log.warning("Not enough history data for %s", sym)
                return None

            prev_close = float(hist["Close"].iloc[-2])
            current_price = float(hist["Close"].iloc[-1])

            daily_pct = ((current_price - prev_close) / prev_close) * 100.0 if prev_close else 0.0

            return QuoteData(
                symbol=sym,
                current_price=current_price,
                daily_change_percent=round(daily_pct, 2),
                logo_url=logo_url,
            )
        except Exception:
            log.exception("Failed to fetch quote for %s", sym)
            return None

    def search_instruments(
        self, query: str, *, max_results: int = 10
    ) -> list[InstrumentSearchResultData]:
        query_text = query.strip()
        if not query_text:
            return []

        search_cls = getattr(yf, "Search", None)
        if search_cls is None:
            log.warning("yfinance.Search is not available in the installed yfinance version")
            return []

        try:
            search = search_cls(
                query=query_text,
                max_results=max_results * 3,
                news_count=0,
                include_cb=False,
                include_nav_links=False,
                enable_fuzzy_query=False,
            )

            quotes = getattr(search, "quotes", None)
            if quotes is None:
                maybe_search = getattr(search, "search", None)
                if callable(maybe_search):
                    maybe_search()
                quotes = getattr(search, "quotes", None)

            raw_quotes = list(quotes or [])
        except Exception:
            log.exception("Failed to search instruments for query=%s", query_text)
            return []

        seen: set[str] = set()
        results: list[InstrumentSearchResultData] = []
        query_upper = query_text.upper()

        for raw in raw_quotes:
            if not isinstance(raw, dict):
                continue

            built = _build_instrument_result(raw)
            if built is None:
                continue

            if not _is_supported_us_equity(built):
                continue

            if built.symbol in seen:
                continue

            seen.add(built.symbol)
            results.append(built)

        results.sort(key=lambda item: _sort_key_for_query(item, query_upper))
        shortlisted = results[:max_results]

        enriched: list[InstrumentSearchResultData] = []
        for item in shortlisted:
            if item.logo_url:
                enriched.append(item)
                continue

            metadata = self._get_instrument_metadata(item.symbol)
            enriched.append(
                InstrumentSearchResultData(
                    symbol=item.symbol,
                    name=item.name,
                    exchange=item.exchange,
                    asset_type=item.asset_type,
                    currency=item.currency,
                    logo_url=metadata.logo_url,
                )
            )

        return enriched
