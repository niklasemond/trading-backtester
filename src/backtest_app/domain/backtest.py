"""Backtest execution and portfolio-accounting outputs."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class TradeSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class CorporateActionType(StrEnum):
    DIVIDEND = "dividend"
    SPLIT = "split"


class CorporateActionRecord(BaseModel):
    """One corporate action actually applied to an open portfolio position."""

    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    action_type: CorporateActionType
    quantity_before: float = Field(ge=0.0)
    quantity_after: float = Field(ge=0.0)
    cash_flow: float = Field(ge=0.0)
    cash_after: float
    dividend_per_share: float | None = Field(default=None, ge=0.0)
    split_ratio: float | None = Field(default=None, gt=0.0)


class TradeRecord(BaseModel):
    """One executed order/fill in the deterministic single-asset simulator."""

    model_config = ConfigDict(frozen=True)

    side: TradeSide
    signal_timestamp: datetime
    execution_timestamp: datetime
    reference_open: float = Field(gt=0.0)
    fill_price: float = Field(gt=0.0)
    quantity: float = Field(gt=0.0)
    commission: float = Field(ge=0.0)
    slippage_cost: float = Field(ge=0.0)
    cash_after: float
    position_after: float = Field(ge=0.0)


class EquityPoint(BaseModel):
    """End-of-bar marked-to-market portfolio state."""

    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    cash: float
    position_quantity: float = Field(ge=0.0)
    close_price: float = Field(gt=0.0)
    equity: float


class BacktestResult(BaseModel):
    """Core execution result before performance analytics are added."""

    model_config = ConfigDict(frozen=True)

    engine_version: str
    symbol: str
    starting_capital: float = Field(gt=0.0)
    final_cash: float
    final_position_quantity: float = Field(ge=0.0)
    trades: tuple[TradeRecord, ...]
    equity_curve: tuple[EquityPoint, ...]
    corporate_actions: tuple[CorporateActionRecord, ...] = ()
