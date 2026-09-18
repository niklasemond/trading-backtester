"""HTTP API request and response schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backtest_app.domain.analytics import BacktestAnalysis
from backtest_app.domain.backtest import BacktestResult
from backtest_app.domain.experiment import ExperimentSpec


class HealthResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str = "ok"
    api_version: str = "1"


class BacktestResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    experiment: ExperimentSpec
    execution: BacktestResult
    analysis: BacktestAnalysis
    data_provider: str
