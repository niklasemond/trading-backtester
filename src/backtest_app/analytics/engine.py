"""Deterministic performance analytics for daily single-asset backtests."""

from __future__ import annotations

from decimal import Decimal, ROUND_FLOOR
from math import sqrt
from statistics import fmean, stdev

from backtest_app.domain.analytics import BacktestAnalysis, BenchmarkResult, PerformanceMetrics
from backtest_app.domain.backtest import BacktestResult, EquityPoint, TradeSide
from backtest_app.domain.experiment import BacktestConfig
from backtest_app.domain.market_data import MarketDataSet
from backtest_app.domain.strategy import StrategySpec
from backtest_app.execution.corporate_actions import apply_corporate_actions

_TRADING_DAYS = 252
_CALENDAR_DAYS = 365.25
_BPS = Decimal("10000")
_ZERO = Decimal("0")


def _decimal(value: float | int) -> Decimal:
    return Decimal(str(value))


def _daily_returns(starting_capital: float, equity_curve: tuple[EquityPoint, ...]) -> list[float]:
    if not equity_curve:
        return []

    values = [starting_capital, *(point.equity for point in equity_curve)]
    returns: list[float] = []
    for previous, current in zip(values, values[1:]):
        if previous == 0:
            continue
        returns.append(current / previous - 1.0)
    return returns


def _max_drawdown(starting_capital: float, equity_curve: tuple[EquityPoint, ...]) -> float:
    peak = starting_capital
    worst = 0.0
    for point in equity_curve:
        peak = max(peak, point.equity)
        if peak > 0:
            worst = max(worst, 1.0 - point.equity / peak)
    return worst


def _completed_round_trips(result: BacktestResult) -> int:
    open_position = False
    completed = 0
    for trade in result.trades:
        if trade.side == TradeSide.BUY and not open_position:
            open_position = True
        elif trade.side == TradeSide.SELL and open_position:
            completed += 1
            open_position = False
    return completed


def calculate_metrics(
    starting_capital: float,
    equity_curve: tuple[EquityPoint, ...],
    *,
    number_of_trades: int = 0,
) -> PerformanceMetrics:
    """Calculate first-milestone daily performance metrics."""

    if not equity_curve:
        return PerformanceMetrics(
            total_return=0.0,
            cagr=None,
            annualized_volatility=None,
            sharpe_ratio=None,
            max_drawdown=0.0,
            number_of_trades=number_of_trades,
        )

    final_equity = equity_curve[-1].equity
    total_return = final_equity / starting_capital - 1.0

    elapsed_days = (
        equity_curve[-1].timestamp.date() - equity_curve[0].timestamp.date()
    ).days
    cagr: float | None = None
    if elapsed_days > 0 and final_equity > 0:
        years = elapsed_days / _CALENDAR_DAYS
        cagr = (final_equity / starting_capital) ** (1.0 / years) - 1.0

    returns = _daily_returns(starting_capital, equity_curve)
    annualized_volatility: float | None = None
    sharpe_ratio: float | None = None
    if len(returns) >= 2:
        daily_volatility = stdev(returns)
        annualized_volatility = daily_volatility * sqrt(_TRADING_DAYS)
        if daily_volatility > 0:
            sharpe_ratio = fmean(returns) / daily_volatility * sqrt(_TRADING_DAYS)

    return PerformanceMetrics(
        total_return=total_return,
        cagr=cagr,
        annualized_volatility=annualized_volatility,
        sharpe_ratio=sharpe_ratio,
        max_drawdown=_max_drawdown(starting_capital, equity_curve),
        number_of_trades=number_of_trades,
    )


def create_buy_and_hold_benchmark(
    strategy: StrategySpec,
    backtest: BacktestConfig,
    market_data: MarketDataSet,
) -> BenchmarkResult:
    """Buy first in-range open, then apply the same corporate-action policy.

    Corporate actions occur before the event-date open. Therefore a benchmark
    purchase on the first in-range event date does not receive that date's
    dividend or split adjustment; later events apply to the held position.
    """

    in_range_bars = tuple(
        bar
        for bar in market_data.bars
        if backtest.start_date <= bar.timestamp.date() <= backtest.end_date
    )
    if not in_range_bars:
        return BenchmarkResult(
            symbol=strategy.symbols[0],
            starting_capital=backtest.starting_capital,
            quantity=0.0,
            final_quantity=0.0,
            entry_price=None,
            commission=0.0,
            equity_curve=(),
            corporate_actions=(),
        )

    cash = _decimal(backtest.starting_capital)
    commission = _decimal(backtest.costs.commission_amount)
    slippage_fraction = _decimal(backtest.costs.slippage_bps) / _BPS
    cash_buffer = _decimal(strategy.position_sizing.cash_buffer_fraction)
    quantity = _ZERO
    entry_quantity = _ZERO
    charged_commission = _ZERO
    entry_price: Decimal | None = None
    curve: list[EquityPoint] = []
    corporate_actions = []

    for index, bar in enumerate(in_range_bars):
        if quantity > _ZERO:
            action_state = apply_corporate_actions(
                bar, cash=cash, position=quantity
            )
            cash = action_state.cash
            quantity = action_state.position
            corporate_actions.extend(action_state.records)

        if index == 0:
            entry_price = _decimal(bar.open) * (
                Decimal("1") + slippage_fraction
            )
            deployable = cash * (Decimal("1") - cash_buffer) - commission
            if deployable > _ZERO:
                raw_quantity = deployable / entry_price
                if strategy.position_sizing.allow_fractional_shares:
                    quantity = raw_quantity
                else:
                    quantity = raw_quantity.to_integral_value(rounding=ROUND_FLOOR)
                if quantity > _ZERO:
                    cash -= quantity * entry_price + commission
                    entry_quantity = quantity
                    charged_commission = commission

        close_price = _decimal(bar.close)
        curve.append(
            EquityPoint(
                timestamp=bar.timestamp,
                cash=float(cash),
                position_quantity=float(quantity),
                close_price=float(close_price),
                equity=float(cash + quantity * close_price),
            )
        )

    return BenchmarkResult(
        symbol=strategy.symbols[0],
        starting_capital=backtest.starting_capital,
        quantity=float(entry_quantity),
        final_quantity=float(quantity),
        entry_price=float(entry_price) if entry_quantity > _ZERO and entry_price else None,
        commission=float(charged_commission),
        equity_curve=tuple(curve),
        corporate_actions=tuple(corporate_actions),
    )


def analyze_backtest(
    result: BacktestResult,
    strategy: StrategySpec,
    backtest: BacktestConfig,
    market_data: MarketDataSet,
) -> BacktestAnalysis:
    """Produce strategy metrics and a comparable buy-and-hold benchmark."""

    benchmark = create_buy_and_hold_benchmark(strategy, backtest, market_data)
    return BacktestAnalysis(
        strategy_metrics=calculate_metrics(
            result.starting_capital,
            result.equity_curve,
            number_of_trades=_completed_round_trips(result),
        ),
        benchmark=benchmark,
        benchmark_metrics=calculate_metrics(
            benchmark.starting_capital,
            benchmark.equity_curve,
            number_of_trades=1 if benchmark.quantity > 0 else 0,
        ),
    )
