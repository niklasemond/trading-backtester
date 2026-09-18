from fastapi.testclient import TestClient

from backtest_app.api.app import create_app
from test_api import ApiTestProvider


def test_browser_root_serves_backtest_form_and_guide() -> None:
    client = TestClient(create_app(lambda _: ApiTestProvider()))

    response = client.get("/")

    assert response.status_code == 200
    assert "Trading Backtester" in response.text
    assert 'id="backtest-form"' in response.text
    assert ">About</button>" in response.text
    assert 'id="about-view"' in response.text
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


def test_browser_exposes_strategy_spec_v11_builder_controls() -> None:
    client = TestClient(create_app(lambda _: ApiTestProvider()))
    response = client.get("/")
    assert 'id="trend-filter"' in response.text
    assert 'id="momentum-entry"' in response.text
    assert 'id="momentum-exit"' in response.text
    assert 'id="vol-entry"' in response.text
    assert 'id="vol-exit"' in response.text
    assert 'id="entry-logic"' in response.text
    assert 'id="exit-logic"' in response.text
    assert "schema_version:advanced?'1.1':'1.0'" in response.text
    assert "type:'roc'" in response.text
    assert "type:'volatility'" in response.text
    assert "kind:'constant'" in response.text


def test_browser_exposes_research_search_ui() -> None:
    client = TestClient(create_app(lambda _: ApiTestProvider()))
    response = client.get("/")
    assert 'data-view="research-view"' in response.text
    assert 'id="research-form"' in response.text
    assert 'id="research-validation"' in response.text
    assert 'id="research-objective"' in response.text
    assert 'id="research-count"' in response.text
    assert 'id="research-results"' in response.text
    assert "/api/v1/research/search" in response.text
    assert "Holdout excess" in response.text
    assert "Estimated candidate grid" in response.text


def test_browser_exposes_excess_return_objective_and_robustness_view() -> None:
    client = TestClient(create_app(lambda _: ApiTestProvider()))
    response = client.get("/")
    assert 'value="excess_total_return"' in response.text
    assert "Excess return vs buy & hold" in response.text
    assert "Robustness" in response.text
    assert "Robustness is a post-search diagnostic" in response.text
    assert "worst excess" in response.text


def test_browser_exposes_cross_linked_trading_wiki() -> None:
    client = TestClient(create_app(lambda _: ApiTestProvider()))
    response = client.get("/")
    assert 'data-view="learn-view"' in response.text
    assert 'id="learn-view"' in response.text
    assert 'id="wiki-search"' in response.text
    assert 'id="wiki-sma"' in response.text
    assert 'id="wiki-momentum"' in response.text
    assert 'id="wiki-slippage"' in response.text
    assert 'id="wiki-train-holdout"' in response.text
    assert 'id="wiki-robustness"' in response.text
    assert 'data-wiki-target="wiki-volatility"' in response.text
    assert 'data-wiki-target="wiki-drawdown"' in response.text
    assert 'data-wiki-target="wiki-excess"' in response.text
    assert "Search trading concepts" in response.text


def test_browser_wiki_includes_visual_explainers_and_plain_english_app_context() -> None:
    client = TestClient(create_app(lambda _: ApiTestProvider()))
    response = client.get("/")
    assert 'aria-label="Interactive price line and moving average"' in response.text
    assert 'aria-label="Interactive timeline divided into training and holdout periods"' in response.text
    assert 'aria-label="Interactive maximum drawdown illustration"' in response.text
    assert "In the app" in response.text
    assert "Trading intuition" in response.text
    assert "1 basis point (bp) = 0.01%" in response.text


def test_browser_script_has_no_escaped_template_delimiters() -> None:
    client = TestClient(create_app(lambda _: ApiTestProvider()))
    response = client.get("/")
    script = response.text.split("<script>", 1)[1].split("</script>", 1)[0]
    assert r"\`" not in script
    assert "function filterWiki()" in script


def test_top_navigation_order_and_about_default_view() -> None:
    client = TestClient(create_app(lambda _: ApiTestProvider()))
    response = client.get("/")
    html = response.text
    about = html.index('data-view="about-view"')
    learn = html.index('data-view="learn-view"')
    backtest = html.index('data-view="backtest-view"')
    research = html.index('data-view="research-view"')
    assert about < learn < backtest < research
    assert 'class="tab active" data-view="about-view"' in html
    assert '<section id="about-view" class="view">' in html
    assert '<section id="backtest-view" class="view" hidden>' in html


def test_learn_visuals_include_interactive_controls() -> None:
    client = TestClient(create_app(lambda _: ApiTestProvider()))
    response = client.get("/")
    html = response.text
    assert 'id="learn-sma-window"' in html
    assert 'id="learn-slippage-bps"' in html
    assert 'id="learn-drawdown"' in html
    assert 'id="learn-holdout-split"' in html
    assert "function updateSmaDemo()" in html
    assert "function updateSlippageDemo()" in html
    assert "function updateDrawdownDemo()" in html
    assert "function updateHoldoutDemo()" in html


def test_about_is_product_focused_not_duplicate_glossary() -> None:
    client = TestClient(create_app(lambda _: ApiTestProvider()))
    response = client.get("/")
    html = response.text
    about = html.split('<section id="about-view"', 1)[1].split('</section>\n</main>', 1)[0]
    assert "What this app is for" in about
    assert "Core design choices" in about
    assert "Data and current limitations" in about
    assert "Definitions live in Learn" in about
    assert "How to read the results" not in about


def test_learn_includes_putting_it_all_together_capstone() -> None:
    client = TestClient(create_app(lambda _: ApiTestProvider()))
    response = client.get("/")
    html = response.text
    assert 'id="wiki-putting-it-together"' in html
    assert 'data-wiki-target="wiki-putting-it-together"' in html
    assert "Putting it all together: a simple backtest" in html
    assert "Choose a simple first version" in html
    assert "Run the backtest and read the result in layers" in html
    assert "A worked interpretation" in html
    assert "Decide what to test next" in html
    assert 'data-wiki-target="wiki-buy-hold"' in html
    assert 'data-wiki-target="wiki-drawdown"' in html
    assert 'data-wiki-target="wiki-train-holdout"' in html
