from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backtest_app.domain.market_data import MarketBar, MarketDataMetadata, MarketDataSet


def bar(day: int, symbol: str = "SPY") -> MarketBar:
    return MarketBar(
        timestamp=datetime(2024, 1, day, tzinfo=timezone.utc),
        symbol=symbol,
        open=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
        volume=1_000,
    )


def metadata() -> MarketDataMetadata:
    return MarketDataMetadata(
        provider="deterministic-test",
        retrieved_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
    )


def test_market_bar_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        MarketBar(
            timestamp=datetime(2024, 1, 1),
            symbol="SPY",
            open=100,
            high=101,
            low=99,
            close=100,
            volume=1000,
        )


def test_dataset_requires_strict_timestamp_order() -> None:
    with pytest.raises(ValidationError, match="strictly ordered"):
        MarketDataSet(symbol="SPY", bars=(bar(2), bar(1)), metadata=metadata())


def test_dataset_rejects_symbol_mismatch() -> None:
    with pytest.raises(ValidationError, match="dataset symbol"):
        MarketDataSet(symbol="SPY", bars=(bar(1, symbol="QQQ"),), metadata=metadata())
