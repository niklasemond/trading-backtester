from fastapi.testclient import TestClient

from backtest_app.api.app import create_app
from test_api import ApiTestProvider


def test_api_accepts_filtered_strategy_spec_v11_payload() -> None:
    client = TestClient(create_app(lambda _: ApiTestProvider()))
    payload = {
        "strategy": {
            "schema_version": "1.1",
            "name": "filtered trend",
            "symbols": ["SPY"],
            "frequency": "1d",
            "direction": "long_only",
            "indicators": [
                {"type": "sma", "id": "fast", "source": "close", "window": 2},
                {"type": "sma", "id": "slow", "source": "close", "window": 3},
                {"type": "roc", "id": "momentum", "source": "close", "window": 2},
                {"type": "volatility", "id": "volatility", "source": "close", "window": 2, "annualization_factor": 252},
            ],
            "entry_conditions": [
                {"type": "crossover", "left": {"kind": "indicator", "id": "fast"}, "operator": "crosses_above", "right": {"kind": "indicator", "id": "slow"}},
                {"type": "comparison", "left": {"kind": "price", "field": "close"}, "operator": "above", "right": {"kind": "indicator", "id": "slow"}},
                {"type": "comparison", "left": {"kind": "indicator", "id": "momentum"}, "operator": "above", "right": {"kind": "constant", "value": 0.0}},
                {"type": "comparison", "left": {"kind": "indicator", "id": "volatility"}, "operator": "below", "right": {"kind": "constant", "value": 1.0}},
            ],
            "exit_conditions": [
                {"type": "crossover", "left": {"kind": "indicator", "id": "fast"}, "operator": "crosses_below", "right": {"kind": "indicator", "id": "slow"}},
                {"type": "comparison", "left": {"kind": "indicator", "id": "momentum"}, "operator": "below", "right": {"kind": "constant", "value": 0.0}},
            ],
            "entry_logic": "all",
            "exit_logic": "any",
            "position_sizing": {"type": "all_in", "cash_buffer_fraction": 0.0, "allow_fractional_shares": False},
            "execution": {"signal_price": "close", "execution_bar": "next_bar", "execution_price": "open"},
        },
        "backtest": {
            "start_date": "2024-01-02",
            "end_date": "2024-01-09",
            "starting_capital": 1000,
            "costs": {"commission_type": "fixed_per_order", "commission_amount": 0, "slippage_bps": 0},
        },
        "requested_data_provider": "api-test",
    }
    response = client.post("/api/v1/backtests", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["experiment"]["strategy"]["schema_version"] == "1.1"
    assert body["experiment"]["strategy"]["exit_logic"] == "any"
