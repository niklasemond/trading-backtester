from datetime import date, datetime, timezone

import pytest

from backtest_app.domain.market_data import MarketBar, MarketDataMetadata, MarketDataSet
from backtest_app.market_data.provider import MarketDataProvider, MarketDataRequest


class DeterministicProvider(MarketDataProvider):
    @property
    def name(self) -> str:
        return "deterministic-test"

    async def get_history(self, request: MarketDataRequest) -> MarketDataSet:
        bars = (
            MarketBar(
                timestamp=datetime(2024, 1, 2, tzinfo=timezone.utc),
                symbol=request.symbol,
                open=100,
                high=101,
                low=99,
                close=100.5,
                volume=1234,
            ),
        )
        return MarketDataSet(
            symbol=request.symbol,
            bars=bars,
            metadata=MarketDataMetadata(
                provider=self.name,
                retrieved_at=datetime(2024, 1, 3, tzinfo=timezone.utc),
            ),
        )


@pytest.mark.asyncio
async def test_provider_returns_canonical_dataset() -> None:
    provider = DeterministicProvider()
    request = MarketDataRequest(
        symbol="SPY",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31),
    )

    result = await provider.get_history(request)

    assert provider.name == "deterministic-test"
    assert result.symbol == "SPY"
    assert result.bars[0].close == 100.5
