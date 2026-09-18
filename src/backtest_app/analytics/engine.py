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
    """Calculate first-milestone daily performance metrics.

    Volatility and Sharpe use arithmetic end-of-bar returns, a 252-day annual
    factor, sample standard deviation, and a 0% risk-free rate. CAGR uses actual
    elapsed calendar time between the first and last equity observations.
    """

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
    """Buy at the first in-range open and hold through the final close.

    The benchmark uses the strategy's fractional/integer sizing and cash buffer,
    plus the same buy commission and adverse buy slippage as the strategy run.
    It is not force-liquidated at the end, so no exit cost is charged.
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
            entry_price=None,
            commission=0.0,
            equity_curve=(),
        )

    cash = _decimal(backtest.starting_capital)
    commission = _decimal(backtest.costs.commission_amount)
    slippage_fraction = _decimal(backtest.costs.slippage_bps) / _BPS
    cash_buffer = _decimal(strategy.position_sizing.cash_buffer_fraction)
    first = in_range_bars[0]
    entry_price = _decimal(first.open) * (Decimal("1") + slippage_fraction)

    deployable = cash * (Decimal("1") - cash_buffer) - commission
    quantity = _ZERO
    charged_commission = _ZERO
    if deployable > _ZERO:
        raw_quantity = deployable / entry_price
        if strategy.position_sizing.allow_fractional_shares:
            quantity = raw_quantity
        else:
            quantity = raw_quantity.to_integral_value(rounding=ROUND_FLOOR)
        if quantity > _ZERO:
            cash -= quantity * entry_price + commission
            charged_commission = commission

    curve = tuple(
        EquityPoint(
            timestamp=bar.timestamp,
            cash=float(cash),
            position_quantity=float(quantity),
            close_price=bar.close,
            equity=float(cash + quantity * _decimal(bar.close)),
        )
        for bar in in_range_bars
    )

    return BenchmarkResult(
        symbol=strategy.symbols[0],
        starting_capital=backtest.starting_capital,
        quantity=float(quantity),
        entry_price=float(entry_price) if quantity > _ZERO else None,
        commission=float(charged_commission),
        equity_curve=curve,
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
