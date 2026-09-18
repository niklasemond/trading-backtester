import json
from datetime import date
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
