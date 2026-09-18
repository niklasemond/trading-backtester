# Built-in instrument library

The Backtest UI includes eight built-in liquid ETF instruments while preserving an
`Other ticker…` fallback for arbitrary Yahoo-supported symbols.

| Ticker | Exposure | Research role |
| --- | --- | --- |
| SPY | S&P 500 | broad US large-cap baseline |
| QQQ | Nasdaq-100 | growth/technology-sensitive equity regime |
| IWM | Russell 2000 | small-cap/cyclical equity regime |
| TLT | long US Treasuries | rate-sensitive government-bond regime |
| GLD | gold | non-equity real-asset regime |
| EFA | developed ex-US equities | geographic diversification |
| EEM | emerging-market equities | macro/currency-sensitive equity regime |
| HYG | high-yield corporate bonds | credit/risk-appetite regime |

## Data-quality validation

`backtest_app.market_data.quality.validate_instrument_history` is the reusable
provider-validation entry point. It fetches a canonical dataset and reports:

- number of usable bars;
- first and last session dates;
- dividend and split event counts;
- adjusted-close coverage;
- presence of the provider's daily-bar completion policy metadata.

The canonical `MarketBar` and `MarketDataSet` models already reject invalid OHLC
ranges, naive timestamps, symbol mismatches, duplicate timestamps, and non-strict
ordering before the report is created.

Yahoo-specific tests separately cover current-session exclusion, exchange-local
date handling, corporate-action parsing, and the US regular-session fallback.

## Worked historical examples

SPY keeps its earlier 2000-01-03 through 2025-12-31 calibration. The other seven
built-ins use a shared 2008-01-02 through 2025-12-31 window, $100,000 starting
capital, $0 fixed commission, and 5 bps adverse slippage.

The candidate grid is deliberately interpretable: SMA fast windows
5/10/20/30/50/75/100, slow windows 50/75/100/150/200/250/300, and the optional
price-above-slow trend filter. Momentum and volatility filters are excluded until
their warm-up audit issue is resolved.

Weak / Typical / Strong are **relative labels inside each instrument's tested
candidate distribution**, not claims of investment quality or future performance.
Some Strong examples still lag buy-and-hold over the calibration period; the UI
states that explicitly.
