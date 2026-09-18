from datetime import UTC, date, datetime, timedelta

import pytest

from backtest_app.domain.market_data import MarketBar, MarketDataMetadata, MarketDataSet
from backtest_app.domain.research import StrategySearchRequest, StrategySearchSpace
from backtest_app.market_data.provider import MarketDataProvider, MarketDataRequest
from backtest_app.services.research import search_strategies


class ResearchProvider(MarketDataProvider):
    def __init__(self) -> None:
        self.requests: list[MarketDataRequest] = []

    @property
    def name(self) -> str:
        return "research-test"

    async def get_history(self, request: MarketDataRequest) -> MarketDataSet:
        self.requests.append(request)
        start = datetime(2023, 1, 1, tzinfo=UTC)
        closes = tuple(
            100 + i * 0.35 + (4 if i % 18 < 9 else -4) for i in range(420)
        )
        bars = tuple(
            MarketBar(
                timestamp=start + timedelta(days=i),
                symbol=request.symbol,
                open=close,
                high=close + 1,
                low=close - 1,
                close=close,
                volume=1000,
            )
            for i, close in enumerate(closes)
            if request.start_date <= (start + timedelta(days=i)).date() <= request.end_date
        )
        return MarketDataSet(
            symbol=request.symbol,
            bars=bars,
            metadata=MarketDataMetadata(
                provider=self.name,
                retrieved_at=datetime(2024, 6, 1, tzinfo=UTC),
            ),
        )


def request() -> StrategySearchRequest:
    return StrategySearchRequest(
        symbol="SPY",
        start_date=date(2023, 3, 1),
        validation_start_date=date(2023, 11, 1),
        end_date=date(2024, 2, 20),
        requested_data_provider="research-test",
        top_n=3,
        search_space=StrategySearchSpace(
            fast_windows=(2, 3),
            slow_windows=(5, 8),
            trend_filter_options=(False, True),
            momentum_windows=(None, 5),
            momentum_thresholds=(0.0,),
            volatility_windows=(None,),
            volatility_thresholds=(0.30,),
        ),
    )


@pytest.mark.asyncio
async def test_search_fetches_market_data_once_and_returns_ranked_holdout_results() -> None:
    provider = ResearchProvider()
    result = await search_strategies(request(), provider)

    assert len(provider.requests) == 1
    assert result.evaluated_candidates == 16
    assert len(result.candidates) == 3
    assert [candidate.rank for candidate in result.candidates] == [1, 2, 3]
    assert result.training_end_date == date(2023, 10, 31)
    assert result.validation_start_date == date(2023, 11, 1)
    assert all(candidate.training.strategy_metrics for candidate in result.candidates)
    assert all(candidate.validation.strategy_metrics for candidate in result.candidates)


@pytest.mark.asyncio
async def test_search_rejects_grid_above_explicit_candidate_cap() -> None:
    provider = ResearchProvider()
    too_large = request().model_copy(update={"max_candidates": 5})

    with pytest.raises(ValueError, match="above max_candidates"):
        await search_strategies(too_large, provider)

    assert provider.requests == []
