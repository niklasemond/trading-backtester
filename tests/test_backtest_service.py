from datetime import UTC, date, datetime, timedelta

import pytest

from backtest_app.domain.experiment import BacktestConfig, ExperimentSpec
from backtest_app.domain.market_data import MarketBar, MarketDataMetadata, MarketDataSet
from backtest_app.domain.strategy import (
    CrossoverCondition,
    IndicatorRef,
    SmaIndicator,
    StrategySpec,
)
from backtest_app.market_data.provider import MarketDataProvider, MarketDataRequest
from backtest_app.services.backtests import execute_experiment, required_warmup_bars


class FilteringProvider(MarketDataProvider):
    def __init__(self) -> None:
        self.requests: list[MarketDataRequest] = []
        start = datetime(2024, 1, 1, tzinfo=UTC)
        closes = (10.0, 9.0, 8.0, 11.0, 10.0, 9.0)
        opens = (10.0, 9.0, 8.0, 11.0, 20.0, 9.0)
        self._bars = tuple(
            MarketBar(
                timestamp=start + timedelta(days=i),
                symbol="SPY",
                open=o,
                high=max(o, c) + 1,
                low=min(o, c) * 0.9,
                close=c,
                volume=1000,
            )
            for i, (o, c) in enumerate(zip(opens, closes, strict=True))
        )

    @property
    def name(self) -> str:
        return "filtering-test"

    async def get_history(self, request: MarketDataRequest) -> MarketDataSet:
        self.requests.append(request)
        bars = tuple(
            bar
            for bar in self._bars
            if request.start_date <= bar.timestamp.date() <= request.end_date
        )
        return MarketDataSet(
            symbol=request.symbol,
            bars=bars,
            metadata=MarketDataMetadata(
                provider=self.name,
                retrieved_at=datetime(2024, 2, 1, tzinfo=UTC),
            ),
        )


def strategy() -> StrategySpec:
    fast = IndicatorRef(id="fast")
    slow = IndicatorRef(id="slow")
    return StrategySpec(
        name="2/3 warmup test",
        symbols=("SPY",),
        indicators=(
            SmaIndicator(id="fast", window=2),
            SmaIndicator(id="slow", window=3),
        ),
        entry_conditions=(
            CrossoverCondition(left=fast, operator="crosses_above", right=slow),
        ),
        exit_conditions=(
            CrossoverCondition(left=fast, operator="crosses_below", right=slow),
        ),
    )


def experiment() -> ExperimentSpec:
    return ExperimentSpec(
        strategy=strategy(),
        backtest=BacktestConfig(
            start_date=date(2024, 1, 4),
            end_date=date(2024, 1, 6),
            starting_capital=1000,
        ),
        requested_data_provider="filtering-test",
    )


def test_required_warmup_uses_largest_indicator_window() -> None:
    assert required_warmup_bars(strategy()) == 3


@pytest.mark.asyncio
async def test_service_fetches_pre_start_bars_but_keeps_portfolio_in_range() -> None:
    provider = FilteringProvider()

    completed = await execute_experiment(experiment(), provider)

    assert provider.requests[0].start_date < experiment().backtest.start_date
    assert completed.execution.trades[0].signal_timestamp.date() == date(2024, 1, 4)
    assert completed.execution.trades[0].execution_timestamp.date() == date(2024, 1, 5)
    assert all(
        point.timestamp.date() >= experiment().backtest.start_date
        for point in completed.execution.equity_curve
    )
    assert completed.analysis.benchmark.equity_curve[0].timestamp.date() == date(2024, 1, 4)


@pytest.mark.asyncio
async def test_pre_start_warmup_never_creates_pre_period_trade() -> None:
    provider = FilteringProvider()
    completed = await execute_experiment(experiment(), provider)

    assert all(
        trade.execution_timestamp.date() >= experiment().backtest.start_date
        for trade in completed.execution.trades
    )
