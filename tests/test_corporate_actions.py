from datetime import UTC, date, datetime, timedelta

import pytest

from backtest_app.analytics.engine import analyze_backtest, create_buy_and_hold_benchmark
from backtest_app.domain.backtest import CorporateActionType
from backtest_app.domain.experiment import BacktestConfig
from backtest_app.domain.market_data import MarketBar, MarketDataMetadata, MarketDataSet
from backtest_app.domain.signals import SignalPoint, SignalSeries
from backtest_app.domain.strategy import (
    CrossoverCondition,
    IndicatorRef,
    SmaIndicator,
    StrategySpec,
)
from backtest_app.execution.engine import simulate_execution


def strategy() -> StrategySpec:
    fast = IndicatorRef(id="fast")
    slow = IndicatorRef(id="slow")
    return StrategySpec(
        name="corporate action fixture",
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


def market(
    *,
    prices: tuple[float, ...],
    dividends: dict[int, float] | None = None,
    splits: dict[int, float] | None = None,
) -> MarketDataSet:
    dividends = dividends or {}
    splits = splits or {}
    start = datetime(2024, 1, 2, tzinfo=UTC)
    bars = tuple(
        MarketBar(
            timestamp=start + timedelta(days=index),
            symbol="SPY",
            open=price,
            high=price,
            low=price,
            close=price,
            volume=1_000,
            dividend=dividends.get(index),
            split_ratio=splits.get(index),
        )
        for index, price in enumerate(prices)
    )
    return MarketDataSet(
        symbol="SPY",
        bars=bars,
        metadata=MarketDataMetadata(
            provider="deterministic-test",
            retrieved_at=datetime(2024, 1, 1, tzinfo=UTC),
        ),
    )


def signals(data: MarketDataSet, entry_index: int = 0) -> SignalSeries:
    return SignalSeries(
        symbol=data.symbol,
        points=tuple(
            SignalPoint(
                timestamp=bar.timestamp,
                enter_long=index == entry_index,
            )
            for index, bar in enumerate(data.bars)
        ),
    )


def config(data: MarketDataSet, capital: float) -> BacktestConfig:
    return BacktestConfig(
        start_date=data.bars[0].timestamp.date(),
        end_date=data.bars[-1].timestamp.date(),
        starting_capital=capital,
    )


def test_dividend_credits_cash_equity_metrics_and_benchmark_consistently() -> None:
    data = market(prices=(10.0, 10.0, 10.0), dividends={2: 1.0})
    cfg = config(data, 100.0)
    spec = strategy()

    result = simulate_execution(spec, cfg, data, signals(data))
    analysis = analyze_backtest(result, spec, cfg, data)

    assert result.trades[0].quantity == 10.0
    assert result.final_cash == pytest.approx(10.0)
    assert result.equity_curve[-1].cash == pytest.approx(10.0)
    assert result.equity_curve[-1].equity == pytest.approx(110.0)
    assert analysis.strategy_metrics.total_return == pytest.approx(0.10)

    assert len(result.corporate_actions) == 1
    action = result.corporate_actions[0]
    assert action.action_type == CorporateActionType.DIVIDEND
    assert action.dividend_per_share == 1.0
    assert action.cash_flow == pytest.approx(10.0)

    benchmark = analysis.benchmark
    assert benchmark.equity_curve[-1].cash == pytest.approx(10.0)
    assert benchmark.equity_curve[-1].equity == pytest.approx(110.0)
    assert analysis.benchmark_metrics.total_return == pytest.approx(0.10)
    assert benchmark.corporate_actions[0].cash_flow == pytest.approx(10.0)


def test_split_adjusts_quantity_without_creating_or_destroying_value() -> None:
    data = market(prices=(100.0, 100.0, 50.0), splits={2: 2.0})
    cfg = config(data, 1_000.0)
    spec = strategy()

    result = simulate_execution(spec, cfg, data, signals(data))
    analysis = analyze_backtest(result, spec, cfg, data)

    assert result.trades[0].quantity == 10.0
    assert result.final_position_quantity == pytest.approx(20.0)
    assert result.equity_curve[1].equity == pytest.approx(1_000.0)
    assert result.equity_curve[2].position_quantity == pytest.approx(20.0)
    assert result.equity_curve[2].equity == pytest.approx(1_000.0)
    assert analysis.strategy_metrics.total_return == pytest.approx(0.0)

    action = result.corporate_actions[0]
    assert action.action_type == CorporateActionType.SPLIT
    assert action.quantity_before == pytest.approx(10.0)
    assert action.quantity_after == pytest.approx(20.0)
    assert action.cash_flow == 0.0

    benchmark = analysis.benchmark
    assert benchmark.quantity == pytest.approx(10.0)
    assert benchmark.final_quantity == pytest.approx(20.0)
    assert benchmark.equity_curve[-1].equity == pytest.approx(1_000.0)
    assert analysis.benchmark_metrics.total_return == pytest.approx(0.0)


def test_event_date_actions_apply_before_orders_at_that_open() -> None:
    data = market(prices=(10.0, 10.0, 10.0), dividends={1: 1.0})
    cfg = config(data, 100.0)
    spec = strategy()

    # Signal on day 0 buys at day 1 open. Because the dividend event is treated
    # as an ex-date entitlement, a position opened on day 1 does not receive it.
    result = simulate_execution(spec, cfg, data, signals(data))

    assert result.final_cash == pytest.approx(0.0)
    assert result.corporate_actions == ()

    # The benchmark bought on day 0, so it is entitled on day 1.
    benchmark = create_buy_and_hold_benchmark(spec, cfg, data)
    assert benchmark.equity_curve[-1].cash == pytest.approx(10.0)
    assert benchmark.corporate_actions[0].action_type == CorporateActionType.DIVIDEND
