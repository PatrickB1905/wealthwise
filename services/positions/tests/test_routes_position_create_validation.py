from __future__ import annotations

import asyncio

import app.api.routes as routes_mod


def test_create_position_rejects_unknown_ticker(client, monkeypatch) -> None:
    monkeypatch.setattr(
        routes_mod,
        "ticker_exists_in_market_data",
        lambda base_url, ticker: False,
    )
    monkeypatch.setattr(
        routes_mod,
        "fetch_quotes_from_market_data",
        lambda base_url, symbols: [],
    )

    original_to_thread = asyncio.to_thread

    async def fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)

    response = client.post(
        "/api/positions",
        json={
            "ticker": "NOTREAL",
            "quantity": 1,
            "buyPrice": 100,
            "buyDate": "2026-03-08T00:00:00+00:00",
        },
    )

    monkeypatch.setattr(asyncio, "to_thread", original_to_thread)

    assert response.status_code == 400
    assert (
        response.json()["detail"] == "Please select a valid market symbol from the search results."
    )


def test_create_position_returns_503_when_market_data_validation_is_unavailable(
    client,
    monkeypatch,
) -> None:
    def fake_ticker_exists(base_url: str, ticker: str) -> bool:
        raise routes_mod.MarketDataValidationError(
            "Instrument validation is currently unavailable."
        )

    monkeypatch.setattr(routes_mod, "ticker_exists_in_market_data", fake_ticker_exists)
    monkeypatch.setattr(
        routes_mod,
        "fetch_quotes_from_market_data",
        lambda base_url, symbols: [],
    )

    original_to_thread = asyncio.to_thread

    async def fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)

    response = client.post(
        "/api/positions",
        json={
            "ticker": "AAPL",
            "quantity": 1,
            "buyPrice": 100,
            "buyDate": "2026-03-08T00:00:00+00:00",
        },
    )

    monkeypatch.setattr(asyncio, "to_thread", original_to_thread)

    assert response.status_code == 503
    assert response.json()["detail"] == "Instrument validation is currently unavailable."


def test_create_position_accepts_valid_ticker(client, monkeypatch) -> None:
    monkeypatch.setattr(
        routes_mod,
        "ticker_exists_in_market_data",
        lambda base_url, ticker: True,
    )
    monkeypatch.setattr(
        routes_mod,
        "fetch_quotes_from_market_data",
        lambda base_url, symbols: [],
    )

    original_to_thread = asyncio.to_thread

    async def fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)

    response = client.post(
        "/api/positions",
        json={
            "ticker": "AAPL",
            "quantity": 2,
            "buyPrice": 150.5,
            "buyDate": "2026-03-08T00:00:00+00:00",
        },
    )

    monkeypatch.setattr(asyncio, "to_thread", original_to_thread)

    assert response.status_code == 201
    assert response.json()["ticker"] == "AAPL"
    assert response.json()["quantity"] == 2.0
    assert response.json()["buyPrice"] == 150.5
