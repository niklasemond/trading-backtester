"""Application service orchestrating one complete backtest experiment."""

from __future__ import annotations

from dataclasses import dataclass

from backtest_app.analytics.engine import analyze_backtest
from backtest_app.domain.analytics import BacktestAnalysis
from backtest_app.domain.backtest import BacktestResult
from backtest_app.domain.experiment import ExperimentSpec
from backtest_app.market_data.provider import MarketDataProvider, MarketDataRequest
from backtest_app.execution.engine import run_backtest


@dataclass(frozen=True)
class CompletedBacktest:
    experiment: ExperimentSpec
    execution: BacktestResult
    analysis: BacktestAnalysis
    data_provider: str


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

    strategy = experiment.strategy
    backtest = experiment.backtest
    market_data = await provider.get_history(
        MarketDataRequest(
            symbol=strategy.symbols[0],
            start_date=backtest.start_date,
            end_date=backtest.end_date,
            frequency=strategy.frequency,
        )
    )
    execution = run_backtest(strategy, backtest, market_data)
    analysis = analyze_backtest(execution, strategy, backtest, market_data)
    return CompletedBacktest(
        experiment=experiment,
        execution=execution,
        analysis=analysis,
        data_provider=market_data.metadata.provider,
    )
