from datetime import UTC, datetime, timedelta

import pytest

from backtest_app.domain.market_data import MarketBar
from backtest_app.domain.strategy import PriceField, SmaIndicator
from backtest_app.signals.indicators import calculate_sma, simple_moving_average


def test_simple_moving_average_has_explicit_warmup_and_trailing_values() -> None:
    result = simple_moving_average((10.0, 9.0, 8.0, 9.0, 11.0), window=3)

    assert result == (None, None, 9.0, pytest.approx(26 / 3), pytest.approx(28 / 3))


def test_sma_uses_requested_market_bar_field() -> None:
    start = datetime(2024, 1, 2, tzinfo=UTC)
    bars = tuple(
        MarketBar(
            timestamp=start + timedelta(days=index),
            symbol="SPY",
            open=open_price,
            high=max(open_price, close_price) + 1,
            low=min(open_price, close_price) - 1,
            close=close_price,
            volume=100,
        )
        for index, (open_price, close_price) in enumerate(
            ((5.0, 10.0), (7.0, 20.0), (9.0, 30.0))
        )
    )

    result = calculate_sma(
        bars, SmaIndicator(id="open_sma", source=PriceField.OPEN, window=2)
    )

    assert result == (None, 6.0, 8.0)


def test_adjusted_close_indicator_fails_if_source_is_unavailable() -> None:
    bar = MarketBar(
        timestamp=datetime(2024, 1, 2, tzinfo=UTC),
        symbol="SPY",
        open=10,
        high=11,
        low=9,
        close=10,
        volume=100,
    )

    with pytest.raises(ValueError, match="adjusted_close.*unavailable"):
        calculate_sma(
            (bar,),
            SmaIndicator(id="adjusted", source=PriceField.ADJUSTED_CLOSE, window=1),
        )
