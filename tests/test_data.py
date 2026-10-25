"""Tests for azoic.data: DatasetSpec validation and load_data round-trip."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pydantic
import pytest

from azoic.data import EXPOSURE_FLOOR, DatasetSpec, _validate_outcomes, load_data
from tests.conftest import make_synthetic_portfolio


@pytest.mark.parametrize("slot", [0, 1, 2])
@pytest.mark.parametrize("bad", [1.0, [[1.0], [1.0]], [[[1.0, 1.0]]]])
def test_outcomes_reject_nonvector_inputs(slot, bad) -> None:
    outcomes = [[1.0, 1.0], [1.0, 1.0], [1.0, 1.0]]
    outcomes[slot] = bad
    with pytest.raises(ValueError, match="one-dimensional"):
        _validate_outcomes(*outcomes)


@pytest.mark.parametrize("slot", [0, 1, 2])
def test_outcomes_reject_misaligned_vectors(slot) -> None:
    outcomes = [[1.0, 1.0], [1.0, 1.0], [1.0, 1.0]]
    outcomes[slot] = [1.0]
    with pytest.raises(ValueError, match="inconsistent numbers"):
        _validate_outcomes(*outcomes)


def test_outcomes_accept_optional_counts_and_one_day_tolerance() -> None:
    exposure = [EXPOSURE_FLOOR, 0.0027322404371584, 1.0]
    amounts = [0.0, 30.0, 40.0]
    _validate_outcomes(exposure, amounts)
    _validate_outcomes(exposure, amounts, [0.0, 3.0, 4.0])
    _validate_outcomes(exposure, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0])
    with pytest.raises(ValueError, match="1/366"):
        _validate_outcomes([np.nextafter(EXPOSURE_FLOOR, 0.0)], [0.0])
    with pytest.raises(ValueError, match="non-negative finite"):
        _validate_outcomes([1.0], [-1.0])


@pytest.mark.parametrize(
    ("column", "bad", "rule"),
    [
        ("duration", 0.0, "positive finite"),
        ("duration", 0.001, "1/366"),
        ("duration", np.inf, "positive finite"),
        ("cost", -1.0, "non-negative finite"),
        ("cost", np.nan, "non-negative finite"),
        ("count", -1.0, "non-negative finite"),
        ("count", 0.0, "zero or positive together"),
        ("cost", "not-a-number", "numeric finite"),
        ("count", pd.NA, "numeric finite"),
    ],
)
def test_outcome_errors_identify_column_count_and_bounded_positions(column, bad, rule):
    frame = pd.DataFrame({"duration": [1.0] * 12, "cost": [10.0] * 12, "count": [1.0] * 12})
    frame[column] = frame[column].astype(object)
    frame.loc[1:9, column] = bad
    frame.index = ["private-policy-id"] * len(frame)
    original = frame.copy(deep=True)
    with pytest.raises(ValueError, match=rule) as error:
        _validate_outcomes(frame.duration, frame.cost, frame["count"])
    message = str(error.value)
    assert f"column '{column}'" in message
    assert "9 invalid rows; row positions (0-based, first 5): [1, 2, 3, 4, 5]" in message
    assert "private-policy-id" not in message and "not-a-number" not in message
    assert error.value.__suppress_context__
    pd.testing.assert_frame_equal(frame, original)


@pytest.mark.parametrize("entrypoint", ["workflow", "tune", "frequency-severity"])
def test_outcome_error_context_survives_public_callers(entrypoint, monkeypatch):
    from azoic.models import FrequencySeverityModel, RiskGLM
    from azoic.workflow import ExperimentConfig, ModelSpec, run_experiment

    def unexpected_fit(*args, **kwargs):
        pytest.fail("invalid portfolio reached model fitting")

    monkeypatch.setattr(RiskGLM, "fit", unexpected_fit)
    frame = pd.DataFrame(
        {
            "risk": [1, 2, 3, 4],
            "duration": [1.0] * 4,
            "cost": [10.0, -1.0, 10.0, -1.0],
            "count": [1.0] * 4,
        },
        index=[7, 7, 20, 20],
    )
    config = ExperimentConfig(
        data_path="unused.parquet",
        features=["risk"],
        spec=DatasetSpec(target="cost", exposure="duration", claim_count="count"),
        models={"glm": ModelSpec()},
    )
    with pytest.raises(ValueError, match="column 'cost'.*2 invalid rows.*\\[1, 3\\]"):
        if entrypoint == "workflow":
            run_experiment(config, df=frame)
        elif entrypoint == "tune":
            pytest.importorskip("optuna")
            from azoic.tune import tune_experiment

            tune_experiment(config, df=frame, n_trials=1)
        else:
            FrequencySeverityModel(
                freq=RiskGLM(),
                sev=RiskGLM(),
                exposure_col="duration",
                claim_amount_col="cost",
                claim_count_col="count",
            ).fit(frame)


def test_dataset_spec_requires_target_and_exposure() -> None:
    spec = DatasetSpec(target="claim_amount", exposure="exposure", claim_count="claim_count")
    assert spec.target == "claim_amount"
    assert spec.claim_count == "claim_count"
    assert "claim_amount" in spec.required_columns()
    assert "exposure" in spec.required_columns()
    assert "claim_count" in spec.required_columns()


def test_dataset_spec_rejects_empty_strings() -> None:
    with pytest.raises(pydantic.ValidationError):
        DatasetSpec(target="", exposure="exposure")
    with pytest.raises(pydantic.ValidationError):
        DatasetSpec(target="claim_amount", exposure="   ")


def test_dataset_spec_optional_columns_filter() -> None:
    spec = DatasetSpec(target="claim_amount", exposure="exposure")
    assert spec.protected_cols == []
    assert spec.required_columns() == ["claim_amount", "exposure"]


def test_dataset_spec_rejects_misspelled_optional_column() -> None:
    with pytest.raises(pydantic.ValidationError, match="claim_count_col"):
        DatasetSpec.model_validate(
            {"target": "claim_amount", "exposure": "exposure", "claim_count_col": "claim_count"}
        )


@pytest.mark.parametrize(
    ("protected_cols", "message"),
    [
        (["region", "region"], "unique"),
        ([""], "non-empty"),
        (["   "], "non-empty"),
    ],
)
def test_dataset_spec_rejects_invalid_protected_names(
    protected_cols: list[str], message: str
) -> None:
    with pytest.raises(pydantic.ValidationError, match=message):
        DatasetSpec(
            target="claim_amount",
            exposure="exposure",
            protected_cols=protected_cols,
        )


@pytest.mark.parametrize("column", ["claim_amount", "exposure", "claim_count", "period"])
def test_dataset_spec_rejects_protected_special_column_overlap(column: str) -> None:
    with pytest.raises(pydantic.ValidationError, match="overlaps"):
        DatasetSpec(
            target="claim_amount",
            exposure="exposure",
            claim_count="claim_count",
            time_col="period",
            protected_cols=[column],
        )


def test_load_data_roundtrip(tmp_path) -> None:
    df = make_synthetic_portfolio(n=500, seed=3)
    p = tmp_path / "port.parquet"
    df.to_parquet(p)
    spec = DatasetSpec(target="claim_amount", exposure="exposure", claim_count="claim_count")
    df2 = load_data(p, spec=spec)
    pd.testing.assert_frame_equal(df, df2)


def test_load_data_missing_columns_raises(tmp_path) -> None:
    df = pd.DataFrame(
        {
            "exposure": np.linspace(0.5, 1.0, 10),
            "driver_age": np.repeat(30, 10),
        }
    )
    p = tmp_path / "bad.parquet"
    df.to_parquet(p)
    spec = DatasetSpec(target="claim_amount", exposure="exposure")
    with pytest.raises(ValueError, match="missing required columns"):
        load_data(p, spec=spec)


def test_load_data_requires_declared_protected_columns(tmp_path) -> None:
    path = tmp_path / "missing-protected.parquet"
    pd.DataFrame({"claim_amount": [0.0], "exposure": [1.0]}).to_parquet(path)
    spec = DatasetSpec(
        target="claim_amount",
        exposure="exposure",
        protected_cols=["review_group"],
    )

    with pytest.raises(ValueError, match="review_group"):
        load_data(path, spec=spec)


def test_load_data_without_spec(tmp_path) -> None:
    df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    p = tmp_path / "plain.parquet"
    df.to_parquet(p)
    pd.testing.assert_frame_equal(load_data(p), df)


def test_load_data_keeps_outcome_validation_at_model_boundaries(tmp_path) -> None:
    df = pd.DataFrame({"claim_amount": [-1.0], "exposure": [0.0], "claim_count": [np.nan]})
    path = tmp_path / "unchecked-outcomes.parquet"
    df.to_parquet(path)
    spec = DatasetSpec(target="claim_amount", exposure="exposure", claim_count="claim_count")
    pd.testing.assert_frame_equal(load_data(path, spec), df)


# ---------------------------------------------------------------------------
# Special-column distinctness (M32)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"target": "amount", "exposure": "amount"},
        {"target": "amount", "exposure": "e", "claim_count": "amount"},
        {"target": "t", "exposure": "e", "claim_count": "c", "time_col": "c"},
        {"target": "t", "exposure": "e", "claim_count": "e", "time_col": "t"},
    ],
)
def test_dataset_spec_rejects_aliased_special_columns(overrides) -> None:
    """Aliased specials previously produced a constant response (amount/amount == 1)."""
    with pytest.raises(pydantic.ValidationError, match="must be distinct"):
        DatasetSpec(**overrides)


def test_dataset_spec_accepts_distinct_optional_columns() -> None:
    spec = DatasetSpec(target="t", exposure="e", claim_count="c", time_col="p")
    assert spec.required_columns() == ["t", "e", "c", "p"]


@pytest.mark.parametrize("field", ["target", "exposure", "claim_count", "time_col"])
def test_dataset_spec_rejects_empty_special_names(field) -> None:
    """Empty optional names previously passed validation and failed later
    with a bare KeyError."""
    base = {"target": "t", "exposure": "e"}
    base[field] = ""
    with pytest.raises(pydantic.ValidationError, match="non-empty"):
        DatasetSpec(**base)
