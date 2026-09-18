"""Yahoo Finance daily historical-data adapter."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from backtest_app.domain.market_data import MarketBar, MarketDataMetadata, MarketDataSet
from backtest_app.market_data.provider import MarketDataProvider, MarketDataRequest

_BASE = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
_UA = "Mozilla/5.0 (compatible; trading-backtester/0.1)"
Transport = Callable[[str], bytes]
Clock = Callable[[], datetime]


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

_US_EQUITY_TIMEZONE = "America/New_York"
_US_REGULAR_CLOSE = time(16, 0)


def _exchange_timezone(meta: dict) -> ZoneInfo | None:
    name = str(meta.get("exchangeTimezoneName") or "")
    if not name:
        return None
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return None


def _regular_session_end(meta: dict, *, session_date: date, timezone: ZoneInfo) -> datetime | None:
    """Return Yahoo's stated regular-session end when it matches the bar date."""

    try:
        raw_end = int(meta["currentTradingPeriod"]["regular"]["end"])
        end = datetime.fromtimestamp(raw_end, tz=UTC).astimezone(timezone)
    except (KeyError, TypeError, ValueError, OSError):
        return None
    return end if end.date() == session_date else None


def _is_completed_daily_session(
    timestamp: datetime,
    *,
    meta: dict,
    now: datetime,
) -> bool:
    """Whether a Yahoo daily bar represents a completed exchange session.

    Past exchange-local session dates are complete. A same-day bar is accepted
    only after the regular session end. Yahoo's currentTradingPeriod metadata is
    preferred; for the current US-equity scope, 16:00 America/New_York is the
    conservative fallback when Yahoo omits that field.
    """

    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Yahoo provider clock must return a timezone-aware datetime")

    timezone = _exchange_timezone(meta)
    if timezone is None:
        # Without an exchange timezone we cannot safely interpret a current-day
        # daily timestamp. Historical UTC dates remain safe to accept.
        return timestamp.date() < now.astimezone(UTC).date()

    session_date = timestamp.astimezone(timezone).date()
    current_exchange_date = now.astimezone(timezone).date()
    if session_date < current_exchange_date:
        return True
    if session_date > current_exchange_date:
        return False

    end = _regular_session_end(meta, session_date=session_date, timezone=timezone)
    if end is None and str(meta.get("exchangeTimezoneName") or "") == _US_EQUITY_TIMEZONE:
        end = datetime.combine(session_date, _US_REGULAR_CLOSE, tzinfo=timezone)

    # Unknown same-day session end is treated as incomplete rather than risking
    # a close-derived signal from a still-forming daily bar.
    return end is not None and now.astimezone(timezone) >= end


def _session_date(timestamp: datetime, meta: dict) -> date:
    timezone = _exchange_timezone(meta)
    if timezone is None:
        return timestamp.date()
    return timestamp.astimezone(timezone).date()


def _parse(payload: dict, request: MarketDataRequest, *, now: datetime) -> MarketDataSet:
    chart = payload.get("chart") or {}
    if chart.get("error"):
        error = chart["error"]
        raise MarketDataProviderError(str(error.get("description") or error.get("code")))
    results = chart.get("result") or []
    if not results:
        raise MarketDataProviderError(f"Yahoo Finance returned no data for {request.symbol}")

    result = results[0]
    meta = result.get("meta") or {}
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
        session_day = _session_date(ts, meta)
        if not request.start_date <= session_day <= request.end_date or any(v is None for v in values.values()):
            continue
        if not _is_completed_daily_session(ts, meta=meta, now=now):
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
                dividend=dividends.get(session_day),
                split_ratio=splits.get(session_day),
            )
        )
    if not bars:
        raise MarketDataProviderError(f"Yahoo Finance returned no complete bars for {request.symbol}")

    return MarketDataSet(
        symbol=request.symbol,
        bars=tuple(sorted(bars, key=lambda bar: bar.timestamp)),
        metadata=MarketDataMetadata(
            provider="yahoo",
            retrieved_at=now.astimezone(UTC),
            provider_version="chart-v8",
            dataset_id=f"{request.symbol}:{request.start_date}:{request.end_date}:1d",
            notes={
                "exchange": str(meta.get("exchangeName") or ""),
                "timezone": str(meta.get("exchangeTimezoneName") or ""),
                "tradable_price_series": (
                    "Yahoo quote OHLC is stored as delivered and treated by the "
                    "engine as raw tradable/mark-to-market prices."
                ),
                "adjusted_close_policy": (
                    "Yahoo adjusted_close is stored separately and is never used "
                    "for execution or portfolio mark-to-market."
                ),
                "corporate_action_policy": (
                    "Yahoo dividend/split chart events are mapped to event-date "
                    "bars; held shares receive explicit cash/share adjustments "
                    "before event-date execution."
                ),
                "daily_bar_completion_policy": (
                    "Daily bars dated today in the exchange timezone are excluded "
                    "until the regular session has ended; Yahoo currentTradingPeriod "
                    "is preferred, with a 16:00 America/New_York fallback for the "
                    "current US-equity scope."
                ),
                "provider_uncertainty": (
                    "Yahoo chart-v8 data is research-grade and may contain "
                    "corporate-action anomalies; this adapter does not repair them."
                ),
            },
        ),
    )


class YahooFinanceProvider(MarketDataProvider):
    def __init__(
        self,
        transport: Transport | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._transport = transport or _download
        self._clock = clock or (lambda: datetime.now(tz=UTC))

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
            return _parse(json.loads(raw.decode()), request, now=self._clock())
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MarketDataProviderError("Yahoo Finance returned invalid JSON") from exc
