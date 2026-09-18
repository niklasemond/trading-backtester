from datetime import UTC, datetime, timedelta

import pytest

from backtest_app.domain.market_data import MarketBar, MarketDataMetadata, MarketDataSet
from backtest_app.domain.strategy import (
    CrossoverCondition,
    IndicatorRef,
    SmaIndicator,
    StrategySpec,
)
from backtest_app.signals.engine import generate_signals


def make_market_data(closes: tuple[float, ...], symbol: str = "SPY") -> MarketDataSet:
    start = datetime(2024, 1, 2, tzinfo=UTC)
    bars = tuple(
        MarketBar(
            timestamp=start + timedelta(days=index),
            symbol=symbol,
            open=close,
            high=close + 1,
            low=close - 1,
            close=close,
            volume=1_000,
        )
        for index, close in enumerate(closes)
    )
    return MarketDataSet(
        symbol=symbol,
        bars=bars,
        metadata=MarketDataMetadata(
            provider="deterministic-test",
            retrieved_at=datetime(2024, 1, 1, tzinfo=UTC),
        ),
    )


def crossover_spec(symbol: str = "SPY") -> StrategySpec:
    fast = IndicatorRef(id="fast")
    slow = IndicatorRef(id="slow")
    return StrategySpec(
        name="2/3 SMA crossover",
        symbols=(symbol,),
        indicators=(
            SmaIndicator(id="fast", window=2),
            SmaIndicator(id="slow", window=3),
        ),
        entry_conditions=(
            CrossoverCondition(left=fast, operator="crosses_above", right=slow),
        ),
        exit_conditions=(
            CrossoverCondition(left=fast, operator="crosses_below", right=slow),
        ),
    )


def test_crossover_signal_generation_and_warmup() -> None:
    result = generate_signals(
        crossover_spec(), make_market_data((10, 9, 8, 9, 11, 10, 8))
    )

    assert [point.indicator_values["fast"] for point in result.points] == [
        None,
        9.5,
        8.5,
        8.5,
        10.0,
        10.5,
        9.0,
    ]
    assert [point.indicator_values["slow"] for point in result.points] == [
        None,
        None,
        9.0,
        pytest.approx(26 / 3),
        pytest.approx(28 / 3),
        10.0,
        pytest.approx(29 / 3),
    ]
    assert [index for index, point in enumerate(result.points) if point.enter_long] == [4]
    assert [index for index, point in enumerate(result.points) if point.exit_long] == [6]


def test_crossover_includes_transition_from_equality() -> None:
    # At index 2, SMA(2) == SMA(3) == 10. At index 3 the fast SMA is above.
    result = generate_signals(crossover_spec(), make_market_data((10, 10, 10, 12)))

    assert result.points[2].indicator_values == {"fast": 10.0, "slow": 10.0}
    assert result.points[3].enter_long is True


def test_future_bar_cannot_change_prior_indicator_values_or_signals() -> None:
    prefix = (10, 9, 8, 9, 11)
    baseline = generate_signals(crossover_spec(), make_market_data(prefix))
    extended = generate_signals(
        crossover_spec(), make_market_data(prefix + (1_000_000.0,))
    )

    assert extended.points[: len(prefix)] == baseline.points


def test_signal_engine_rejects_symbol_mismatch() -> None:
    with pytest.raises(ValueError, match="does not match"):
        generate_signals(crossover_spec("QQQ"), make_market_data((10, 9, 8)))
