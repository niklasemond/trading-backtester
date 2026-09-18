# Built-in instrument library

The Backtest UI includes a deliberately small set of liquid US-listed ETFs:

| Symbol | Exposure | Research role |
| --- | --- | --- |
| SPY | S&P 500 / broad US large-cap equity | Baseline US-equity market |
| QQQ | Nasdaq-100 / growth-heavy US equity | Momentum and growth-sensitive regimes |
| IWM | Russell 2000 / US small caps | Cyclical and higher-volatility equity behavior |
| TLT | Long-duration US Treasuries | Interest-rate and bond-trend regimes |
| GLD | Gold | Non-equity real-asset trends |
| EFA | Developed equities outside US/Canada | Geographic portability |
| EEM | Emerging-market equities | Different macro, currency, and volatility regimes |
| HYG | High-yield corporate bonds | Credit and risk-appetite behavior |

All remain single-asset backtests. The application does not yet construct a
multi-asset portfolio from these instruments.

## Worked historical examples

SPY retains its existing 2000-01-03 through 2025-12-31 worked examples.

The seven added ETFs use one common calibration period:
2008-01-02 through 2025-12-31, with $100,000 starting capital, $0 fixed
commission, 5 bps slippage, whole-share sizing, and SMA/trend rules only.

The example labels are descriptive of the tested historical grid:

- **Weak**: a deliberately poor historical candidate.
- **Good**: a candidate near buy-and-hold performance, useful as a middle case.
- **Strong**: the strongest excess-return result found in the bounded tested grid.

"Strong" means strongest among the tested historical candidates. It does not
mean the rule is expected to outperform in the future. If even the strongest
tested candidate lags buy-and-hold, the UI says so explicitly.

ROC and volatility filters are intentionally excluded from these calibrations
until the separate warm-up audit item is completed.

## Provider validation

Run:

```bash
python scripts/validate_instruments.py
```

The live smoke check requests a completed historical window from Yahoo for all
eight built-ins. Creation of the canonical `MarketDataSet` enforces:

- timezone-aware timestamps;
- positive and internally consistent OHLC values;
- matching symbols;
- strict chronological ordering;
- no duplicate timestamps.

The script additionally reports bar coverage, adjusted-close coverage, and
dividend/split event counts.

This check is provider-facing and network-dependent. Deterministic tests remain
the source of truth for engine semantics such as incomplete-session exclusion,
corporate-action accounting, signals, and execution timing.
