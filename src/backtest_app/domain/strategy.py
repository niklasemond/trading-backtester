"""Versioned, declarative strategy intermediate representation."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Frequency(StrEnum):
    DAILY = "1d"


class PriceField(StrEnum):
    OPEN = "open"
    HIGH = "high"
    LOW = "low"
    CLOSE = "close"
    ADJUSTED_CLOSE = "adjusted_close"


class SmaIndicator(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["sma"] = "sma"
    id: str = Field(min_length=1, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    source: PriceField = PriceField.CLOSE
    window: int = Field(gt=0)


class RocIndicator(BaseModel):
    """Trailing price rate of change over ``window`` observations."""

    model_config = ConfigDict(frozen=True)
    type: Literal["roc"] = "roc"
    id: str = Field(min_length=1, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    source: PriceField = PriceField.CLOSE
    window: int = Field(gt=0)


class VolatilityIndicator(BaseModel):
    """Annualized sample volatility of trailing arithmetic daily returns."""

    model_config = ConfigDict(frozen=True)
    type: Literal["volatility"] = "volatility"
    id: str = Field(min_length=1, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    source: PriceField = PriceField.CLOSE
    window: int = Field(gt=1)
    annualization_factor: int = Field(default=252, gt=0)


IndicatorSpec = Annotated[
    SmaIndicator | RocIndicator | VolatilityIndicator,
    Field(discriminator="type"),
]


class IndicatorRef(BaseModel):
    model_config = ConfigDict(frozen=True)
    kind: Literal["indicator"] = "indicator"
    id: str = Field(min_length=1)


class PriceRef(BaseModel):
    model_config = ConfigDict(frozen=True)
    kind: Literal["price"] = "price"
    field: PriceField = PriceField.CLOSE


class ConstantRef(BaseModel):
    model_config = ConfigDict(frozen=True)
    kind: Literal["constant"] = "constant"
    value: float


ValueRef = Annotated[
    IndicatorRef | PriceRef | ConstantRef,
    Field(discriminator="kind"),
]


class CrossoverCondition(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["crossover"] = "crossover"
    left: IndicatorRef
    operator: Literal["crosses_above", "crosses_below"]
    right: IndicatorRef


class ComparisonCondition(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["comparison"] = "comparison"
    left: ValueRef
    operator: Literal["above", "below", "at_or_above", "at_or_below"]
    right: ValueRef


ConditionSpec = Annotated[
    CrossoverCondition | ComparisonCondition,
    Field(discriminator="type"),
]


class PositionSizingSpec(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["all_in"] = "all_in"
    cash_buffer_fraction: float = Field(default=0.0, ge=0.0, lt=1.0)
    allow_fractional_shares: bool = False


class ExecutionTimingSpec(BaseModel):
    """Timing assumptions that prevent ambiguous same-bar execution."""

    model_config = ConfigDict(frozen=True)
    signal_price: Literal["close"] = "close"
    execution_bar: Literal["next_bar"] = "next_bar"
    execution_price: Literal["open"] = "open"


class StrategySpec(BaseModel):
    """Validated strategy IR consumed by the backtesting engine."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["1.0", "1.1"] = "1.0"
    name: str = Field(min_length=1)
    symbols: tuple[str, ...] = Field(min_length=1, max_length=1)
    frequency: Frequency = Frequency.DAILY
    direction: Literal["long_only"] = "long_only"
    indicators: tuple[IndicatorSpec, ...] = Field(min_length=1)
    entry_conditions: tuple[ConditionSpec, ...] = Field(min_length=1)
    exit_conditions: tuple[ConditionSpec, ...] = Field(min_length=1)
    entry_logic: Literal["all", "any"] = "all"
    exit_logic: Literal["all", "any"] = "all"
    position_sizing: PositionSizingSpec = Field(default_factory=PositionSizingSpec)
    execution: ExecutionTimingSpec = Field(default_factory=ExecutionTimingSpec)

    @model_validator(mode="after")
    def validate_strategy(self) -> Self:
        ids = [indicator.id for indicator in self.indicators]
        if len(ids) != len(set(ids)):
            raise ValueError("indicator ids must be unique")

        known = set(ids)
        for condition in (*self.entry_conditions, *self.exit_conditions):
            for ref in (condition.left, condition.right):
                if isinstance(ref, IndicatorRef) and ref.id not in known:
                    raise ValueError(f"condition references unknown indicator: {ref.id}")

        if self.schema_version == "1.0":
            if any(not isinstance(i, SmaIndicator) for i in self.indicators):
                raise ValueError("StrategySpec 1.0 supports SMA indicators only")
            if any(
                not isinstance(c, CrossoverCondition)
                for c in (*self.entry_conditions, *self.exit_conditions)
            ):
                raise ValueError("StrategySpec 1.0 supports crossover conditions only")
            if self.entry_logic != "all" or self.exit_logic != "all":
                raise ValueError("StrategySpec 1.0 supports all-condition logic only")
        return self
