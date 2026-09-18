"""Yahoo Finance daily historical-data adapter."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from backtest_app.domain.market_data import MarketBar, MarketDataMetadata, MarketDataSet
from backtest_app.market_data.provider import MarketDataProvider, MarketDataRequest

_BASE = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
_UA = "Mozilla/5.0 (compatible; trading-backtester/0.1)"
Transport = Callable[[str], bytes]


class MarketDataProviderError(RuntimeError):
    """External provider did not return usable data."""


def _download(url: str) -> bytes:
    try:
        with urlopen(Request(url, headers={"User-Agent": _UA}), timeout=20) as response:  # noqa: S310
            return response.read()
    except (HTTPError, URLError, TimeoutError) as exc:
        raise MarketDataProviderError(f"Yahoo Finance request failed: {exc}") from exc


def _unix(day: date) -> int:
    return int(datetime.combine(day, time.min, tzinfo=UTC).timestamp())


def _event_day(event: dict) -> date | None:
    try:
        return datetime.fromtimestamp(int(event["date"]), tz=UTC).date()
    except (KeyError, TypeError, ValueError, OSError):
        return None


def _split(event: dict) -> float | None:
    try:
        return float(event["numerator"]) / float(event["denominator"])
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        try:
            left, right = str(event["splitRatio"]).split(":", 1)
            return float(left) / float(right)
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            return None


def _parse(payload: dict, request: MarketDataRequest) -> MarketDataSet:
    chart = payload.get("chart") or {}
    if chart.get("error"):
        error = chart["error"]
        raise MarketDataProviderError(str(error.get("description") or error.get("code")))
    results = chart.get("result") or []
    if not results:
        raise MarketDataProviderError(f"Yahoo Finance returned no data for {request.symbol}")

    result = results[0]
    quote_rows = (result.get("indicators") or {}).get("quote") or []
    if not quote_rows:
        raise MarketDataProviderError("Yahoo Finance response is missing OHLCV data")
    quote_data = quote_rows[0]
    adjusted_rows = (result.get("indicators") or {}).get("adjclose") or []
    adjusted = adjusted_rows[0].get("adjclose", []) if adjusted_rows else []

    events = result.get("events") or {}
    dividends: dict[date, float] = {}
    for event in (events.get("dividends") or {}).values():
        day = _event_day(event)
        if day is not None and event.get("amount") is not None:
            dividends[day] = dividends.get(day, 0.0) + float(event["amount"])
    splits = {
        day: ratio
        for event in (events.get("splits") or {}).values()
        if (day := _event_day(event)) is not None and (ratio := _split(event)) is not None
    }

    bars: list[MarketBar] = []
    fields = ("open", "high", "low", "close", "volume")
    for index, raw_ts in enumerate(result.get("timestamp") or []):
        try:
            ts = datetime.fromtimestamp(int(raw_ts), tz=UTC)
            values = {field: quote_data[field][index] for field in fields}
        except (KeyError, IndexError, TypeError, ValueError, OSError):
            continue
        if not request.start_date <= ts.date() <= request.end_date or any(v is None for v in values.values()):
            continue
        adj = adjusted[index] if index < len(adjusted) else None
        bars.append(
            MarketBar(
                timestamp=ts,
                symbol=request.symbol,
                open=float(values["open"]),
                high=float(values["high"]),
                low=float(values["low"]),
                close=float(values["close"]),
                volume=int(values["volume"]),
                adjusted_close=float(adj) if adj is not None else None,
                dividend=dividends.get(ts.date()),
                split_ratio=splits.get(ts.date()),
            )
        )
    if not bars:
        raise MarketDataProviderError(f"Yahoo Finance returned no complete bars for {request.symbol}")

    meta = result.get("meta") or {}
    return MarketDataSet(
        symbol=request.symbol,
        bars=tuple(sorted(bars, key=lambda bar: bar.timestamp)),
        metadata=MarketDataMetadata(
            provider="yahoo",
            retrieved_at=datetime.now(tz=UTC),
            provider_version="chart-v8",
            dataset_id=f"{request.symbol}:{request.start_date}:{request.end_date}:1d",
            notes={
                "exchange": str(meta.get("exchangeName") or ""),
                "timezone": str(meta.get("exchangeTimezoneName") or ""),
                "price_adjustment": "Yahoo OHLC may reflect split adjustments; adjusted_close is stored separately.",
            },
        ),
    )


class YahooFinanceProvider(MarketDataProvider):
    def __init__(self, transport: Transport | None = None) -> None:
        self._transport = transport or _download

    @property
    def name(self) -> str:
        return "yahoo"

    async def get_history(self, request: MarketDataRequest) -> MarketDataSet:
        if request.frequency.value != "1d":
            raise MarketDataProviderError("Yahoo provider currently supports daily bars only")
        query = urlencode(
            {
                "period1": _unix(request.start_date),
                "period2": _unix(request.end_date + timedelta(days=1)),
                "interval": "1d",
                "events": "div,splits",
                "includeAdjustedClose": "true",
                "includePrePost": "false",
            }
        )
        url = f"{_BASE.format(symbol=quote(request.symbol, safe=''))}?{query}"
        raw = await asyncio.to_thread(self._transport, url)
        try:
            return _parse(json.loads(raw.decode()), request)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MarketDataProviderError("Yahoo Finance returned invalid JSON") from exc
