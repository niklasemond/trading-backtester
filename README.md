# Trading Backtester

A modular trading-strategy backtesting application. The first milestone is a browser-based SPY SMA-crossover backtest with correct next-bar execution, benchmark comparison, analytics, and saved experiments.

## Current status

Iteration 5 is complete. The project now includes the versioned strategy/domain foundation, deterministic SMA/crossover signal generation, a single-asset long-only execution/portfolio engine, performance analytics, and an executable buy-and-hold benchmark. Close-derived signals execute only at the next observed bar's open, with configurable fixed commissions, adverse slippage, all-in sizing, trade records, cash accounting, and end-of-bar equity curves.

Analytics now include total return, CAGR, annualized volatility, Sharpe ratio, maximum drawdown, completed-trade count, and a benchmark curve using the same entry-cost and sizing assumptions. FastAPI now exposes the complete tested pipeline; the browser frontend and live/free data-provider wiring follow next.

## Development

```bash
cd /mnt/data/trading-backtester
python -m pytest
```

The source package uses a `src/` layout. Tests use small deterministic datasets so timing, fills, cash, positions, and equity can be checked exactly.

## FastAPI (Iteration 5)

The HTTP layer is now available and deliberately contains no backtesting logic. It validates an `ExperimentSpec`, resolves a market-data provider, runs the existing application service, and serializes the execution + analytics result.

Start the API locally with:

```bash
uvicorn backtest_app.api.app:app --app-dir src --reload
```

Then open:

- `http://127.0.0.1:8000/docs` for the interactive OpenAPI/Swagger UI
- `http://127.0.0.1:8000/health` for the health check

The default app intentionally has no live/free market-data provider registered yet, so `/api/v1/backtests` will return a clear 422 until a provider is configured. Tests inject a deterministic provider and exercise the complete API pipeline. The next provider/frontend iteration will wire a user-facing data source into the same boundary without changing the backtesting engine.
