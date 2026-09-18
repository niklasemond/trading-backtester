"""Bounded strategy-search request and result models."""

from __future__ import annotations

from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .analytics import PerformanceMetrics
from .experiment import CostModel


class StrategySearchSpace(BaseModel):
    """Small, explicit grid for StrategySpec 1.1 trend-filter research."""

    model_config = ConfigDict(frozen=True)

    fast_windows: tuple[int, ...] = Field(default=(20, 50, 100), min_length=1)
    slow_windows: tuple[int, ...] = Field(default=(100, 150, 200), min_length=1)
    trend_filter_options: tuple[bool, ...] = Field(default=(False, True), min_length=1)
    momentum_windows: tuple[int | None, ...] = Field(default=(None, 63, 126), min_length=1)
    momentum_thresholds: tuple[float, ...] = Field(default=(0.0,), min_length=1)
    volatility_windows: tuple[int | None, ...] = Field(default=(None, 20, 63), min_length=1)
    volatility_thresholds: tuple[float, ...] = Field(default=(0.30, 0.40), min_length=1)
    momentum_exit: bool = True
    volatility_exit: bool = False

    @model_validator(mode="after")
    def validate_values(self) -> Self:
        if any(window <= 0 for window in self.fast_windows + self.slow_windows):
            raise ValueError("SMA windows must be positive")
        if any(window is not None and window <= 0 for window in self.momentum_windows):
            raise ValueError("momentum windows must be positive")
        if any(window is not None and window <= 1 for window in self.volatility_windows):
            raise ValueError("volatility windows must be greater than one")
        if any(value < 0 for value in self.volatility_thresholds):
            raise ValueError("volatility thresholds must be non-negative")
        return self


class StrategySearchRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str = Field(default="SPY", min_length=1)
    start_date: date
    validation_start_date: date
    end_date: date
    starting_capital: float = Field(default=100_000.0, gt=0.0)
    costs: CostModel = Field(default_factory=CostModel)
    requested_data_provider: str = Field(default="yahoo", min_length=1)
    search_space: StrategySearchSpace = Field(default_factory=StrategySearchSpace)
    objective: Literal["total_return", "excess_total_return", "sharpe_ratio", "max_drawdown"] = "excess_total_return"
    top_n: int = Field(default=10, ge=1, le=50)
    max_candidates: int = Field(default=2_000, ge=1, le=10_000)

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if not self.start_date < self.validation_start_date <= self.end_date:
            raise ValueError(
                "validation_start_date must be after start_date and on or before end_date"
            )
        return self


class SearchParameters(BaseModel):
    model_config = ConfigDict(frozen=True)

    fast_window: int
    slow_window: int
    trend_filter: bool
    momentum_window: int | None
    momentum_threshold: float | None
    volatility_window: int | None
    volatility_threshold: float | None
    momentum_exit: bool
    volatility_exit: bool


class SearchPeriodResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    strategy_metrics: PerformanceMetrics
    benchmark_metrics: PerformanceMetrics
    excess_total_return: float


class StrategySearchCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    rank: int
    parameters: SearchParameters
    training: SearchPeriodResult
    validation: SearchPeriodResult
    robustness_score: float
    robustness_label: Literal["positive_both", "mixed", "negative_both", "neutral"]


class StrategySearchResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    objective: str
    training_start_date: date
    training_end_date: date
    validation_start_date: date
    validation_end_date: date
    evaluated_candidates: int
    skipped_candidates: int
    data_provider: str
    candidates: tuple[StrategySearchCandidate, ...]
