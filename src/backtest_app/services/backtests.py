"""Application service orchestrating one complete backtest experiment."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from backtest_app.analytics.engine import analyze_backtest
from backtest_app.domain.analytics import BacktestAnalysis
from backtest_app.domain.backtest import BacktestResult
from backtest_app.domain.experiment import ExperimentSpec
from backtest_app.domain.strategy import SmaIndicator, StrategySpec
from backtest_app.execution.engine import run_backtest
from backtest_app.market_data.provider import MarketDataProvider, MarketDataRequest


@dataclass(frozen=True)
class CompletedBacktest:
    experiment: ExperimentSpec
    execution: BacktestResult
    analysis: BacktestAnalysis
    data_provider: str


def required_warmup_bars(strategy: StrategySpec) -> int:
    """Return the pre-period observations needed for first-bar crossover state.

    A crossover on the first in-range bar compares indicator values from that
    bar and the immediately preceding bar. For a trailing SMA with window N,
    N complete pre-start observations are therefore sufficient to make the
    prior-bar SMA available without using any in-period future information.
    """

    windows = [
        indicator.window
        for indicator in strategy.indicators
        if isinstance(indicator, SmaIndicator)
    ]
    return max(windows, default=0)


def _warmup_calendar_days(warmup_bars: int) -> int:
    """Translate trading observations into a conservative calendar lookback.

    Daily US-equity history contains weekends and exchange holidays. Two
    calendar days per requested observation plus ten extra days comfortably
    covers ordinary closures while keeping the initial provider request small.
    The caller verifies the actual number of returned pre-start bars and expands
    adaptively if needed.
    """

    return max(14, warmup_bars * 2 + 10)


async def _get_history_with_warmup(
    experiment: ExperimentSpec,
    provider: MarketDataProvider,
):
    strategy = experiment.strategy
    backtest = experiment.backtest
    required = required_warmup_bars(strategy)

    if required == 0:
        return await provider.get_history(
            MarketDataRequest(
                symbol=strategy.symbols[0],
                start_date=backtest.start_date,
                end_date=backtest.end_date,
                frequency=strategy.frequency,
            )
        )

    lookback_days = _warmup_calendar_days(required)
    last_earliest = None
    market_data = None

    # Four attempts is intentionally bounded. In normal daily US-equity data the
    # first request is sufficient even for common long windows (e.g. SMA 200).
    for _ in range(4):
        request = MarketDataRequest(
            symbol=strategy.symbols[0],
            start_date=backtest.start_date - timedelta(days=lookback_days),
            end_date=backtest.end_date,
            frequency=strategy.frequency,
        )
        market_data = await provider.get_history(request)
        pre_start = [
            bar for bar in market_data.bars if bar.timestamp.date() < backtest.start_date
        ]
        if len(pre_start) >= required:
            break

        earliest = market_data.bars[0].timestamp if market_data.bars else None
        if earliest is None or earliest == last_earliest:
            # No evidence that requesting farther back yields more history (for
            # example a newly listed security). Proceed with the available bars;
            # indicator warm-up rules will naturally suppress unavailable signals.
            break
        last_earliest = earliest
        lookback_days *= 2

    assert market_data is not None
    return market_data


async def execute_experiment(
    experiment: ExperimentSpec,
    provider: MarketDataProvider,
) -> CompletedBacktest:
    """Fetch canonical data and run one validated experiment end-to-end."""

    if provider.name != experiment.requested_data_provider:
        raise ValueError(
            f"requested provider {experiment.requested_data_provider!r} "
            f"does not match resolved provider {provider.name!r}"
        )

    market_data = await _get_history_with_warmup(experiment, provider)
    execution = run_backtest(experiment.strategy, experiment.backtest, market_data)
    analysis = analyze_backtest(
        execution, experiment.strategy, experiment.backtest, market_data
    )
    return CompletedBacktest(
        experiment=experiment,
        execution=execution,
        analysis=analysis,
        data_provider=market_data.metadata.provider,
    )
