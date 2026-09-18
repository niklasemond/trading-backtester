"""Canonical internal market-data representation."""

from __future__ import annotations

from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MarketBar(BaseModel):
    """One canonical OHLCV bar.

    Timestamps must be timezone-aware. Providers are responsible for converting
    their source data into this representation before returning it to the rest
    of the application.
    """

    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    symbol: str = Field(min_length=1)
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: int = Field(ge=0)
    adjusted_close: float | None = Field(default=None, gt=0)
    dividend: float | None = Field(default=None, ge=0)
    split_ratio: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_bar(self) -> Self:
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("market-data timestamps must be timezone-aware")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be >= open, close, and low")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be <= open, close, and high")
        return self


class MarketDataMetadata(BaseModel):
    """Provenance needed to understand and later reproduce a data retrieval."""

    model_config = ConfigDict(frozen=True)

    provider: str = Field(min_length=1)
    retrieved_at: datetime
    provider_version: str | None = None
    dataset_id: str | None = None
    raw_data_fingerprint: str | None = None
    notes: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_retrieval_time(self) -> Self:
        if self.retrieved_at.tzinfo is None or self.retrieved_at.utcoffset() is None:
            raise ValueError("retrieved_at must be timezone-aware")
        return self


class MarketDataSet(BaseModel):
    """A validated, ordered collection of canonical bars."""

    model_config = ConfigDict(frozen=True)

    symbol: str = Field(min_length=1)
    bars: tuple[MarketBar, ...]
    metadata: MarketDataMetadata

    @model_validator(mode="after")
    def validate_dataset(self) -> Self:
        previous: datetime | None = None
        seen: set[datetime] = set()
        for bar in self.bars:
            if bar.symbol != self.symbol:
                raise ValueError("all bars must match the dataset symbol")
            if bar.timestamp in seen:
                raise ValueError("duplicate market-data timestamps are not allowed")
            if previous is not None and bar.timestamp <= previous:
                raise ValueError("bars must be strictly ordered by timestamp")
            seen.add(bar.timestamp)
            previous = bar.timestamp
        return self
