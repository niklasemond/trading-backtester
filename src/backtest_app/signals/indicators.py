"""Deterministic indicator calculations over canonical market bars."""

from __future__ import annotations

from collections.abc import Sequence

from backtest_app.domain.market_data import MarketBar
from backtest_app.domain.strategy import PriceField, SmaIndicator


def simple_moving_average(
    values: Sequence[float], window: int
) -> tuple[float | None, ...]:
    """Return a trailing SMA using only the current and prior observations.

    Values before a complete window exists are represented by ``None``. The
    implementation is intentionally small and dependency-free so timing
    semantics remain easy to inspect and test.
    """

    if window <= 0:
        raise ValueError("SMA window must be positive")

    output: list[float | None] = []
    rolling_sum = 0.0

    for index, value in enumerate(values):
        rolling_sum += float(value)
        if index >= window:
            rolling_sum -= float(values[index - window])

        if index + 1 < window:
            output.append(None)
        else:
            output.append(rolling_sum / window)

    return tuple(output)


def indicator_source_values(
    bars: Sequence[MarketBar], source: PriceField
) -> tuple[float, ...]:
    """Extract one numeric source field from canonical bars.

    ``adjusted_close`` is optional in the canonical model, so requesting it for
    a dataset that does not contain it is an explicit error rather than a silent
    fallback to close.
    """

    values: list[float] = []
    for bar in bars:
        value = getattr(bar, source.value)
        if value is None:
            raise ValueError(
                f"indicator source {source.value!r} is unavailable at {bar.timestamp.isoformat()}"
            )
        values.append(float(value))
    return tuple(values)


def calculate_sma(
    bars: Sequence[MarketBar], indicator: SmaIndicator
) -> tuple[float | None, ...]:
    """Calculate an SMA specification over canonical bars."""

    values = indicator_source_values(bars, indicator.source)
    return simple_moving_average(values, indicator.window)
