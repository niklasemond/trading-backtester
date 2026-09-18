from datetime import UTC, date, datetime, timedelta

import pytest

from backtest_app.domain.backtest import TradeSide
from backtest_app.domain.experiment import BacktestConfig, CostModel
from backtest_app.domain.market_data import MarketBar, MarketDataMetadata, MarketDataSet
from backtest_app.domain.strategy import (
    CrossoverCondition,
    IndicatorRef,
    PositionSizingSpec,
    SmaIndicator,
    StrategySpec,
)
from backtest_app.execution.engine import run_backtest


def make_market_data(
    closes: tuple[float, ...],
    opens: tuple[float, ...] | None = None,
    symbol: str = "SPY",
) -> MarketDataSet:
    if opens is None:
        opens = closes
    assert len(opens) == len(closes)

    start = datetime(2024, 1, 2, tzinfo=UTC)
    bars = []
    for index, (open_price, close_price) in enumerate(zip(opens, closes, strict=True)):
        high = max(open_price, close_price) + 1
        low = min(open_price, close_price) * 0.5
        bars.append(
            MarketBar(
                timestamp=start + timedelta(days=index),
                symbol=symbol,
                open=open_price,
                high=high,
                low=low,
                close=close_price,
                volume=1_000,
            )
        )

    return MarketDataSet(
        symbol=symbol,
        bars=tuple(bars),
        metadata=MarketDataMetadata(
            provider="deterministic-test",
            retrieved_at=datetime(2024, 1, 1, tzinfo=UTC),
        ),
    )


def crossover_spec(
    *,
    cash_buffer_fraction: float = 0.0,
    allow_fractional_shares: bool = False,
) -> StrategySpec:
    fast = IndicatorRef(id="fast")
    slow = IndicatorRef(id="slow")
    return StrategySpec(
        name="2/3 SMA crossover",
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
        position_sizing=PositionSizingSpec(
            cash_buffer_fraction=cash_buffer_fraction,
            allow_fractional_shares=allow_fractional_shares,
        ),
    )


def config(
    *,
    capital: float = 1_000.0,
    commission: float = 0.0,
    slippage_bps: float = 0.0,
    start_date: date = date(2024, 1, 2),
    end_date: date = date(2024, 1, 20),
) -> BacktestConfig:
    return BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        starting_capital=capital,
        costs=CostModel(
            commission_amount=commission,
            slippage_bps=slippage_bps,
        ),
    )


def test_signals_execute_at_next_bar_open_not_signal_close() -> None:
    data = make_market_data(
        closes=(10, 9, 8, 9, 11, 10, 8, 7),
        opens=(10, 9, 8, 9, 11, 20, 8, 5),
    )

    result = run_backtest(crossover_spec(), config(), data)

    assert len(result.trades) == 2
    buy, sell = result.trades
    assert buy.side == TradeSide.BUY
    assert buy.signal_timestamp == data.bars[4].timestamp
    assert buy.execution_timestamp == data.bars[5].timestamp
    assert buy.fill_price == 20.0
    assert buy.quantity == 50.0
    assert sell.side == TradeSide.SELL
    assert sell.signal_timestamp == data.bars[6].timestamp
    assert sell.execution_timestamp == data.bars[7].timestamp
    assert sell.fill_price == 5.0
    assert result.final_cash == 250.0
    assert result.final_position_quantity == 0.0


def test_commission_and_slippage_affect_quantity_and_cash_exactly() -> None:
    data = make_market_data(
        closes=(10, 9, 8, 9, 11, 10, 8, 7),
        opens=(10, 9, 8, 9, 11, 20, 8, 5),
    )

    result = run_backtest(
        crossover_spec(),
        config(commission=1.0, slippage_bps=100.0),
        data,
    )

    buy, sell = result.trades
    assert buy.fill_price == pytest.approx(20.2)
    assert buy.quantity == 49.0
    assert buy.commission == 1.0
    assert buy.slippage_cost == pytest.approx(9.8)
    assert buy.cash_after == pytest.approx(9.2)

    assert sell.fill_price == pytest.approx(4.95)
    assert sell.quantity == 49.0
    assert sell.slippage_cost == pytest.approx(2.45)
    assert sell.cash_after == pytest.approx(250.75)
    assert result.final_cash == pytest.approx(250.75)


def test_equity_curve_marks_position_to_close_after_open_execution() -> None:
    data = make_market_data(
        closes=(10, 9, 8, 9, 11, 10, 8, 7),
        opens=(10, 9, 8, 9, 11, 20, 8, 5),
    )

    result = run_backtest(crossover_spec(), config(), data)

    assert [point.equity for point in result.equity_curve] == [
        1000.0,
        1000.0,
        1000.0,
        1000.0,
        1000.0,
        500.0,
        400.0,
        250.0,
    ]
    assert result.equity_curve[5].position_quantity == 50.0
    assert result.equity_curve[7].position_quantity == 0.0


def test_cash_buffer_is_respected_for_integer_all_in_sizing() -> None:
    data = make_market_data(
        closes=(10, 9, 8, 9, 11, 10),
        opens=(10, 9, 8, 9, 11, 20),
    )

    result = run_backtest(
        crossover_spec(cash_buffer_fraction=0.10),
        config(),
        data,
    )

    assert len(result.trades) == 1
    assert result.trades[0].quantity == 45.0
    assert result.trades[0].cash_after == 100.0


def test_fractional_all_in_sizing_can_deploy_the_budget() -> None:
    data = make_market_data(
        closes=(10, 9, 8, 9, 11, 10),
        opens=(10, 9, 8, 9, 11, 30),
    )

    result = run_backtest(
        crossover_spec(allow_fractional_shares=True),
        config(),
        data,
    )

    assert result.trades[0].quantity == pytest.approx(1000 / 30)
    assert result.trades[0].cash_after == pytest.approx(0.0)


def test_final_bar_signal_cannot_execute_without_a_future_bar() -> None:
    data = make_market_data(closes=(10, 9, 8, 9, 11))

    result = run_backtest(crossover_spec(), config(), data)

    assert result.trades == ()
    assert result.final_cash == 1000.0
    assert result.final_position_quantity == 0.0


def test_pre_start_signal_does_not_create_position_at_period_start() -> None:
    data = make_market_data(
        closes=(10, 9, 8, 9, 11, 10, 10),
        opens=(10, 9, 8, 9, 11, 20, 20),
    )

    result = run_backtest(
        crossover_spec(),
        config(start_date=date(2024, 1, 7), end_date=date(2024, 1, 8)),
        data,
    )

    # Entry signal occurred Jan 6, before the experiment starts on Jan 7.
    assert result.trades == ()
    assert [point.equity for point in result.equity_curve] == [1000.0, 1000.0]


def test_exit_commission_can_make_cash_negative_without_crashing() -> None:
    data = make_market_data(
        closes=(10, 9, 8, 9, 11, 10, 8, 0.01),
        opens=(10, 9, 8, 9, 11, 20, 8, 0.01),
    )

    result = run_backtest(
        crossover_spec(),
        config(capital=21.0, commission=1.0),
        data,
    )

    assert result.trades[0].quantity == 1.0
    assert result.trades[0].cash_after == 0.0
    assert result.trades[1].cash_after == pytest.approx(-0.99)
    assert result.final_cash == pytest.approx(-0.99)
