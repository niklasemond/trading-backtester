"""Built-in instrument catalog used for validation and documentation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InstrumentDefinition:
    symbol: str
    name: str
    category: str
    research_use: str


BUILT_IN_INSTRUMENTS: tuple[InstrumentDefinition, ...] = (
    InstrumentDefinition("SPY", "S&P 500", "US equity", "Broad US large-cap baseline."),
    InstrumentDefinition("QQQ", "Nasdaq-100", "US growth equity", "Growth/technology-sensitive equity regime."),
    InstrumentDefinition("IWM", "Russell 2000", "US small-cap equity", "Cyclical and higher-volatility equity regime."),
    InstrumentDefinition("TLT", "Long US Treasuries", "Government bonds", "Long-duration rate-sensitive bond regime."),
    InstrumentDefinition("GLD", "Gold", "Commodity / real asset", "Non-equity real-asset trend regime."),
    InstrumentDefinition("EFA", "Developed ex-US equities", "International equity", "Developed-market geographic diversification."),
    InstrumentDefinition("EEM", "Emerging markets", "Emerging equity", "Macro/currency-sensitive emerging-market regime."),
    InstrumentDefinition("HYG", "High-yield credit", "Credit", "Credit-risk and rate-sensitive regime."),
)

BUILT_IN_SYMBOLS: tuple[str, ...] = tuple(item.symbol for item in BUILT_IN_INSTRUMENTS)
