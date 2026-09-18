from datetime import date

import pytest
from pydantic import ValidationError

from backtest_app.domain.experiment import BacktestConfig, CostModel, ExperimentSpec
from test_strategy_spec import valid_spec


def test_experiment_captures_run_level_assumptions() -> None:
    experiment = ExperimentSpec(
        strategy=valid_spec(),
        backtest=BacktestConfig(
            start_date=date(2020, 1, 1),
            end_date=date(2024, 12, 31),
            starting_capital=100_000,
            costs=CostModel(commission_amount=1.0, slippage_bps=2.5),
        ),
        requested_data_provider="free-provider",
    )

    assert experiment.backtest.costs.slippage_bps == 2.5
    assert experiment.strategy.execution.execution_bar == "next_bar"


def test_backtest_config_rejects_reversed_dates() -> None:
    with pytest.raises(ValidationError, match="end_date"):
        BacktestConfig(
            start_date=date(2024, 2, 1),
            end_date=date(2024, 1, 1),
            starting_capital=10_000,
        )


def test_cost_model_rejects_slippage_of_100_percent_or_more() -> None:
    with pytest.raises(ValidationError, match="slippage_bps"):
        CostModel(slippage_bps=10_000)
