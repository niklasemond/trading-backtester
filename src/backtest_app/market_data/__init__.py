"""Market-data provider abstraction and built-in adapters."""

from .provider import MarketDataProvider, MarketDataRequest
from .yahoo import MarketDataProviderError, YahooFinanceProvider

__all__ = [
    "MarketDataProvider",
    "MarketDataProviderError",
    "MarketDataRequest",
    "YahooFinanceProvider",
]
