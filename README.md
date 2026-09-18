# Trading Backtester

A modular browser-based trading-strategy backtester focused on explicit timing, deterministic accounting, and reproducible experiments.

## Current milestone

The application now has its first browser-usable vertical slice:

- versioned, declarative `StrategySpec`
- daily single-asset SMA crossover signals
- close-derived signals with next-observed-bar open execution
- long-only portfolio/cash accounting
- fixed commissions and adverse slippage
- equity curve and trade history
- total return, CAGR, volatility, Sharpe ratio, and maximum drawdown
- executable buy-and-hold benchmark
- FastAPI HTTP API
- built-in Yahoo Finance daily-data adapter behind the provider abstraction
- browser form for symbol, SMA windows, dates, capital, costs, slippage, and sizing
- Defensive, Neutral, and Offensive backtest example presets that populate strategy, filter, sizing, and execution assumptions while leaving the selected date range unchanged
- Weak, Good, and Strong historical SPY examples calibrated on 2000-01-03 through 2025-12-31 with 5 bps slippage; these load the fixed calibration dates and are labeled as historical examples rather than forecasts
- browser results for metrics, equity-vs-benchmark chart, and trade history
- About tab focused on application purpose, workflow, design choices, scope, and limitations
- clickable metric cards with buy-and-hold comparisons and clearer chart axes/legend
- browser strategy builder for optional price-trend, ROC momentum, and volatility filters with configurable entry/exit logic
- bounded strategy research API with a chronological holdout period and buy-and-hold excess-return reporting
- browser Research tab for bounded parameter grids, candidate-cap previews, ranked training results, and separate holdout metrics
- excess-return ranking objective plus a post-search robustness diagnostic that never affects holdout-independent ranking
- cross-linked Learn tab with searchable plain-English concept articles and interactive visual explainers
- worked simple-backtest capstone that connects input selection, execution assumptions, benchmark comparison, risk metrics, and next-step research

The system remains intentionally small: the browser UI contains no backtesting logic and there is no authentication or separate JavaScript build toolchain yet.

## Run locally

From a fresh checkout:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e ".[api,dev]"
python -m pytest
uvicorn backtest_app.api.app:app --app-dir src --reload
```

Then open:

- `http://127.0.0.1:8000/` — browser backtester
- `http://127.0.0.1:8000/docs` — interactive API documentation
- `http://127.0.0.1:8000/health` — health check

The browser defaults to SPY with a 20/50 SMA crossover and Yahoo Finance as the free historical-data provider.

## Important data/correctness caveats

Yahoo is used as a convenient free research source, not as a licensed production market-data feed. The engine now applies explicit split quantity changes and dividend cash credits from provider events to both strategy and buy-and-hold portfolios, while raw OHLC remains the tradable/mark-to-market series and adjusted close is stored separately. Yahoo data can still contain missing or incorrect corporate-action/price records, so real-data results remain research-grade rather than production-feed quality.

Indicator warm-up is fetched automatically before the selected start date. Warm-up bars are used only for indicator state; portfolio accounting, benchmark construction, and reported performance remain constrained to the selected experiment dates.

The research search ranks candidates only on the training period and reports a later chronological validation period separately. That single holdout reduces one obvious source of in-sample bias but is not a complete defense against overfitting.

## Tests

The tests use small deterministic datasets so expected fills, cash balances, signals, equity, benchmark values, metrics, and search behavior can be checked directly.
