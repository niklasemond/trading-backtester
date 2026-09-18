from fastapi.testclient import TestClient

from backtest_app.api.app import create_app
from test_research import ResearchProvider


def test_research_search_endpoint_returns_training_and_validation_results() -> None:
    client = TestClient(create_app(lambda _: ResearchProvider()))
    payload = {
        "symbol": "SPY",
        "start_date": "2023-03-01",
        "validation_start_date": "2023-11-01",
        "end_date": "2024-02-20",
        "starting_capital": 100000,
        "requested_data_provider": "research-test",
        "objective": "total_return",
        "top_n": 2,
        "max_candidates": 100,
        "search_space": {
            "fast_windows": [2, 3],
            "slow_windows": [5],
            "trend_filter_options": [False, True],
            "momentum_windows": [None, 5],
            "momentum_thresholds": [0.0],
            "volatility_windows": [None],
            "volatility_thresholds": [0.3],
            "momentum_exit": True,
            "volatility_exit": False,
        },
    }

    response = client.post("/api/v1/research/search", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["evaluated_candidates"] == 8
    assert len(body["candidates"]) == 2
    assert body["candidates"][0]["rank"] == 1
    assert "training" in body["candidates"][0]
    assert "validation" in body["candidates"][0]
    assert "excess_total_return" in body["candidates"][0]["validation"]
