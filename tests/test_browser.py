from fastapi.testclient import TestClient

from backtest_app.api.app import create_app
from test_api import ApiTestProvider


def test_browser_root_serves_backtest_form_and_guide() -> None:
    client = TestClient(create_app(lambda _: ApiTestProvider()))

    response = client.get("/")

    assert response.status_code == 200
    assert "Trading Backtester" in response.text
    assert 'id="backtest-form"' in response.text
    assert "About &amp; guide" in response.text
    assert 'id="guide-view"' in response.text
    assert "/api/v1/backtests" in response.text


def test_browser_contains_metric_explainer_and_clear_chart_axes() -> None:
    client = TestClient(create_app(lambda _: ApiTestProvider()))

    response = client.get("/")

    assert 'id="metric-detail"' in response.text
    assert "Click for details" in response.text
    assert "Buy &amp; hold" in response.text
    assert "Y-axis: portfolio value" in response.text
    assert "X-axis: calendar date" in response.text
    assert "Portfolio value" in response.text
