"""FastAPI application exposing the backtesting service and browser UI."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse

from backtest_app.api.models import BacktestResponse, HealthResponse
from backtest_app.domain.experiment import ExperimentSpec
from backtest_app.domain.research import StrategySearchRequest, StrategySearchResponse
from backtest_app.market_data import MarketDataProviderError, YahooFinanceProvider
from backtest_app.market_data.provider import MarketDataProvider
from backtest_app.services.backtests import execute_experiment
from backtest_app.services.research import search_strategies

ProviderResolver = Callable[[str], MarketDataProvider]
_WEB_INDEX = Path(__file__).parents[1] / "web" / "index.html"


def default_provider_resolver(name: str) -> MarketDataProvider:
    """Resolve built-in data providers without leaking provider logic into routes."""

    if name == "yahoo":
        return YahooFinanceProvider()
    raise LookupError(f"unknown market data provider: {name!r}")


def create_app(provider_resolver: ProviderResolver | None = None) -> FastAPI:
    """Application factory to keep provider selection injectable and testable."""

    resolver = provider_resolver or default_provider_resolver

    app = FastAPI(
        title="Trading Backtester API",
        version="0.2.0",
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

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def browser_app() -> HTMLResponse:
        return HTMLResponse(_WEB_INDEX.read_text(encoding="utf-8"))

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
        except MarketDataProviderError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc
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

    @app.post(
        "/api/v1/research/search",
        response_model=StrategySearchResponse,
        tags=["research"],
    )
    async def research_search(search: StrategySearchRequest) -> StrategySearchResponse:
        try:
            provider = app.state.provider_resolver(search.requested_data_provider)
            return await search_strategies(search, provider)
        except LookupError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc
        except MarketDataProviderError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc

    return app


app = create_app()
