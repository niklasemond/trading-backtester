"""Deterministic corporate-action accounting shared by strategy and benchmark."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from backtest_app.domain.backtest import CorporateActionRecord, CorporateActionType
from backtest_app.domain.market_data import MarketBar

_ZERO = Decimal("0")
_ONE = Decimal("1")


def _decimal(value: float | int) -> Decimal:
    return Decimal(str(value))


@dataclass(frozen=True)
class CorporateActionState:
    cash: Decimal
    position: Decimal
    records: tuple[CorporateActionRecord, ...]


def apply_corporate_actions(
    bar: MarketBar,
    *,
    cash: Decimal,
    position: Decimal,
) -> CorporateActionState:
    """Apply event-date actions to shares held entering the bar.

    Policy for the current daily US-equity model:

    * raw canonical OHLC remains the tradable/mark-to-market price series;
    * a split is effective before the event-date open, so an existing position
      quantity is multiplied by the split ratio before any order can execute;
    * a dividend event is treated as an ex-date entitlement and credited as cash
      on the event date to the position held entering that session;
    * if split and dividend occur on one bar, split is applied first and the
      provider's dividend amount is interpreted per post-split share;
    * positions opened at the event-date open do not receive that day's dividend.

    This function deliberately does not use adjusted_close. Doing so in addition
    to explicit cash/share adjustments would double-count corporate actions.
    """

    records: list[CorporateActionRecord] = []
    current_cash = cash
    current_position = position

    if current_position <= _ZERO:
        return CorporateActionState(
            cash=current_cash, position=current_position, records=()
        )

    if bar.split_ratio is not None:
        ratio = _decimal(bar.split_ratio)
        if ratio != _ONE:
            before = current_position
            current_position *= ratio
            records.append(
                CorporateActionRecord(
                    timestamp=bar.timestamp,
                    action_type=CorporateActionType.SPLIT,
                    quantity_before=float(before),
                    quantity_after=float(current_position),
                    cash_flow=0.0,
                    cash_after=float(current_cash),
                    split_ratio=float(ratio),
                )
            )

    if bar.dividend is not None:
        dividend = _decimal(bar.dividend)
        if dividend > _ZERO:
            before = current_position
            cash_flow = current_position * dividend
            current_cash += cash_flow
            records.append(
                CorporateActionRecord(
                    timestamp=bar.timestamp,
                    action_type=CorporateActionType.DIVIDEND,
                    quantity_before=float(before),
                    quantity_after=float(current_position),
                    cash_flow=float(cash_flow),
                    cash_after=float(current_cash),
                    dividend_per_share=float(dividend),
                )
            )

    return CorporateActionState(
        cash=current_cash,
        position=current_position,
        records=tuple(records),
    )
