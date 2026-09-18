# Yahoo Finance provider notes

Iteration 6 adds the first built-in free historical-data adapter, identified as `yahoo`.

- It uses Yahoo Finance's public chart endpoint for daily history.
- HTTP/JSON handling is isolated in `market_data/yahoo.py`; the engine only consumes canonical `MarketDataSet` objects.
- The adapter preserves the application's inclusive end-date contract by sending Yahoo an exclusive `period2` equal to the day after `end_date`.
- Adjusted close is stored separately, while dividend and split events are mapped onto canonical bars when Yahoo supplies them.
- Rows missing required OHLCV values are skipped rather than forward-filled or synthesized.
- Yahoo historical OHLC behavior around splits is provider-specific and may already reflect split adjustments. That caveat is recorded in retrieval metadata.
- The backtester still does not maintain an independent corporate-action ledger, so real-data results remain research-grade rather than production total-return accounting.
- External-provider failures are surfaced through the API and are never replaced with fabricated prices.

The bundled browser UI is thin HTML/JavaScript served by FastAPI. It creates the same versioned `StrategySpec` used by API clients; no signal, execution, accounting, or analytics logic lives in the browser.

A known limitation remains: indicator warm-up begins at the selected start date. Pre-start warm-up retrieval should be added later while keeping portfolio accounting constrained to the requested experiment range.
