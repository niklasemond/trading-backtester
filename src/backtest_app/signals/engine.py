"""Declarative strategy evaluation and crossover signal generation."""

from __future__ import annotations

from backtest_app.domain.market_data import MarketDataSet
from backtest_app.domain.signals import SignalPoint, SignalSeries
from backtest_app.domain.strategy import (
    ConditionSpec,
    CrossoverCondition,
    SmaIndicator,
    StrategySpec,
)
from backtest_app.signals.indicators import calculate_sma


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
    if condition.operator == "crosses_below":
        return previous_left >= previous_right and current_left < current_right

    raise ValueError(f"unsupported crossover operator: {condition.operator}")


def _condition_matches(
    condition: ConditionSpec,
    previous: dict[str, float | None],
    current: dict[str, float | None],
) -> bool:
    if isinstance(condition, CrossoverCondition):
        return _crossed(condition, previous, current)
    raise TypeError(f"unsupported condition type: {type(condition).__name__}")


def _all_conditions_match(
    conditions: tuple[ConditionSpec, ...],
    previous: dict[str, float | None],
    current: dict[str, float | None],
) -> bool:
    return all(_condition_matches(condition, previous, current) for condition in conditions)


def generate_signals(strategy: StrategySpec, market_data: MarketDataSet) -> SignalSeries:
    """Evaluate a validated strategy over canonical market data.

    This function generates close-of-bar signals only. It does not simulate
    orders or holdings. The execution engine introduced later must apply the
    strategy's explicit next-bar timing contract.
    """

    symbol = strategy.symbols[0]
    if market_data.symbol != symbol:
        raise ValueError(
            f"strategy symbol {symbol!r} does not match market data {market_data.symbol!r}"
        )

    indicator_series: dict[str, tuple[float | None, ...]] = {}
    for indicator in strategy.indicators:
        if isinstance(indicator, SmaIndicator):
            indicator_series[indicator.id] = calculate_sma(market_data.bars, indicator)
        else:
            raise TypeError(f"unsupported indicator type: {type(indicator).__name__}")

    points: list[SignalPoint] = []
    previous_values: dict[str, float | None] | None = None

    for index, bar in enumerate(market_data.bars):
        current_values = {
            indicator_id: values[index]
            for indicator_id, values in indicator_series.items()
        }

        enter_long = False
        exit_long = False
        if previous_values is not None:
            enter_long = _all_conditions_match(
                strategy.entry_conditions, previous_values, current_values
            )
            exit_long = _all_conditions_match(
                strategy.exit_conditions, previous_values, current_values
            )

        points.append(
            SignalPoint(
                timestamp=bar.timestamp,
                indicator_values=current_values,
                enter_long=enter_long,
                exit_long=exit_long,
            )
        )
        previous_values = current_values

    return SignalSeries(symbol=symbol, points=tuple(points))
