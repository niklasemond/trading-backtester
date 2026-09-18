# Trading Backtester

A modular trading-strategy backtesting application. The first milestone is a browser-based SPY SMA-crossover backtest with correct next-bar execution, benchmark comparison, analytics, and saved experiments.

## Current status

Iteration 4 is complete. The project now includes the versioned strategy/domain foundation, deterministic SMA/crossover signal generation, a single-asset long-only execution/portfolio engine, performance analytics, and an executable buy-and-hold benchmark. Close-derived signals execute only at the next observed bar's open, with configurable fixed commissions, adverse slippage, all-in sizing, trade records, cash accounting, and end-of-bar equity curves.

Analytics now include total return, CAGR, annualized volatility, Sharpe ratio, maximum drawdown, completed-trade count, and a benchmark curve using the same entry-cost and sizing assumptions. There is intentionally no browser UI yet; FastAPI is the next major iteration and the browser frontend follows after that.

## Development

```bash
cd /mnt/data/trading-backtester
python -m pytest
```

The source package uses a `src/` layout. Tests use small deterministic datasets so timing, fills, cash, positions, and equity can be checked exactly.
