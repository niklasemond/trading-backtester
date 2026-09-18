import json
from datetime import UTC, date, datetime
from urllib.parse import parse_qs, urlparse

import pytest

from backtest_app.market_data.provider import MarketDataRequest
from backtest_app.market_data.yahoo import MarketDataProviderError, YahooFinanceProvider


def yahoo_payload() -> bytes:
    return json.dumps(
        {
            "chart": {
                "result": [
                    {
                        "meta": {
                            "currency": "USD",
                            "exchangeName": "NYQ",
                            "exchangeTimezoneName": "America/New_York",
                        },
                        "timestamp": [1704205800, 1704292200],
                        "indicators": {
                            "quote": [
                                {
                                    "open": [100.0, 102.0],
                                    "high": [103.0, 104.0],
                                    "low": [99.0, 101.0],
                                    "close": [102.0, 103.0],
                                    "volume": [1000, 1200],
                                }
                            ],
                            "adjclose": [{"adjclose": [101.5, 102.5]}],
                        },
                        "events": {
                            "dividends": {"1704205800": {"date": 1704205800, "amount": 0.5}},
                            "splits": {
                                "1704292200": {
                                    "date": 1704292200,
                                    "numerator": 2.0,
                                    "denominator": 1.0,
                                    "splitRatio": "2:1",
                                }
                            },
                        },
                    }
                ],
                "error": None,
            }
        }
    ).encode()


@pytest.mark.asyncio
async def test_yahoo_provider_normalizes_chart_payload_and_events() -> None:
    seen: list[str] = []

    def transport(url: str) -> bytes:
        seen.append(url)
        return yahoo_payload()

    provider = YahooFinanceProvider(transport=transport)
    result = await provider.get_history(
        MarketDataRequest(symbol="SPY", start_date=date(2024, 1, 2), end_date=date(2024, 1, 3))
    )

    assert result.metadata.provider == "yahoo"
    assert result.metadata.provider_version == "chart-v8"
    assert len(result.bars) == 2
    assert result.bars[0].adjusted_close == 101.5
    assert result.bars[0].dividend == 0.5
    assert result.bars[1].split_ratio == 2.0

    parsed = urlparse(seen[0])
    query = parse_qs(parsed.query)
    assert parsed.path.endswith("/SPY")
    assert query["interval"] == ["1d"]
    assert int(query["period2"][0]) > int(query["period1"][0])


@pytest.mark.asyncio
async def test_yahoo_provider_rejects_provider_error() -> None:
    payload = json.dumps(
        {"chart": {"result": None, "error": {"code": "Not Found", "description": "No data found"}}}
    ).encode()
    provider = YahooFinanceProvider(transport=lambda _: payload)

    with pytest.raises(MarketDataProviderError, match="No data found"):
        await provider.get_history(
            MarketDataRequest(symbol="NOPE", start_date=date(2024, 1, 2), end_date=date(2024, 1, 3))
        )


@pytest.mark.asyncio
async def test_yahoo_provider_skips_incomplete_rows() -> None:
    payload = json.loads(yahoo_payload())
    payload["chart"]["result"][0]["indicators"]["quote"][0]["open"][1] = None
    provider = YahooFinanceProvider(transport=lambda _: json.dumps(payload).encode())

    result = await provider.get_history(
        MarketDataRequest(symbol="SPY", start_date=date(2024, 1, 2), end_date=date(2024, 1, 3))
    )

    assert len(result.bars) == 1


def daily_payload(
    *,
    session_open_utc: datetime,
    regular_end_utc: datetime | None,
) -> bytes:
    meta = {
        "currency": "USD",
        "exchangeName": "NMS",
        "exchangeTimezoneName": "America/New_York",
    }
    if regular_end_utc is not None:
        meta["currentTradingPeriod"] = {
            "regular": {
                "start": int(session_open_utc.timestamp()),
                "end": int(regular_end_utc.timestamp()),
                "timezone": "EDT",
                "gmtoffset": -14400,
            }
        }
    return json.dumps(
        {
            "chart": {
                "result": [
                    {
                        "meta": meta,
                        "timestamp": [int(session_open_utc.timestamp())],
                        "indicators": {
                            "quote": [
                                {
                                    "open": [100.0],
                                    "high": [102.0],
                                    "low": [99.0],
                                    "close": [101.0],
                                    "volume": [1000],
                                }
                            ],
                            "adjclose": [{"adjclose": [101.0]}],
                        },
                        "events": {},
                    }
                ],
                "error": None,
            }
        }
    ).encode()


@pytest.mark.asyncio
async def test_yahoo_accepts_completed_historical_session() -> None:
    session_open = datetime(2026, 9, 17, 13, 30, tzinfo=UTC)
    provider = YahooFinanceProvider(
        transport=lambda _: daily_payload(
            session_open_utc=session_open,
            regular_end_utc=None,
        ),
        clock=lambda: datetime(2026, 9, 18, 15, 0, tzinfo=UTC),
    )

    result = await provider.get_history(
        MarketDataRequest(
            symbol="SPY",
            start_date=date(2026, 9, 17),
            end_date=date(2026, 9, 17),
        )
    )

    assert len(result.bars) == 1


@pytest.mark.asyncio
async def test_yahoo_excludes_current_incomplete_daily_session() -> None:
    session_open = datetime(2026, 9, 18, 13, 30, tzinfo=UTC)
    session_end = datetime(2026, 9, 18, 20, 0, tzinfo=UTC)
    provider = YahooFinanceProvider(
        transport=lambda _: daily_payload(
            session_open_utc=session_open,
            regular_end_utc=session_end,
        ),
        clock=lambda: datetime(2026, 9, 18, 17, 0, tzinfo=UTC),
    )

    with pytest.raises(MarketDataProviderError, match="no complete bars"):
        await provider.get_history(
            MarketDataRequest(
                symbol="SPY",
                start_date=date(2026, 9, 18),
                end_date=date(2026, 9, 18),
            )
        )


@pytest.mark.asyncio
async def test_yahoo_accepts_current_daily_bar_after_regular_session_close() -> None:
    session_open = datetime(2026, 9, 18, 13, 30, tzinfo=UTC)
    session_end = datetime(2026, 9, 18, 20, 0, tzinfo=UTC)
    provider = YahooFinanceProvider(
        transport=lambda _: daily_payload(
            session_open_utc=session_open,
            regular_end_utc=session_end,
        ),
        clock=lambda: datetime(2026, 9, 18, 20, 1, tzinfo=UTC),
    )

    result = await provider.get_history(
        MarketDataRequest(
            symbol="SPY",
            start_date=date(2026, 9, 18),
            end_date=date(2026, 9, 18),
        )
    )

    assert len(result.bars) == 1
    assert result.metadata.retrieved_at == datetime(2026, 9, 18, 20, 1, tzinfo=UTC)


@pytest.mark.asyncio
async def test_yahoo_weekend_keeps_latest_completed_friday_bar() -> None:
    friday_open = datetime(2026, 9, 18, 13, 30, tzinfo=UTC)
    provider = YahooFinanceProvider(
        transport=lambda _: daily_payload(
            session_open_utc=friday_open,
            regular_end_utc=None,
        ),
        clock=lambda: datetime(2026, 9, 19, 14, 0, tzinfo=UTC),
    )

    result = await provider.get_history(
        MarketDataRequest(
            symbol="SPY",
            start_date=date(2026, 9, 18),
            end_date=date(2026, 9, 19),
        )
    )

    assert len(result.bars) == 1


@pytest.mark.asyncio
async def test_yahoo_uses_us_close_fallback_when_current_trading_period_missing() -> None:
    session_open = datetime(2026, 9, 18, 13, 30, tzinfo=UTC)
    provider = YahooFinanceProvider(
        transport=lambda _: daily_payload(
            session_open_utc=session_open,
            regular_end_utc=None,
        ),
        clock=lambda: datetime(2026, 9, 18, 20, 1, tzinfo=UTC),
    )

    result = await provider.get_history(
        MarketDataRequest(
            symbol="SPY",
            start_date=date(2026, 9, 18),
            end_date=date(2026, 9, 18),
        )
    )

    assert len(result.bars) == 1
    assert "Daily bars dated today" in result.metadata.notes["daily_bar_completion_policy"]
