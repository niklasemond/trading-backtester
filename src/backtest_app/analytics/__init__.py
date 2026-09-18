"""Performance analytics and benchmark construction."""

from .engine import analyze_backtest, calculate_metrics, create_buy_and_hold_benchmark

__all__ = [
    "analyze_backtest",
    "calculate_metrics",
    "create_buy_and_hold_benchmark",
]
