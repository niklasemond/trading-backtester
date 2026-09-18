# StrategySpec 1.1

StrategySpec 1.1 extends the original SMA-crossover representation without changing existing 1.0 behavior.

## New indicators

- `roc`: trailing rate of change, calculated as `price[t] / price[t-window] - 1`.
- `volatility`: sample standard deviation of trailing arithmetic daily returns, annualized by a configurable factor (252 by default).

Both indicators use only the current bar and earlier observations. Their warm-up periods are explicit and return no value until sufficient history exists.

## New condition operands

A comparison can use an indicator reference, a canonical price field such as `close`, or a numeric constant. This makes filters such as `close > SMA(200)`, `ROC(126) > 0`, and `volatility(20) < 0.35` machine-readable.

## Condition logic

Entry and exit lists can independently use `all` (AND) or `any` (OR) logic. Schema 1.0 remains restricted to the original all-condition SMA crossover behavior.

## Timing

Comparison conditions are evaluated at the signal bar using information available through that bar. The existing execution contract still applies: a close-derived signal can execute only at the next available bar's open.

## Example

A filtered long-only trend strategy can be represented as:

- enter when a fast SMA crosses above a slow SMA,
- AND close is above the slow SMA,
- AND 126-day ROC is positive;
- exit when the fast SMA crosses below the slow SMA,
- OR 126-day ROC becomes negative.

This remains declarative data and requires no arbitrary Python callback.
