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
- browser results for metrics, equity-vs-benchmark chart, and trade history
- in-app About & guide tab explaining inputs, assumptions, and result metrics
- clickable metric cards with buy-and-hold comparisons and clearer chart axes/legend
- browser strategy builder for optional price-trend, ROC momentum, and volatility filters with configurable entry/exit logic

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

Yahoo is used as a convenient free research source, not as a licensed production market-data feed. The adapter captures OHLCV, adjusted close, and dividend/split events when supplied, but the engine does not yet maintain its own corporate-action ledger. Yahoo's historical OHLC behavior around splits is provider-specific, so real-data results should still be treated as research-grade.

Indicator warm-up is fetched automatically before the selected start date. Warm-up bars are used only for indicator state; portfolio accounting, benchmark construction, and reported performance remain constrained to the selected experiment dates.

## Tests

The tests use small deterministic datasets so expected fills, cash balances, signals, equity, benchmark values, and metrics can be checked directly.
