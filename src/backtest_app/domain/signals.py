"""Signal-generation outputs produced from validated strategy specifications."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SignalPoint(BaseModel):
    """Strategy state at one market-data bar.

    A signal point is informational only. Execution is deliberately handled by a
    later component so that a close-derived signal cannot accidentally trade on
    the same bar.
    """

    model_config = ConfigDict(frozen=True)

    timestamp: datetime
    indicator_values: dict[str, float | None] = Field(default_factory=dict)
    enter_long: bool = False
    exit_long: bool = False


class SignalSeries(BaseModel):
    """Ordered signal output for one single-asset strategy evaluation."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    points: tuple[SignalPoint, ...]
