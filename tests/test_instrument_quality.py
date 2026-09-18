from datetime import UTC, date, datetime, timedelta

import pytest

from backtest_app.domain.market_data import MarketBar, MarketDataMetadata, MarketDataSet
from backtest_app.market_data.instruments import BUILT_IN_INSTRUMENTS, BUILT_IN_SYMBOLS
from backtest_app.market_data.provider import MarketDataProvider, MarketDataRequest
from backtest_app.market_data.quality import validate_instrument_history


class CatalogFixtureProvider(MarketDataProvider):
    @property
    def name(self) -> str:
        return "fixture"

    async def get_history(self, request: MarketDataRequest) -> MarketDataSet:
        start = datetime.combine(request.start_date, datetime.min.time(), tzinfo=UTC)
        bars = tuple(
            MarketBar(
                timestamp=start + timedelta(days=i),
                symbol=request.symbol,
                open=100 + i,
                high=101 + i,
                low=99 + i,
                close=100.5 + i,
                volume=1_000,
                adjusted_close=100.5 + i,
                dividend=0.5 if i == 1 else None,
            )
            for i in range(3)
        )
        return MarketDataSet(
            symbol=request.symbol,
            bars=bars,
            metadata=MarketDataMetadata(
                provider=self.name,
                retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
                notes={"daily_bar_completion_policy": "fixture completed bars"},
            ),
        )


def test_builtin_instrument_catalog_is_unique_and_expected() -> None:
    assert BUILT_IN_SYMBOLS == ("SPY", "QQQ", "IWM", "TLT", "GLD", "EFA", "EEM", "HYG")
    assert len(BUILT_IN_SYMBOLS) == len(set(BUILT_IN_SYMBOLS))
    assert all(item.name and item.category and item.research_use for item in BUILT_IN_INSTRUMENTS)


@pytest.mark.asyncio
@pytest.mark.parametrize("instrument", BUILT_IN_INSTRUMENTS)
async def test_quality_report_runs_for_every_builtin_instrument(instrument) -> None:
    report = await validate_instrument_history(
        CatalogFixtureProvider(),
        instrument,
        start_date=date(2025, 1, 2),
        end_date=date(2025, 1, 4),
    )

    assert report.symbol == instrument.symbol
    assert report.provider == "fixture"
    assert report.bars == 3
    assert report.dividend_events == 1
    assert report.split_events == 0
    assert report.adjusted_close_coverage == 1.0
    assert report.daily_bar_completion_policy_present is True
