from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from backtest_app.domain.market_data import (
    MarketBar,
    MarketDataMetadata,
    MarketDataSet,
)
from backtest_app.domain.strategy import (
    ComparisonCondition,
    ConstantRef,
    CrossoverCondition,
    IndicatorRef,
    PriceRef,
    RocIndicator,
    SmaIndicator,
    StrategySpec,
    VolatilityIndicator,
)
from backtest_app.services.backtests import required_warmup_bars
from backtest_app.signals.engine import generate_signals
from backtest_app.signals.indicators import rate_of_change, rolling_volatility


def data(closes: tuple[float, ...]) -> MarketDataSet:
    start = datetime(2024, 1, 2, tzinfo=UTC)
    bars = tuple(
        MarketBar(
            timestamp=start + timedelta(days=i),
            symbol="SPY",
            open=close,
            high=close + 1,
            low=close - 1,
            close=close,
            volume=1000,
        )
        for i, close in enumerate(closes)
    )
    return MarketDataSet(
        symbol="SPY",
        bars=bars,
        metadata=MarketDataMetadata(
            provider="test",
            retrieved_at=datetime(2024, 1, 1, tzinfo=UTC),
        ),
    )


def filtered_spec() -> StrategySpec:
    fast = IndicatorRef(id="fast")
    slow = IndicatorRef(id="slow")
    momentum = IndicatorRef(id="momentum")
    return StrategySpec(
        schema_version="1.1",
        name="filtered trend",
        symbols=("SPY",),
        indicators=(
            SmaIndicator(id="fast", window=2),
            SmaIndicator(id="slow", window=3),
            RocIndicator(id="momentum", window=2),
        ),
        entry_conditions=(
            CrossoverCondition(
                left=fast, operator="crosses_above", right=slow
            ),
            ComparisonCondition(
                left=PriceRef(), operator="above", right=slow
            ),
            ComparisonCondition(
                left=momentum,
                operator="above",
                right=ConstantRef(value=0.0),
            ),
        ),
        exit_conditions=(
            CrossoverCondition(
                left=fast, operator="crosses_below", right=slow
            ),
            ComparisonCondition(
                left=momentum,
                operator="below",
                right=ConstantRef(value=0.0),
            ),
        ),
        entry_logic="all",
        exit_logic="any",
    )


def test_roc_and_volatility_are_trailing_only() -> None:
    values = (100.0, 110.0, 99.0, 108.9)
    assert rate_of_change(values, 2)[2] == pytest.approx(-0.01)
    assert rolling_volatility(values, 2, 1)[2] == pytest.approx(0.1414213562)


def test_v11_serializes_new_indicator_and_operand_types() -> None:
    spec = filtered_spec()
    payload = spec.model_dump(mode="json")
    assert payload["schema_version"] == "1.1"
    assert payload["indicators"][2]["type"] == "roc"
    assert payload["entry_conditions"][1]["left"] == {
        "kind": "price",
        "field": "close",
    }


def test_v10_rejects_v11_features() -> None:
    with pytest.raises(ValidationError, match="1.0 supports SMA indicators only"):
        StrategySpec(
            schema_version="1.0",
            name="invalid",
            symbols=("SPY",),
            indicators=(RocIndicator(id="momentum", window=20),),
            entry_conditions=(
                ComparisonCondition(
                    left=IndicatorRef(id="momentum"),
                    operator="above",
                    right=ConstantRef(value=0),
                ),
            ),
            exit_conditions=(
                ComparisonCondition(
                    left=IndicatorRef(id="momentum"),
                    operator="below",
                    right=ConstantRef(value=0),
                ),
            ),
        )


def test_filtered_strategy_supports_all_entry_and_any_exit_logic() -> None:
    result = generate_signals(
        filtered_spec(), data((10, 9, 8, 9, 11, 10, 8))
    )
    assert result.points[4].enter_long is True
    assert result.points[6].exit_long is True


def test_v11_filters_have_no_future_leakage() -> None:
    prefix = (10, 9, 8, 9, 11, 10)
    baseline = generate_signals(filtered_spec(), data(prefix))
    extended = generate_signals(
        filtered_spec(), data(prefix + (1_000_000.0,))
    )
    assert extended.points[: len(prefix)] == baseline.points


def test_required_warmup_covers_all_v11_indicator_windows() -> None:
    fast = IndicatorRef(id="fast")
    slow = IndicatorRef(id="slow")
    spec = StrategySpec(
        schema_version="1.1",
        name="warmup",
        symbols=("SPY",),
        indicators=(
            SmaIndicator(id="fast", window=20),
            RocIndicator(id="momentum", window=126),
            VolatilityIndicator(id="volatility", window=63),
            SmaIndicator(id="slow", window=200),
        ),
        entry_conditions=(
            CrossoverCondition(
                left=fast, operator="crosses_above", right=slow
            ),
        ),
        exit_conditions=(
            CrossoverCondition(
                left=fast, operator="crosses_below", right=slow
            ),
        ),
    )
    assert required_warmup_bars(spec) == 200
