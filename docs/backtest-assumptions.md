# Backtest assumptions and correctness contract

These are the foundation rules for the first milestone. Implementations and tests should make changes to these rules explicit rather than silently changing semantics.

## Information timing

- Daily strategy indicators are computed only from bars available through the signal bar's close.
- A signal that depends on day **T** close may not execute on day **T**.
- Initial execution model: signal at day **T** close, execute at the next available bar (**T+1**) open.
- Missing calendar days are not synthesized. "Next bar" means the next observation actually returned in the validated dataset.
- Requested `start_date` and `end_date` are inclusive boundaries; provider adapters must document any source-specific conversion needed to achieve that contract.
- A daily bar may be used as a close-derived signal only after its exchange session is complete. Provider adapters must exclude current-session/incomplete daily bars before they reach signal generation.
- Daily-session completeness is evaluated in the exchange timezone, never from the local computer's calendar date.

## Market data

- Providers must normalize source data into the canonical `MarketBar` model before the engine sees it.
- Canonical timestamps are timezone-aware. Provider implementations are responsible for defining and documenting how a daily source date maps to a timestamp.
- Bars must be strictly increasing with no duplicate timestamps.
- OHLC fields represent unadjusted tradable prices unless a provider explicitly documents otherwise; `adjusted_close` is a separate field.
- Dividend and split fields may be `None` when the source cannot provide them. `None` means unavailable, not necessarily zero/no event.
- Corporate actions use explicit event accounting. Raw canonical OHLC is the tradable and mark-to-market series; `adjusted_close` is never used for portfolio accounting.
- Split events are applied to shares held entering the event-date bar before that bar's execution. Position quantity is multiplied by the split ratio, with no cash flow.
- Dividend events are treated as ex-date entitlements: cash is credited on the provider event date to shares held entering that session. A position opened at that session's open does not receive that dividend.
- If a split and dividend share one bar, the split is applied first and the dividend amount is interpreted per post-split share.
- Corporate actions actually applied to a held position are recorded in the strategy or benchmark corporate-action ledger.

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
- Corporate-action accounting is explicit: held positions receive split quantity changes and dividend cash flows before event-date execution, and each applied action is recorded in the result ledger.
- Equity continues to use raw canonical close prices after those explicit adjustments. `adjusted_close` must not be substituted into portfolio accounting because that would double-count the same actions.

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
- Strategy and buy-and-hold use the same corporate-action application function and event ordering.
- Provider-data quality remains a limitation: if a source supplies an incorrect/missing dividend, split ratio, or raw price, the engine deliberately does not invent a repair.


## Pre-start indicator warm-up added in Iteration 7

- The application service requests historical observations before the user-selected start date so trailing indicators can be fully initialized when the experiment begins.
- For the current SMA/crossover schema, the required pre-start observation count is the largest SMA window. This is sufficient to calculate both the previous-bar and first in-range-bar indicator states needed for crossover detection.
- The provider request uses a conservative calendar lookback and verifies the actual number of returned pre-start observations. If insufficient history is returned, the lookback expands adaptively with a bounded number of retries.
- A security with genuinely insufficient prior history is still allowed to run; normal indicator warm-up semantics suppress signals until enough observations exist.
- Pre-start bars may influence indicator values only. They cannot create trades, equity points, benchmark points, or performance observations before the requested `start_date`.
- No future observations are introduced by warm-up; all first-day signals depend only on bars at or before that signal bar.
