# Backtest assumptions and correctness contract

These are the foundation rules for the first milestone. Implementations and tests should make changes to these rules explicit rather than silently changing semantics.

## Information timing

- Daily strategy indicators are computed only from bars available through the signal bar's close.
- A signal that depends on day **T** close may not execute on day **T**.
- Initial execution model: signal at day **T** close, execute at the next available bar (**T+1**) open.
- Missing calendar days are not synthesized. "Next bar" means the next observation actually returned in the validated dataset.
- Requested `start_date` and `end_date` are inclusive boundaries; provider adapters must document any source-specific conversion needed to achieve that contract.

## Market data

- Providers must normalize source data into the canonical `MarketBar` model before the engine sees it.
- Canonical timestamps are timezone-aware. Provider implementations are responsible for defining and documenting how a daily source date maps to a timestamp.
- Bars must be strictly increasing with no duplicate timestamps.
- OHLC fields represent unadjusted tradable prices unless a provider explicitly documents otherwise; `adjusted_close` is a separate field.
- Dividend and split fields may be `None` when the source cannot provide them. `None` means unavailable, not necessarily zero/no event.
- The exact corporate-action accounting policy is intentionally **not implemented yet**. Iterations that add the data provider and portfolio engine must choose and test a consistent policy before performance results are treated as meaningful.

## Strategy representation

- Backtesting logic consumes a validated, versioned `StrategySpec`; UI code will not contain financial logic.
- The initial schema is single-asset, daily, and long-only by validation.
- Indicator and condition definitions are declarative. No arbitrary Python callback is part of the persisted strategy representation.
- Version `1.0` initially supports SMA indicators and crossover conditions. Schema evolution must be versioned.

## Portfolio and execution

- Initial sizing intent is all-in long, integer shares by default, while retaining an explicit cash balance.
- Starting capital must be positive.
- Initial cost model is a fixed commission per executed order plus non-negative slippage in basis points.
- Exact slippage application (buy price worsens upward, sell price worsens downward) will be implemented and tested with the execution engine.
- Orders that cannot be funded after costs must never create negative cash silently.

## Reproducibility

A persisted result should eventually capture at least:

- experiment schema version
- `StrategySpec` including schema version and resolved parameter values
- engine version
- requested and actual data provider
- data retrieval timestamp and, where possible, provider dataset/version or raw-data fingerprint
- instrument, frequency, and requested date range
- starting capital and cost assumptions
- execution timing assumptions

## Deliberately unresolved in Iteration 1

The foundation does not yet decide or implement survivorship-bias handling, delisted securities, tax treatment, borrow/shorting, intraday bars, multi-asset synchronization, or a final total-return/corporate-action methodology. Those are outside the first milestone and should not be accidentally implied by early results.

## Signal-generation semantics added in Iteration 2

- SMA values are trailing arithmetic means. A bar receives no SMA value until a full window of observations exists.
- Indicator calculations consume canonical bars in their existing order and never inspect later bars.
- `crosses_above` is true on bar **T** when `left[T-1] <= right[T-1]` and `left[T] > right[T]`.
- `crosses_below` is true on bar **T** when `left[T-1] >= right[T-1]` and `left[T] < right[T]`.
- A crossover is false if either indicator is unavailable on either side of the transition, which prevents signals during indicator warm-up.
- Multiple conditions within an entry or exit list use AND semantics in schema version `1.0`.
- Signal generation is position-agnostic. It reports strategy intent at the signal bar; execution/portfolio logic is responsible for deciding whether an order is valid given current holdings.
- Signal generation never executes a trade. For the v1 execution contract, a signal on bar **T** remains eligible only for execution on the next observed bar's open.

## Execution and portfolio semantics added in Iteration 3

- A signal on observed bar **T** is inspected only after that bar has been marked to its close. It can execute only on the next observed bar, at that bar's open.
- A signal on the final available bar cannot execute because there is no future observation.
- Missing calendar dates are irrelevant to execution timing: "next bar" means the next canonical observation, not the next calendar day.
- Signals before the requested experiment `start_date` may contribute to indicator warm-up but cannot create a position inside the experiment. The portfolio begins the requested period in cash.
- Orders are not carried beyond the inclusive `end_date`.
- Buy slippage raises the execution price by `slippage_bps / 10,000`; sell slippage lowers it by the same fraction. Slippage must be less than 10,000 bps so a sell fill cannot become non-positive.
- Fixed commission is charged once per executed buy or sell order. An unfundable buy is skipped rather than borrowing cash.
- Integer all-in sizing uses the largest whole-share quantity affordable after reserving the configured cash buffer and buy commission. Fractional all-in sizing is supported explicitly by the `StrategySpec` flag.
- Cash, fills, and sizing arithmetic use decimal arithmetic internally. Public result models remain numeric/JSON-friendly.
- Portfolio equity is marked at each in-range bar's close as `cash + quantity * close` after any opening execution on that bar.
- A sufficiently severe price collapse combined with a fixed exit commission can produce negative final cash/equity. This is recorded explicitly rather than rejected or silently clipped.
- Trade history currently records executed fills (buy/sell) with both the originating signal timestamp and execution timestamp. Round-trip trade analytics are deferred to the analytics layer.
- Corporate-action accounting remains unresolved. Until a consistent split/dividend methodology is implemented and tested, results from real historical data should not be interpreted as production-grade total-return backtests.

## Analytics and benchmark semantics added in Iteration 4

- Strategy total return is `final equity / starting capital - 1`; starting capital is the return base even if the first in-range close differs from it.
- CAGR uses actual elapsed calendar days between the first and last in-range equity observations and a 365.25-day year. CAGR is left undefined when there is insufficient elapsed time or final equity is non-positive.
- Daily return statistics include the change from starting capital to the first in-range end-of-bar equity, then each subsequent end-of-bar change.
- Annualized volatility uses sample standard deviation of arithmetic daily returns multiplied by `sqrt(252)`.
- Sharpe ratio uses the arithmetic mean daily return divided by daily sample standard deviation, annualized by `sqrt(252)`, with a 0% risk-free rate for the first milestone. It is undefined when volatility is zero or there are too few returns.
- Maximum drawdown is reported as a positive magnitude from the running equity peak, with starting capital included as the initial peak.
- `number_of_trades` for the strategy means completed round trips (buy followed by sell). An open position at the end is not counted as a completed trade.
- The buy-and-hold benchmark is executable: it buys at the first in-range bar's open using the same buy slippage, fixed commission, cash buffer, and integer/fractional sizing assumptions as the strategy. It then holds through the final close and is not force-liquidated, so no benchmark exit cost is charged.
- Benchmark equity is marked to the same in-range closes as the strategy, allowing chart points to align directly.
- Corporate-action limitations from earlier iterations still apply to both strategy and benchmark results.
