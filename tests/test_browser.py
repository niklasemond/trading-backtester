from fastapi.testclient import TestClient

from backtest_app.api.app import create_app
from test_api import ApiTestProvider


def test_browser_root_serves_backtest_form() -> None:
    client = TestClient(create_app(lambda _: ApiTestProvider()))

    response = client.get("/")

    assert response.status_code == 200
    assert "Trading Backtester" in response.text
    assert 'id="backtest-form"' in response.text
    assert "/api/v1/backtests" in response.text
