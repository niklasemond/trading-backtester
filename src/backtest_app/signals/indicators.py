"""Deterministic indicator calculations over canonical market bars."""

from __future__ import annotations

from collections.abc import Sequence
from math import sqrt
from statistics import stdev

from backtest_app.domain.market_data import MarketBar
from backtest_app.domain.strategy import PriceField, RocIndicator, SmaIndicator, VolatilityIndicator


def simple_moving_average(values: Sequence[float], window: int) -> tuple[float | None, ...]:
    if window <= 0:
        raise ValueError("SMA window must be positive")
    output: list[float | None] = []
    rolling_sum = 0.0
    for index, value in enumerate(values):
        rolling_sum += float(value)
        if index >= window:
            rolling_sum -= float(values[index - window])
        output.append(None if index + 1 < window else rolling_sum / window)
    return tuple(output)


def rate_of_change(values: Sequence[float], window: int) -> tuple[float | None, ...]:
    """Return price[t] / price[t-window] - 1 without future observations."""
    if window <= 0:
        raise ValueError("ROC window must be positive")
    output: list[float | None] = []
    for index, value in enumerate(values):
        if index < window:
            output.append(None)
            continue
        previous = float(values[index - window])
        output.append(float(value) / previous - 1.0)
    return tuple(output)


def rolling_volatility(
    values: Sequence[float], window: int, annualization_factor: int = 252
) -> tuple[float | None, ...]:
    """Annualized sample volatility of the trailing window daily returns."""
    if window <= 1:
        raise ValueError("volatility window must be greater than one")
    returns = [
        float(values[i]) / float(values[i - 1]) - 1.0
        for i in range(1, len(values))
    ]
    output: list[float | None] = []
    for index in range(len(values)):
        if index < window:
            output.append(None)
            continue
        sample = returns[index - window:index]
        output.append(stdev(sample) * sqrt(annualization_factor))
    return tuple(output)


def indicator_source_values(
    bars: Sequence[MarketBar], source: PriceField
) -> tuple[float, ...]:
    values: list[float] = []
    for bar in bars:
        value = getattr(bar, source.value)
        if value is None:
            raise ValueError(
                f"indicator source {source.value!r} is unavailable at "
                f"{bar.timestamp.isoformat()}"
            )
        values.append(float(value))
    return tuple(values)


def calculate_sma(
    bars: Sequence[MarketBar], indicator: SmaIndicator
) -> tuple[float | None, ...]:
    return simple_moving_average(
        indicator_source_values(bars, indicator.source), indicator.window
    )


def calculate_roc(
    bars: Sequence[MarketBar], indicator: RocIndicator
) -> tuple[float | None, ...]:
    return rate_of_change(
        indicator_source_values(bars, indicator.source), indicator.window
    )


def calculate_volatility(
    bars: Sequence[MarketBar], indicator: VolatilityIndicator
) -> tuple[float | None, ...]:
    return rolling_volatility(
        indicator_source_values(bars, indicator.source),
        indicator.window,
        indicator.annualization_factor,
    )
