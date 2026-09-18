"""Reusable market-data quality checks for built-in instrument validation."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from backtest_app.market_data.instruments import InstrumentDefinition
from backtest_app.market_data.provider import MarketDataProvider, MarketDataRequest


class InstrumentQualityReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    provider: str
    bars: int = Field(gt=0)
    first_date: date
    last_date: date
    dividend_events: int = Field(ge=0)
    split_events: int = Field(ge=0)
    adjusted_close_coverage: float = Field(ge=0.0, le=1.0)
    daily_bar_completion_policy_present: bool


async def validate_instrument_history(
    provider: MarketDataProvider,
    instrument: InstrumentDefinition,
    *,
    start_date: date,
    end_date: date,
) -> InstrumentQualityReport:
    """Fetch one instrument and summarize provider/canonical-data quality.

    Structural invariants such as timezone-aware timestamps, valid OHLC ranges,
    strict ordering, duplicate prevention, and symbol consistency are enforced by
    the canonical MarketDataSet/MarketBar models before this function receives data.
    """

    data = await provider.get_history(
        MarketDataRequest(
            symbol=instrument.symbol,
            start_date=start_date,
            end_date=end_date,
        )
    )
    if not data.bars:
        raise ValueError(f"no daily bars returned for {instrument.symbol}")

    adjusted = sum(bar.adjusted_close is not None for bar in data.bars)
    return InstrumentQualityReport(
        symbol=data.symbol,
        provider=data.metadata.provider,
        bars=len(data.bars),
        first_date=data.bars[0].timestamp.date(),
        last_date=data.bars[-1].timestamp.date(),
        dividend_events=sum(bar.dividend is not None for bar in data.bars),
        split_events=sum(bar.split_ratio is not None for bar in data.bars),
        adjusted_close_coverage=adjusted / len(data.bars),
        daily_bar_completion_policy_present=(
            "daily_bar_completion_policy" in data.metadata.notes
        ),
    )
