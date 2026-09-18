"""Provider boundary for historical market data."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backtest_app.domain.market_data import MarketDataSet
from backtest_app.domain.strategy import Frequency


class MarketDataRequest(BaseModel):
    """Provider-neutral historical data request."""

    model_config = ConfigDict(frozen=True)

    symbol: str = Field(min_length=1)
    start_date: date
    end_date: date
    frequency: Frequency = Frequency.DAILY

    @model_validator(mode="after")
    def validate_date_range(self) -> "MarketDataRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class MarketDataProvider(ABC):
    """Abstract source of canonical historical market data.

    Provider implementations own downloading, source-specific normalization,
    corporate-action field mapping, caching, and provenance capture. Consumers
    only receive a canonical ``MarketDataSet``.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable provider identifier persisted with experiment results."""

    @abstractmethod
    async def get_history(self, request: MarketDataRequest) -> MarketDataSet:
        """Fetch and normalize historical data for one instrument."""
