"""Performance analytics and benchmark outputs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .backtest import EquityPoint


class PerformanceMetrics(BaseModel):
    """Standard first-milestone performance statistics.

    Return-like values are decimal fractions: ``0.10`` means 10%.
    ``cagr`` and ``sharpe_ratio`` are nullable when they are not mathematically
    meaningful for the available observations.
    """

    model_config = ConfigDict(frozen=True)

    total_return: float
    cagr: float | None
    annualized_volatility: float | None = Field(default=None, ge=0.0)
    sharpe_ratio: float | None
    max_drawdown: float = Field(ge=0.0)
    number_of_trades: int = Field(ge=0)


class BenchmarkResult(BaseModel):
    """Executable buy-and-hold benchmark using the run's cost assumptions."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    starting_capital: float = Field(gt=0.0)
    quantity: float = Field(ge=0.0)
    entry_price: float | None = Field(default=None, gt=0.0)
    commission: float = Field(ge=0.0)
    equity_curve: tuple[EquityPoint, ...]


class BacktestAnalysis(BaseModel):
    """Analytics attached to one completed execution result."""

    model_config = ConfigDict(frozen=True)

    strategy_metrics: PerformanceMetrics
    benchmark: BenchmarkResult
    benchmark_metrics: PerformanceMetrics
