import pytest
from pydantic import ValidationError

from backtest_app.domain.strategy import (
    CrossoverCondition,
    IndicatorRef,
    SmaIndicator,
    StrategySpec,
)


def valid_spec() -> StrategySpec:
    fast = IndicatorRef(id="fast")
    slow = IndicatorRef(id="slow")
    return StrategySpec(
        name="SPY 20/50 SMA crossover",
        symbols=("SPY",),
        indicators=(
            SmaIndicator(id="fast", window=20),
            SmaIndicator(id="slow", window=50),
        ),
        entry_conditions=(
            CrossoverCondition(left=fast, operator="crosses_above", right=slow),
        ),
        exit_conditions=(
            CrossoverCondition(left=fast, operator="crosses_below", right=slow),
        ),
    )


def test_strategy_spec_is_machine_serializable_and_versioned() -> None:
    payload = valid_spec().model_dump(mode="json")

    assert payload["schema_version"] == "1.0"
    assert payload["indicators"][0] == {
        "type": "sma",
        "id": "fast",
        "source": "close",
        "window": 20,
    }
    assert payload["execution"] == {
        "signal_price": "close",
        "execution_bar": "next_bar",
        "execution_price": "open",
    }


def test_strategy_rejects_duplicate_indicator_ids() -> None:
    ref = IndicatorRef(id="same")
    with pytest.raises(ValidationError, match="indicator ids must be unique"):
        StrategySpec(
            name="invalid",
            symbols=("SPY",),
            indicators=(
                SmaIndicator(id="same", window=20),
                SmaIndicator(id="same", window=50),
            ),
            entry_conditions=(
                CrossoverCondition(left=ref, operator="crosses_above", right=ref),
            ),
            exit_conditions=(
                CrossoverCondition(left=ref, operator="crosses_below", right=ref),
            ),
        )


def test_strategy_rejects_unknown_indicator_reference() -> None:
    with pytest.raises(ValidationError, match="unknown indicator: missing"):
        StrategySpec(
            name="invalid",
            symbols=("SPY",),
            indicators=(SmaIndicator(id="fast", window=20),),
            entry_conditions=(
                CrossoverCondition(
                    left=IndicatorRef(id="fast"),
                    operator="crosses_above",
                    right=IndicatorRef(id="missing"),
                ),
            ),
            exit_conditions=(
                CrossoverCondition(
                    left=IndicatorRef(id="fast"),
                    operator="crosses_below",
                    right=IndicatorRef(id="fast"),
                ),
            ),
        )


def test_example_strategy_json_round_trips_through_validated_ir() -> None:
    import json
    from pathlib import Path

    example_path = Path(__file__).parents[1] / "examples" / "spy_sma_20_50.strategy.json"
    payload = json.loads(example_path.read_text())

    spec = StrategySpec.model_validate(payload)

    assert spec.symbols == ("SPY",)
    assert [indicator.window for indicator in spec.indicators] == [20, 50]
    assert StrategySpec.model_validate(spec.model_dump(mode="json")) == spec
