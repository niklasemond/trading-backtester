from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from backtest_app.api.app import create_app
from backtest_app.domain.market_data import MarketBar, MarketDataMetadata, MarketDataSet
from backtest_app.market_data.provider import MarketDataProvider, MarketDataRequest


class ApiTestProvider(MarketDataProvider):
    @property
    def name(self) -> str:
        return "api-test"

    async def get_history(self, request: MarketDataRequest) -> MarketDataSet:
        closes = (10, 9, 8, 9, 11, 10, 8, 7)
        opens = (10, 9, 8, 9, 11, 20, 8, 5)
        start = datetime(2024, 1, 2, tzinfo=UTC)
        bars = tuple(
            MarketBar(
                timestamp=start + timedelta(days=index),
                symbol=request.symbol,
                open=open_price,
                high=max(open_price, close_price) + 1,
                low=min(open_price, close_price) * 0.5,
                close=close_price,
                volume=1_000,
            )
            for index, (open_price, close_price) in enumerate(
                zip(opens, closes, strict=True)
            )
        )
        return MarketDataSet(
            symbol=request.symbol,
            bars=bars,
            metadata=MarketDataMetadata(
                provider=self.name,
                retrieved_at=datetime(2024, 1, 1, tzinfo=UTC),
            ),
        )


def payload(provider: str = "api-test") -> dict:
    return {
        "strategy": {
            "schema_version": "1.0",
            "name": "2/3 SMA crossover",
            "symbols": ["SPY"],
            "frequency": "1d",
            "direction": "long_only",
            "indicators": [
                {"type": "sma", "id": "fast", "source": "close", "window": 2},
                {"type": "sma", "id": "slow", "source": "close", "window": 3},
            ],
            "entry_conditions": [
                {
                    "type": "crossover",
                    "left": {"kind": "indicator", "id": "fast"},
                    "operator": "crosses_above",
                    "right": {"kind": "indicator", "id": "slow"},
                }
            ],
            "exit_conditions": [
                {
                    "type": "crossover",
                    "left": {"kind": "indicator", "id": "fast"},
                    "operator": "crosses_below",
                    "right": {"kind": "indicator", "id": "slow"},
                }
            ],
            "position_sizing": {
                "type": "all_in",
                "cash_buffer_fraction": 0,
                "allow_fractional_shares": False,
            },
            "execution": {
                "signal_price": "close",
                "execution_bar": "next_bar",
                "execution_price": "open",
            },
        },
        "backtest": {
            "start_date": "2024-01-02",
            "end_date": "2024-01-09",
            "starting_capital": 1000,
            "costs": {
                "commission_type": "fixed_per_order",
                "commission_amount": 0,
                "slippage_bps": 0,
            },
        },
        "requested_data_provider": provider,
    }


def test_health_endpoint() -> None:
    client = TestClient(create_app(lambda _: ApiTestProvider()))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "api_version": "1"}


def test_backtest_endpoint_runs_complete_pipeline() -> None:
    client = TestClient(create_app(lambda _: ApiTestProvider()))

    response = client.post("/api/v1/backtests", json=payload())

    assert response.status_code == 200
    body = response.json()
    assert body["data_provider"] == "api-test"
    assert [trade["side"] for trade in body["execution"]["trades"]] == ["buy", "sell"]
    assert body["execution"]["trades"][0]["execution_timestamp"].startswith("2024-01-07")
    assert body["execution"]["final_cash"] == 250.0
    assert body["analysis"]["strategy_metrics"]["total_return"] == -0.75
    assert len(body["analysis"]["benchmark"]["equity_curve"]) == 8


def test_unknown_provider_returns_422() -> None:
    def resolver(name: str) -> MarketDataProvider:
        raise LookupError(f"unknown provider: {name}")

    client = TestClient(create_app(resolver))

    response = client.post("/api/v1/backtests", json=payload("missing"))

    assert response.status_code == 422
    assert "unknown provider" in response.json()["detail"]


def test_invalid_strategy_is_rejected_before_execution() -> None:
    client = TestClient(create_app(lambda _: ApiTestProvider()))
    body = payload()
    body["strategy"]["indicators"][0]["window"] = 0

    response = client.post("/api/v1/backtests", json=body)

    assert response.status_code == 422
