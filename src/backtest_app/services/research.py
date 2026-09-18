"""Bounded grid search with a chronological holdout period."""

from __future__ import annotations

from datetime import timedelta
from itertools import product

from backtest_app.analytics.engine import analyze_backtest
from backtest_app.domain.experiment import BacktestConfig
from backtest_app.domain.research import (
    SearchParameters,
    SearchPeriodResult,
    StrategySearchCandidate,
    StrategySearchRequest,
    StrategySearchResponse,
)
from backtest_app.domain.strategy import (
    ComparisonCondition,
    ConstantRef,
    CrossoverCondition,
    IndicatorRef,
    PriceRef,
    RocIndicator,
    SmaIndicator,
    StrategySpec,
    VolatilityIndicator,
)
from backtest_app.execution.engine import run_backtest
from backtest_app.market_data.provider import MarketDataProvider, MarketDataRequest
from backtest_app.services.backtests import _warmup_calendar_days


def _candidate_parameters(request: StrategySearchRequest):
    space = request.search_space
    for fast, slow, trend, momentum_window, volatility_window in product(
        space.fast_windows,
        space.slow_windows,
        space.trend_filter_options,
        space.momentum_windows,
        space.volatility_windows,
    ):
        if slow <= fast:
            continue
        momentum_thresholds = (
            space.momentum_thresholds if momentum_window is not None else (None,)
        )
        volatility_thresholds = (
            space.volatility_thresholds if volatility_window is not None else (None,)
        )
        for momentum_threshold, volatility_threshold in product(
            momentum_thresholds, volatility_thresholds
        ):
            yield SearchParameters(
                fast_window=fast,
                slow_window=slow,
                trend_filter=trend,
                momentum_window=momentum_window,
                momentum_threshold=momentum_threshold,
                volatility_window=volatility_window,
                volatility_threshold=volatility_threshold,
                momentum_exit=space.momentum_exit and momentum_window is not None,
                volatility_exit=space.volatility_exit and volatility_window is not None,
            )


def _strategy(symbol: str, params: SearchParameters) -> StrategySpec:
    fast = IndicatorRef(id="fast")
    slow = IndicatorRef(id="slow")
    indicators = [
        SmaIndicator(id="fast", window=params.fast_window),
        SmaIndicator(id="slow", window=params.slow_window),
    ]
    entry = [CrossoverCondition(left=fast, operator="crosses_above", right=slow)]
    exit_conditions = [
        CrossoverCondition(left=fast, operator="crosses_below", right=slow)
    ]

    if params.trend_filter:
        entry.append(ComparisonCondition(left=PriceRef(), operator="above", right=slow))

    if params.momentum_window is not None:
        momentum = IndicatorRef(id="momentum")
        threshold = ConstantRef(value=float(params.momentum_threshold or 0.0))
        indicators.append(RocIndicator(id="momentum", window=params.momentum_window))
        entry.append(
            ComparisonCondition(left=momentum, operator="above", right=threshold)
        )
        if params.momentum_exit:
            exit_conditions.append(
                ComparisonCondition(left=momentum, operator="below", right=threshold)
            )

    if params.volatility_window is not None:
        volatility = IndicatorRef(id="volatility")
        threshold = ConstantRef(value=float(params.volatility_threshold or 0.0))
        indicators.append(
            VolatilityIndicator(id="volatility", window=params.volatility_window)
        )
        entry.append(
            ComparisonCondition(left=volatility, operator="below", right=threshold)
        )
        if params.volatility_exit:
            exit_conditions.append(
                ComparisonCondition(left=volatility, operator="above", right=threshold)
            )

    return StrategySpec(
        schema_version="1.1",
        name="bounded filtered trend search",
        symbols=(symbol,),
        indicators=tuple(indicators),
        entry_conditions=tuple(entry),
        exit_conditions=tuple(exit_conditions),
        entry_logic="all",
        exit_logic="any" if len(exit_conditions) > 1 else "all",
    )


def _period_result(
    strategy: StrategySpec, config: BacktestConfig, market_data
) -> SearchPeriodResult:
    execution = run_backtest(strategy, config, market_data)
    analysis = analyze_backtest(execution, strategy, config, market_data)
    return SearchPeriodResult(
        strategy_metrics=analysis.strategy_metrics,
        benchmark_metrics=analysis.benchmark_metrics,
        excess_total_return=(
            analysis.strategy_metrics.total_return
            - analysis.benchmark_metrics.total_return
        ),
    )


def _score(candidate: StrategySearchCandidate, objective: str) -> float:
    metrics = candidate.training.strategy_metrics
    if objective == "total_return":
        return metrics.total_return
    if objective == "sharpe_ratio":
        return (
            metrics.sharpe_ratio
            if metrics.sharpe_ratio is not None
            else float("-inf")
        )
    if objective == "max_drawdown":
        return -metrics.max_drawdown
    raise ValueError(f"unsupported objective: {objective}")


async def search_strategies(
    request: StrategySearchRequest,
    provider: MarketDataProvider,
) -> StrategySearchResponse:
    """Search on training history and report untouched chronological validation results."""

    if provider.name != request.requested_data_provider:
        raise ValueError(
            f"requested provider {request.requested_data_provider!r} does not match "
            f"resolved provider {provider.name!r}"
        )

    params = list(_candidate_parameters(request))
    if len(params) > request.max_candidates:
        raise ValueError(
            f"search expands to {len(params)} candidates, above max_candidates="
            f"{request.max_candidates}; narrow the grid"
        )
    if not params:
        raise ValueError("search space produced no valid candidates")

    max_window = max(
        max(
            p.fast_window,
            p.slow_window,
            p.momentum_window or 0,
            p.volatility_window or 0,
        )
        for p in params
    )
    market_data = await provider.get_history(
        MarketDataRequest(
            symbol=request.symbol,
            start_date=request.start_date
            - timedelta(days=_warmup_calendar_days(max_window)),
            end_date=request.end_date,
        )
    )

    training_config = BacktestConfig(
        start_date=request.start_date,
        end_date=request.validation_start_date - timedelta(days=1),
        starting_capital=request.starting_capital,
        costs=request.costs,
    )
    validation_config = BacktestConfig(
        start_date=request.validation_start_date,
        end_date=request.end_date,
        starting_capital=request.starting_capital,
        costs=request.costs,
    )

    evaluated: list[StrategySearchCandidate] = []
    skipped = 0
    for parameter_set in params:
        strategy = _strategy(request.symbol, parameter_set)
        try:
            training = _period_result(strategy, training_config, market_data)
            validation = _period_result(strategy, validation_config, market_data)
        except ValueError:
            skipped += 1
            continue
        evaluated.append(
            StrategySearchCandidate(
                rank=0,
                parameters=parameter_set,
                training=training,
                validation=validation,
            )
        )

    evaluated.sort(key=lambda item: _score(item, request.objective), reverse=True)
    top = tuple(
        item.model_copy(update={"rank": index})
        for index, item in enumerate(evaluated[: request.top_n], start=1)
    )
    return StrategySearchResponse(
        symbol=request.symbol,
        objective=request.objective,
        training_start_date=training_config.start_date,
        training_end_date=training_config.end_date,
        validation_start_date=validation_config.start_date,
        validation_end_date=validation_config.end_date,
        evaluated_candidates=len(evaluated),
        skipped_candidates=skipped,
        data_provider=market_data.metadata.provider,
        candidates=top,
    )
