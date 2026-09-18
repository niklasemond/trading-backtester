"""Reproducible backtest experiment configuration."""

from __future__ import annotations

from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .strategy import StrategySpec


class CostModel(BaseModel):
    """Simple deterministic transaction-cost assumptions for the first milestone."""

    model_config = ConfigDict(frozen=True)

    commission_type: Literal["fixed_per_order"] = "fixed_per_order"
    commission_amount: float = Field(default=0.0, ge=0.0)
    slippage_bps: float = Field(default=0.0, ge=0.0, lt=10_000.0)


class BacktestConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    start_date: date
    end_date: date
    starting_capital: float = Field(gt=0.0)
    costs: CostModel = Field(default_factory=CostModel)

    @model_validator(mode="after")
    def validate_date_range(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class ExperimentSpec(BaseModel):
    """Input definition for a reproducible experiment.

    Runtime provenance such as actual provider retrieval metadata and the engine
    version belongs on the persisted experiment result, because it is only known
    once a run has been executed.
    """

    model_config = ConfigDict(frozen=True)

    experiment_schema_version: Literal["1.0"] = "1.0"
    strategy: StrategySpec
    backtest: BacktestConfig
    requested_data_provider: str = Field(min_length=1)
