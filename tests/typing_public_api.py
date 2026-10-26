"""Downstream typing consumer, checked by test_init; never executed."""

from pathlib import Path
from typing import Any, assert_type

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from azoic import (
    AutoBinner,
    AutoGrouper,
    ExperimentConfig,
    FrequencySeverityModel,
    ModelResult,
    ModelSpec,
    RevisedTariff,
    RiskGBM,
    RiskGLM,
    Run,
    TuneResult,
    calibration_table,
    check_experiment,
    comparison_table,
    gini,
    load_run,
    log_run,
    model_card,
    revise_run,
    revise_tariff,
    run_experiment,
    save_run,
    split_portfolio,
    tariff_review,
    tune_experiment,
)


class CustomGLM(RiskGLM):
    pass


def consumer(config: ExperimentConfig, frame: pd.DataFrame, flag: bool):
    assert_type(check_experiment(config, df=frame), dict[str, Any])
    assert_type(split_portfolio(frame, [1, 2], id_col="id"), tuple[pd.DataFrame, pd.DataFrame])
    assert_type(RiskGLM().fit(frame, frame["rate"]), RiskGLM)
    assert_type(CustomGLM().fit(frame, frame["rate"]), CustomGLM)
    assert_type(RiskGBM().fit(frame, frame["rate"]), RiskGBM)
    assert_type(FrequencySeverityModel().fit(frame), FrequencySeverityModel)
    assert_type(AutoBinner().fit(frame, frame["rate"]), AutoBinner)
    assert_type(AutoGrouper().fit(frame, frame["rate"]), AutoGrouper)
    AutoBinner().set_mapping({"x": [1.0, 2.0]}, missing={"x": 0})
    AutoGrouper().set_mapping({"x": {"a": "A", "b": "B"}}, missing={"x": "A"})
    assert_type(AutoBinner().transform(frame), pd.DataFrame)
    assert_type(AutoGrouper().transform(frame), pd.DataFrame)
    assert_type(AutoBinner().transform(np.zeros((3, 1))), np.ndarray)
    assert_type(run_experiment(config, df=frame), Run)
    assert_type(run_experiment(config, return_estimators=False), Run)
    run, estimators = run_experiment(config, return_estimators=True)
    assert_type(run, Run)
    assert_type(estimators, dict[str, RiskGLM | RiskGBM | FrequencySeverityModel | Pipeline])
    assert_type(save_run(run, estimators, "candidates.pkl"), None)
    assert_type(revise_tariff(RiskGLM(), [], recalibrate=False), RevisedTariff)
    revised_run, revised_models = revise_run(
        run, estimators, model="glm", replacements=[], df=frame
    )
    assert_type(revised_run, Run)
    assert_type(
        revised_models,
        dict[str, RiskGLM | RiskGBM | FrequencySeverityModel | Pipeline | RevisedTariff],
    )
    assert_type(
        load_run("candidates.pkl"),
        tuple[
            Run, dict[str, RiskGLM | RiskGBM | FrequencySeverityModel | Pipeline | RevisedTariff]
        ],
    )
    assert_type(
        run_experiment(config, return_estimators=flag),
        Run | tuple[Run, dict[str, RiskGLM | RiskGBM | FrequencySeverityModel | Pipeline]],
    )
    assert_type(run.config, ExperimentConfig)
    assert_type(run.models["glm"], ModelResult)
    assert_type(run.models["glm"].resolved_params, dict[str, Any])
    assert_type(run.runtime_versions, dict[str, str])
    assert_type(run.tuning_settings, dict[str, Any])
    assert_type(ModelSpec(kind="glm").build(), RiskGLM | RiskGBM | FrequencySeverityModel)
    tuned = tune_experiment(config)
    assert_type(tuned, TuneResult)
    assert_type(
        tuned.estimators, dict[str, RiskGLM | RiskGBM | FrequencySeverityModel | Pipeline] | None
    )
    assert_type(gini(frame["amount"], frame["rate"]), float)
    assert_type(calibration_table(frame["amount"], frame["rate"]), pd.DataFrame)
    assert_type(
        tariff_review(
            {"fit": (run, estimators)},
            df=frame,
            incumbent=frame,
            incumbent_rate="old_rate",
            out="review",
            selected="fit/glm",
            rationale="Review evidence",
        ),
        Path,
    )
    assert_type(model_card(run), str)
    assert_type(comparison_table([run]), pd.DataFrame)
    assert_type(log_run(run), str)
