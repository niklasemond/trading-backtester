"""FastAPI application exposing the backtesting service."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, FastAPI, HTTPException, Request, status

from backtest_app.api.models import BacktestResponse, HealthResponse
from backtest_app.domain.experiment import ExperimentSpec
from backtest_app.market_data.provider import MarketDataProvider
from backtest_app.services.backtests import execute_experiment

ProviderResolver = Callable[[str], MarketDataProvider]


def _unconfigured_provider_resolver(name: str) -> MarketDataProvider:
    raise LookupError(
        f"market data provider {name!r} is not configured; "
        "register a provider resolver when creating the application"
    )


def create_app(provider_resolver: ProviderResolver | None = None) -> FastAPI:
    """Application factory to keep provider selection injectable and testable."""

    resolver = provider_resolver or _unconfigured_provider_resolver

    app = FastAPI(
        title="Trading Backtester API",
        version="0.1.0",
        description="Validated single-asset backtesting API with explicit next-bar execution.",
    )
    app.state.provider_resolver = resolver

    def resolve_provider(request: Request, experiment: ExperimentSpec) -> MarketDataProvider:
        try:
            return request.app.state.provider_resolver(experiment.requested_data_provider)
        except LookupError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from exc

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    async def health() -> HealthResponse:
        return HealthResponse()

    @app.post("/api/v1/backtests", response_model=BacktestResponse, tags=["backtests"])
    async def backtest(
        experiment: ExperimentSpec,
        provider: MarketDataProvider = Depends(resolve_provider),
    ) -> BacktestResponse:
        try:
            completed = await execute_experiment(experiment, provider)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from exc

        return BacktestResponse(
            experiment=completed.experiment,
            execution=completed.execution,
            analysis=completed.analysis,
            data_provider=completed.data_provider,
        )

    return app


app = create_app()
