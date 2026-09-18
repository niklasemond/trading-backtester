# Bounded strategy search and holdout validation

The research search endpoint is intentionally designed as a bounded experiment rather than an unconstrained optimizer.

## Workflow

1. Define a finite grid of fast/slow SMA windows plus optional trend, momentum, and volatility filters.
2. Reject the request before fetching data if the grid expands beyond `max_candidates`.
3. Fetch one shared market-data history covering the largest indicator warm-up window.
4. Evaluate every candidate over the training period only.
5. Rank candidates by the selected training objective: total return, Sharpe ratio, or inverse maximum drawdown.
6. Report the same candidate on a later chronological validation period that was not used for ranking.

Training ends on the day before `validation_start_date`. Validation starts with fresh portfolio capital and may use earlier history only for indicator warm-up. Positions are not carried from training into validation.

## Why the holdout matters

A strategy selected because it performed well on the same data used to choose its parameters is in-sample evidence. The validation metrics are intentionally reported separately so a strong training result is not presented as independent confirmation.

The current holdout is a single chronological split, not a complete defense against overfitting. Later research tooling can add walk-forward evaluation, multiple regimes, parameter-stability analysis, and explicit robustness thresholds.

## Benchmark comparison

Each training and validation period includes the app's executable buy-and-hold benchmark under the same starting capital, fixed commission, slippage, cash-buffer, and share-sizing assumptions. `excess_total_return` is strategy total return minus benchmark total return for that period.
