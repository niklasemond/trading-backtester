"""Live data-quality smoke check for the built-in ETF library.

This script intentionally hits the configured free Yahoo adapter. Canonical
Pydantic validation already enforces positive/consistent OHLC, timezone-aware
timestamps, matching symbols, strict ordering, and duplicate rejection.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date

from backtest_app.market_data.provider import MarketDataRequest
from backtest_app.market_data.yahoo import MarketDataProviderError, YahooFinanceProvider

BUILT_IN_INSTRUMENTS = ("SPY", "QQQ", "IWM", "TLT", "GLD", "EFA", "EEM", "HYG")


async def validate_symbol(
    provider: YahooFinanceProvider,
    symbol: str,
    *,
    start_date: date,
    end_date: date,
) -> dict[str, object]:
    data = await provider.get_history(
        MarketDataRequest(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )
    )
    if not data.bars:
        raise RuntimeError(f"{symbol}: provider returned no completed daily bars")

    timestamps = [bar.timestamp for bar in data.bars]
    if timestamps != sorted(timestamps):
        raise RuntimeError(f"{symbol}: canonical bars are not strictly ordered")
    if len(timestamps) != len(set(timestamps)):
        raise RuntimeError(f"{symbol}: duplicate canonical timestamps detected")

    return {
        "symbol": symbol,
        "provider": data.metadata.provider,
        "bars": len(data.bars),
        "first": data.bars[0].timestamp.date().isoformat(),
        "last": data.bars[-1].timestamp.date().isoformat(),
        "adjusted_close_present": sum(bar.adjusted_close is not None for bar in data.bars),
        "dividend_events": sum(bar.dividend is not None and bar.dividend > 0 for bar in data.bars),
        "split_events": sum(bar.split_ratio is not None and bar.split_ratio != 1 for bar in data.bars),
    }


async def main(start_date: date, end_date: date) -> int:
    provider = YahooFinanceProvider()
    failures = 0
    for symbol in BUILT_IN_INSTRUMENTS:
        try:
            result = await validate_symbol(
                provider,
                symbol,
                start_date=start_date,
                end_date=end_date,
            )
            print(json.dumps({"status": "ok", **result}, sort_keys=True))
        except (MarketDataProviderError, RuntimeError, ValueError) as exc:
            failures += 1
            print(json.dumps({"status": "error", "symbol": symbol, "error": str(exc)}))
    print(json.dumps({"validated": len(BUILT_IN_INSTRUMENTS), "failures": failures}))
    return 1 if failures else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=date.fromisoformat, default=date(2024, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2025, 12, 31))
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.start, args.end)))
