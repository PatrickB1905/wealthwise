from __future__ import annotations

import json
from urllib.error import URLError

import pytest

from app.services.market_data import (
    MarketDataValidationError,
    fetch_instruments_from_market_data,
    ticker_exists_in_market_data,
)


class _FakeResponse:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_fetch_instruments_from_market_data_returns_only_dict_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(req, timeout=10):  # noqa: ANN001
        assert "q=AAPL" in req.full_url
        return _FakeResponse(
            [
                {"symbol": "AAPL", "name": "Apple Inc."},
                {"symbol": "MSFT", "name": "Microsoft Corporation"},
                "ignore-me",
            ]
        )

    monkeypatch.setattr("app.services.market_data.urllib.request.urlopen", fake_urlopen)

    results = fetch_instruments_from_market_data("http://market-data/api", "AAPL")

    assert results == [
        {"symbol": "AAPL", "name": "Apple Inc."},
        {"symbol": "MSFT", "name": "Microsoft Corporation"},
    ]


def test_fetch_instruments_from_market_data_raises_validation_error_on_transport_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(req, timeout=10):  # noqa: ANN001
        raise URLError("boom")

    monkeypatch.setattr("app.services.market_data.urllib.request.urlopen", fake_urlopen)

    with pytest.raises(MarketDataValidationError, match="currently unavailable"):
        fetch_instruments_from_market_data("http://market-data/api", "AAPL")


def test_ticker_exists_in_market_data_matches_case_insensitively(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.market_data.fetch_instruments_from_market_data",
        lambda base_api_url, query: [
            {"symbol": "AAPL"},
            {"symbol": "MSFT"},
        ],
    )

    assert ticker_exists_in_market_data("http://market-data/api", "aapl") is True
    assert ticker_exists_in_market_data("http://market-data/api", "nvda") is False
