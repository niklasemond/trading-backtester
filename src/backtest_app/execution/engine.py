"""Deterministic next-bar execution and single-asset portfolio accounting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_FLOOR

from backtest_app.domain.backtest import BacktestResult, EquityPoint, TradeRecord, TradeSide
from backtest_app.domain.experiment import BacktestConfig
from backtest_app.domain.market_data import MarketBar, MarketDataSet
from backtest_app.domain.signals import SignalSeries
from backtest_app.domain.strategy import StrategySpec
from backtest_app.signals.engine import generate_signals

ENGINE_VERSION = "0.2.0"
_BPS = Decimal("10000")
_ZERO = Decimal("0")


def _decimal(value: float | int) -> Decimal:
    return Decimal(str(value))


@dataclass(frozen=True)
class _PendingOrder:
    side: TradeSide
    signal_timestamp: datetime


def _validate_inputs(
    strategy: StrategySpec,
    market_data: MarketDataSet,
    signals: SignalSeries,
) -> None:
    symbol = strategy.symbols[0]
    if market_data.symbol != symbol or signals.symbol != symbol:
        raise ValueError("strategy, market data, and signals must use the same symbol")
    if len(signals.points) != len(market_data.bars):
        raise ValueError("signals must contain exactly one point per market-data bar")
    for bar, point in zip(market_data.bars, signals.points, strict=True):
        if bar.timestamp != point.timestamp:
            raise ValueError("signal timestamps must align exactly with market-data bars")


def _fill_price(bar: MarketBar, side: TradeSide, slippage_bps: Decimal) -> Decimal:
    open_price = _decimal(bar.open)
    slippage_fraction = slippage_bps / _BPS
    if side == TradeSide.BUY:
        return open_price * (Decimal("1") + slippage_fraction)
    return open_price * (Decimal("1") - slippage_fraction)


def _buy_quantity(
    cash: Decimal,
    fill_price: Decimal,
    commission: Decimal,
    cash_buffer_fraction: Decimal,
    allow_fractional_shares: bool,
) -> Decimal:
    deployable_cash = cash * (Decimal("1") - cash_buffer_fraction)
    notional_budget = deployable_cash - commission
    if notional_budget <= _ZERO:
        return _ZERO

    raw_quantity = notional_budget / fill_price
    if allow_fractional_shares:
        return raw_quantity
    return raw_quantity.to_integral_value(rounding=ROUND_FLOOR)


def simulate_execution(
    strategy: StrategySpec,
    backtest: BacktestConfig,
    market_data: MarketDataSet,
    signals: SignalSeries,
) -> BacktestResult:
    """Execute close-derived signals at the next eligible bar's open.

    Portfolio equity is marked to each in-range bar's close. Signals outside the
    requested experiment date range are ignored, which allows callers to supply
    pre-start warm-up data for indicators without creating pre-period positions.
    """

    _validate_inputs(strategy, market_data, signals)

    cash = _decimal(backtest.starting_capital)
    position = _ZERO
    commission = _decimal(backtest.costs.commission_amount)
    slippage_bps = _decimal(backtest.costs.slippage_bps)
    cash_buffer_fraction = _decimal(strategy.position_sizing.cash_buffer_fraction)

    pending: _PendingOrder | None = None
    trades: list[TradeRecord] = []
    equity_curve: list[EquityPoint] = []

    for bar, signal in zip(market_data.bars, signals.points, strict=True):
        bar_date = bar.timestamp.date()
        in_range = backtest.start_date <= bar_date <= backtest.end_date

        # A signal generated on the prior bar can only execute now. If this bar
        # falls outside the experiment range, the order is deliberately dropped.
        if pending is not None:
            if in_range:
                side = pending.side
                fill_price = _fill_price(bar, side, slippage_bps)
                reference_open = _decimal(bar.open)

                if fill_price <= _ZERO:
                    raise ValueError("slippage produced a non-positive execution price")

                if side == TradeSide.BUY and position == _ZERO:
                    quantity = _buy_quantity(
                        cash=cash,
                        fill_price=fill_price,
                        commission=commission,
                        cash_buffer_fraction=cash_buffer_fraction,
                        allow_fractional_shares=strategy.position_sizing.allow_fractional_shares,
                    )
                    if quantity > _ZERO:
                        cash -= quantity * fill_price + commission
                        position += quantity
                        slippage_cost = quantity * (fill_price - reference_open)
                        trades.append(
                            TradeRecord(
                                side=side,
                                signal_timestamp=pending.signal_timestamp,
                                execution_timestamp=bar.timestamp,
                                reference_open=float(reference_open),
                                fill_price=float(fill_price),
                                quantity=float(quantity),
                                commission=float(commission),
                                slippage_cost=float(slippage_cost),
                                cash_after=float(cash),
                                position_after=float(position),
                            )
                        )
                elif side == TradeSide.SELL and position > _ZERO:
                    quantity = position
                    cash += quantity * fill_price - commission
                    position = _ZERO
                    slippage_cost = quantity * (reference_open - fill_price)
                    trades.append(
                        TradeRecord(
                            side=side,
                            signal_timestamp=pending.signal_timestamp,
                            execution_timestamp=bar.timestamp,
                            reference_open=float(reference_open),
                            fill_price=float(fill_price),
                            quantity=float(quantity),
                            commission=float(commission),
                            slippage_cost=float(slippage_cost),
                            cash_after=float(cash),
                            position_after=float(position),
                        )
                    )
            pending = None

        if in_range:
            close_price = _decimal(bar.close)
            equity = cash + position * close_price
            equity_curve.append(
                EquityPoint(
                    timestamp=bar.timestamp,
                    cash=float(cash),
                    position_quantity=float(position),
                    close_price=float(close_price),
                    equity=float(equity),
                )
            )

            # Signals are inspected only after this bar's execution and close
            # marking. That prevents any same-bar use of close-derived signals.
            if bar_date < backtest.end_date:
                if position == _ZERO and signal.enter_long:
                    pending = _PendingOrder(
                        side=TradeSide.BUY,
                        signal_timestamp=signal.timestamp,
                    )
                elif position > _ZERO and signal.exit_long:
                    pending = _PendingOrder(
                        side=TradeSide.SELL,
                        signal_timestamp=signal.timestamp,
                    )
        else:
            # Never carry a pending order across the requested experiment's
            # boundary. Pre-start bars exist only for indicator warm-up.
            pending = None

    return BacktestResult(
        engine_version=ENGINE_VERSION,
        symbol=strategy.symbols[0],
        starting_capital=backtest.starting_capital,
        final_cash=float(cash),
        final_position_quantity=float(position),
        trades=tuple(trades),
        equity_curve=tuple(equity_curve),
    )


def run_backtest(
    strategy: StrategySpec,
    backtest: BacktestConfig,
    market_data: MarketDataSet,
) -> BacktestResult:
    """Run signal generation followed by deterministic execution/accounting."""

    signals = generate_signals(strategy, market_data)
    return simulate_execution(strategy, backtest, market_data, signals)
