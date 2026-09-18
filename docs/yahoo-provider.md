# Yahoo Finance provider notes

The built-in free historical-data adapter is identified as `yahoo`.

- It uses Yahoo Finance's chart-v8 endpoint for daily history.
- HTTP/JSON handling is isolated in `market_data/yahoo.py`; the engine only consumes canonical `MarketDataSet` objects.
- The adapter preserves the application's inclusive end-date contract by sending Yahoo an exclusive `period2` equal to the day after `end_date`.
- Quote OHLCV is stored as delivered and is the canonical tradable/mark-to-market price series.
- Yahoo adjusted close is stored separately. It is not used for execution or portfolio equity.
- Dividend and split events are mapped onto canonical bars when Yahoo supplies them.
- Rows missing required OHLCV values are skipped rather than forward-filled or synthesized.
- External-provider failures are surfaced through the API and are never replaced with fabricated prices.

## Corporate-action semantics

Yahoo's public help describes adjusted close as a historical close adjusted for both split and dividend distributions. The backtester does **not** use that field for portfolio accounting because the engine now applies explicit corporate actions instead.

For canonical Yahoo bars:

1. a split event is treated as effective before the event-date open and multiplies an already-held share quantity;
2. a dividend event is treated as an ex-date entitlement and credits cash to shares held entering that session;
3. a position opened at the event-date open does not receive that event-date dividend;
4. if both events occur on one bar, split is applied before dividend;
5. the same policy is used for the strategy and executable buy-and-hold benchmark.

This is an economic total-return convention, not a claim about actual broker payment-date cash availability. Yahoo chart events provide event dates, not a complete settlement/payment calendar.

## Provider uncertainty

Yahoo's adjusted-close documentation is clear, but the chart-v8 endpoint used here is not a licensed production feed with a formal schema guarantee for every historical raw OHLC/corporate-action edge case. The adapter therefore records its assumptions in metadata and does not silently repair provider data.

The yfinance project separately documents repairs for occasional missing dividend adjustments, split adjustments, and other Yahoo price anomalies. That is a reason to keep this provider research-grade even though the engine's own accounting is now internally consistent.

Useful references:

- Yahoo Help, "What is the adjusted close?": https://help.yahoo.com/kb/SLN28256.html
- Yahoo Help, historical price/dividend/split data: https://help.yahoo.com/kb/sln2311.html
- yfinance price repair notes: https://ranaroussi.github.io/yfinance/advanced/price_repair.html

The browser UI remains a thin client. It creates the same versioned `StrategySpec` used by API clients; no signal, execution, accounting, or analytics logic lives in the browser.
