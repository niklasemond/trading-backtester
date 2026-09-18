from datetime import UTC, date, datetime, timedelta
from math import sqrt
from statistics import stdev

import pytest

from backtest_app.analytics.engine import (
    analyze_backtest,
    calculate_metrics,
    create_buy_and_hold_benchmark,
)
from backtest_app.domain.backtest import BacktestResult, EquityPoint, TradeRecord, TradeSide
from backtest_app.domain.experiment import BacktestConfig, CostModel
from backtest_app.domain.market_data import MarketBar, MarketDataMetadata, MarketDataSet
from backtest_app.domain.strategy import (
    CrossoverCondition,
    IndicatorRef,
    PositionSizingSpec,
    SmaIndicator,
    StrategySpec,
)


def equity(values: tuple[float, ...]) -> tuple[EquityPoint, ...]:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    return tuple(
        EquityPoint(
            timestamp=start + timedelta(days=index),
            cash=value,
            position_quantity=0,
            close_price=100,
            equity=value,
        )
        for index, value in enumerate(values)
    )


def spec(*, fractional: bool = False, buffer: float = 0.0) -> StrategySpec:
    fast = IndicatorRef(id="fast")
    slow = IndicatorRef(id="slow")
    return StrategySpec(
        name="test",
        symbols=("SPY",),
        indicators=(SmaIndicator(id="fast", window=2), SmaIndicator(id="slow", window=3)),
        entry_conditions=(CrossoverCondition(left=fast, operator="crosses_above", right=slow),),
        exit_conditions=(CrossoverCondition(left=fast, operator="crosses_below", right=slow),),
        position_sizing=PositionSizingSpec(
            allow_fractional_shares=fractional,
            cash_buffer_fraction=buffer,
        ),
    )


def data(opens: tuple[float, ...], closes: tuple[float, ...]) -> MarketDataSet:
    start = datetime(2024, 1, 2, tzinfo=UTC)
    bars = tuple(
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
    return MarketDataSet(
        symbol="SPY",
        bars=bars,
        metadata=MarketDataMetadata(
            provider="test",
            retrieved_at=datetime(2024, 1, 1, tzinfo=UTC),
        ),
    )


def test_total_return_and_max_drawdown_are_calculated_from_starting_capital() -> None:
    metrics = calculate_metrics(100.0, equity((110.0, 121.0, 90.75, 99.825)))

    assert metrics.total_return == pytest.approx(-0.00175)
    assert metrics.max_drawdown == pytest.approx(0.25)


def test_volatility_and_sharpe_use_daily_returns_and_252_day_annualization() -> None:
    curve = equity((110.0, 110.0, 121.0))
    metrics = calculate_metrics(100.0, curve)
    returns = [0.10, 0.0, 0.10]
    daily_std = stdev(returns)

    assert metrics.annualized_volatility == pytest.approx(daily_std * sqrt(252))
    assert metrics.sharpe_ratio == pytest.approx((sum(returns) / 3) / daily_std * sqrt(252))


def test_zero_volatility_has_no_sharpe_ratio() -> None:
    metrics = calculate_metrics(100.0, equity((100.0, 100.0, 100.0)))

    assert metrics.annualized_volatility == 0.0
    assert metrics.sharpe_ratio is None


def test_cagr_uses_actual_calendar_elapsed_time() -> None:
    curve = (
        EquityPoint(timestamp=datetime(2024, 1, 1, tzinfo=UTC), cash=100, position_quantity=0, close_price=100, equity=100),
        EquityPoint(timestamp=datetime(2025, 1, 1, tzinfo=UTC), cash=121, position_quantity=0, close_price=100, equity=121),
    )
    metrics = calculate_metrics(100.0, curve)

    expected = (1.21 ** (365.25 / 366)) - 1
    assert metrics.cagr == pytest.approx(expected)


def test_buy_and_hold_enters_first_in_range_open_with_same_costs() -> None:
    market = data((10.0, 12.0, 15.0), (11.0, 13.0, 14.0))
    config = BacktestConfig(
        start_date=date(2024, 1, 2),
        end_date=date(2024, 1, 4),
        starting_capital=100.0,
        costs=CostModel(commission_amount=1.0, slippage_bps=100.0),
    )

    benchmark = create_buy_and_hold_benchmark(spec(), config, market)

    assert benchmark.entry_price == pytest.approx(10.1)
    assert benchmark.quantity == 9.0
    assert benchmark.equity_curve[0].cash == pytest.approx(8.1)
    assert benchmark.equity_curve[-1].equity == pytest.approx(134.1)


def test_buy_and_hold_respects_fractional_sizing_and_cash_buffer() -> None:
    market = data((10.0, 10.0), (10.0, 11.0))
    config = BacktestConfig(
        start_date=date(2024, 1, 2),
        end_date=date(2024, 1, 3),
        starting_capital=100.0,
    )

    benchmark = create_buy_and_hold_benchmark(
        spec(fractional=True, buffer=0.10), config, market
    )

    assert benchmark.quantity == pytest.approx(9.0)
    assert benchmark.equity_curve[0].cash == pytest.approx(10.0)


def test_analysis_counts_completed_round_trips_not_open_entry() -> None:
    market = data((10.0, 10.0, 10.0), (10.0, 10.0, 10.0))
    config = BacktestConfig(
        start_date=date(2024, 1, 2),
        end_date=date(2024, 1, 4),
        starting_capital=100.0,
    )
    ts = [bar.timestamp for bar in market.bars]
    result = BacktestResult(
        engine_version="test",
        symbol="SPY",
        starting_capital=100.0,
        final_cash=0.0,
        final_position_quantity=10.0,
        trades=(
            TradeRecord(
                side=TradeSide.BUY,
                signal_timestamp=ts[0],
                execution_timestamp=ts[1],
                reference_open=10,
                fill_price=10,
                quantity=10,
                commission=0,
                slippage_cost=0,
                cash_after=0,
                position_after=10,
            ),
        ),
        equity_curve=equity((100.0, 100.0, 100.0)),
    )

    analysis = analyze_backtest(result, spec(), config, market)

    assert analysis.strategy_metrics.number_of_trades == 0
    assert analysis.benchmark_metrics.number_of_trades == 1
