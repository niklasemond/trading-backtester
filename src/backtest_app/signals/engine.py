"""Declarative strategy evaluation and signal generation."""

from __future__ import annotations

from backtest_app.domain.market_data import MarketBar, MarketDataSet
from backtest_app.domain.signals import SignalPoint, SignalSeries
from backtest_app.domain.strategy import (
    ComparisonCondition,
    ConditionSpec,
    ConstantRef,
    CrossoverCondition,
    IndicatorRef,
    PriceRef,
    RocIndicator,
    SmaIndicator,
    StrategySpec,
    ValueRef,
    VolatilityIndicator,
)
from backtest_app.signals.indicators import (
    calculate_roc,
    calculate_sma,
    calculate_volatility,
)


def _resolve(
    ref: ValueRef, bar: MarketBar, values: dict[str, float | None]
) -> float | None:
    if isinstance(ref, IndicatorRef):
        return values[ref.id]
    if isinstance(ref, PriceRef):
        value = getattr(bar, ref.field.value)
        return None if value is None else float(value)
    if isinstance(ref, ConstantRef):
        return float(ref.value)
    raise TypeError(f"unsupported reference type: {type(ref).__name__}")


def _crossed(
    condition: CrossoverCondition,
    previous: dict[str, float | None],
    current: dict[str, float | None],
) -> bool:
    previous_left = previous[condition.left.id]
    previous_right = previous[condition.right.id]
    current_left = current[condition.left.id]
    current_right = current[condition.right.id]
    if None in (previous_left, previous_right, current_left, current_right):
        return False
    assert previous_left is not None
    assert previous_right is not None
    assert current_left is not None
    assert current_right is not None
    if condition.operator == "crosses_above":
        return previous_left <= previous_right and current_left > current_right
    return previous_left >= previous_right and current_left < current_right


def _comparison(
    condition: ComparisonCondition,
    bar: MarketBar,
    current: dict[str, float | None],
) -> bool:
    left = _resolve(condition.left, bar, current)
    right = _resolve(condition.right, bar, current)
    if left is None or right is None:
        return False
    return {
        "above": left > right,
        "below": left < right,
        "at_or_above": left >= right,
        "at_or_below": left <= right,
    }[condition.operator]


def _condition_matches(
    condition: ConditionSpec,
    previous: dict[str, float | None],
    current: dict[str, float | None],
    bar: MarketBar,
) -> bool:
    if isinstance(condition, CrossoverCondition):
        return _crossed(condition, previous, current)
    if isinstance(condition, ComparisonCondition):
        return _comparison(condition, bar, current)
    raise TypeError(f"unsupported condition type: {type(condition).__name__}")


def _conditions_match(
    conditions: tuple[ConditionSpec, ...],
    logic: str,
    previous: dict[str, float | None],
    current: dict[str, float | None],
    bar: MarketBar,
) -> bool:
    results = [
        _condition_matches(condition, previous, current, bar)
        for condition in conditions
    ]
    return all(results) if logic == "all" else any(results)


def generate_signals(
    strategy: StrategySpec, market_data: MarketDataSet
) -> SignalSeries:
    symbol = strategy.symbols[0]
    if market_data.symbol != symbol:
        raise ValueError(
            f"strategy symbol {symbol!r} does not match "
            f"market data {market_data.symbol!r}"
        )

    indicator_series: dict[str, tuple[float | None, ...]] = {}
    for indicator in strategy.indicators:
        if isinstance(indicator, SmaIndicator):
            values = calculate_sma(market_data.bars, indicator)
        elif isinstance(indicator, RocIndicator):
            values = calculate_roc(market_data.bars, indicator)
        elif isinstance(indicator, VolatilityIndicator):
            values = calculate_volatility(market_data.bars, indicator)
        else:
            raise TypeError(
                f"unsupported indicator type: {type(indicator).__name__}"
            )
        indicator_series[indicator.id] = values

    points: list[SignalPoint] = []
    previous_values: dict[str, float | None] | None = None
    for index, bar in enumerate(market_data.bars):
        current = {
            indicator_id: values[index]
            for indicator_id, values in indicator_series.items()
        }
        enter_long = False
        exit_long = False
        if previous_values is not None:
            enter_long = _conditions_match(
                strategy.entry_conditions,
                strategy.entry_logic,
                previous_values,
                current,
                bar,
            )
            exit_long = _conditions_match(
                strategy.exit_conditions,
                strategy.exit_logic,
                previous_values,
                current,
                bar,
            )
        points.append(
            SignalPoint(
                timestamp=bar.timestamp,
                indicator_values=current,
                enter_long=enter_long,
                exit_long=exit_long,
            )
        )
        previous_values = current
    return SignalSeries(symbol=symbol, points=tuple(points))
