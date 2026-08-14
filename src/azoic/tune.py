"""Optuna hyperparameter search for ``ExperimentConfig`` models (v0.2 part 1).

Optuna lives in the ``tune`` extra (``uv sync --extra tune``); ``tune_experiment``
imports it lazily and raises with a clear pointer when the extra is missing.

For each named model, ``tune_experiment`` runs an optuna study whose per-trial
objective is the actuarial-aware numeric penalty decided in PRD section 9 (in
lieu of the cut TariffOptimizer constraint DSL):

    deviance_test + calibration_penalty * |1 - op_ratio_test|

per trial → fit/predict/score on a fixed inner split of the outer training
partition. The outer test partition remains untouched until the selected models
are refit on all outer training rows and evaluated once for the returned
canonical ``Run``.

The default search space touches only regularization / tree-structure
hyperparams. The YAML's identity-defining params (``family`` / ``link`` /
``objective`` / ``tweedie_power`` / ``tweedie_variance_power`` /
``exposure_col``) stay put, so PRD rules 1 and 4 are never violated by a
search suggestion.

ponytail: ceiling -- one default search space per ``kind`` (glm/gbm). Add a
config-driven ``search_space`` when a real portfolio needs model-specific
ranges or extra params (``subsample`` / ``colsample_bytree`` / monotone
constraints).
"""

from __future__ import annotations

from typing import Any, Literal, overload

from pydantic import BaseModel, ConfigDict

from azoic.data import load_data
from azoic.workflow import (
    ExperimentConfig,
    ModelSpec,
    Run,
    _evaluate_split,
    _split_indices,
    _validate_portfolio,
)

__all__ = ["tune_experiment", "TuneResult"]


def _suggest(trial, kind: str, base: dict[str, Any]) -> dict[str, Any]:
    """Default actuarial-safe search space per ``kind``.

    Identity params (``family`` / ``link`` / ``objective`` / ``exposure_col`` /
    ``tweedie_power`` / ``tweedie_variance_power`` / ``random_state``) are
    inherited from the YAML and never sampled -- PRD rules 1 and 4 stay
    inviolable under search.
    """
    out = dict(base)
    if kind == "glm":
        out["alpha"] = trial.suggest_float("alpha", 1e-6, 1.0, log=True)
        out["l1_ratio"] = trial.suggest_float("l1_ratio", 0.0, 1.0)
        return out
    out["num_leaves"] = trial.suggest_int("num_leaves", 4, 64)
    out["learning_rate"] = trial.suggest_float("learning_rate", 1e-3, 0.3, log=True)
    out["n_estimators"] = trial.suggest_int("n_estimators", 20, 300)
    out["min_child_samples"] = trial.suggest_int("min_child_samples", 1, 100)
    out["reg_alpha"] = trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True)
    out["reg_lambda"] = trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True)
    return out


def _objective_value(metrics: dict[str, float], calibration_penalty: float) -> float:
    """`deviance_test + penalty * |1 - op_ratio_test|`; +inf when op is NaN
    (pred_total == 0 -- a worthless trial, not a numerical crash)."""
    dev = float(metrics.get("deviance_test", float("inf")))
    op = float(metrics.get("op_ratio_test", float("nan")))
    if op != op:  # NaN -- op_ratio_test when pred_total <= 0.
        return float("inf")
    return dev + calibration_penalty * abs(1.0 - op)


def _make_objective(
    config: ExperimentConfig,
    name: str,
    spec: ModelSpec,
    calibration_penalty: float,
    df,
    train_idx,
    test_idx,
):
    def objective(trial):
        tuned_params = _suggest(trial, spec.kind, dict(spec.params))
        tuned_spec = spec.model_copy(update={"params": tuned_params})
        tuned_config = config.model_copy(update={"models": {name: tuned_spec}})
        run = _evaluate_split(tuned_config, df, train_idx, test_idx)
        return _objective_value(run.models[name].metrics, calibration_penalty)

    return objective


class TuneResult(BaseModel):
    """Full result of one ``tune_experiment`` invocation.

    ``best_params`` carries only the sampled (tuned) hyperparams per model; the
    identity params from the YAML live on ``Run.models[name].params``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    best_params: dict[str, dict[str, Any]]
    best_values: dict[str, float]
    n_trials: int
    run: Run


@overload
def tune_experiment(
    config: ExperimentConfig,
    *,
    n_trials: int = 20,
    calibration_penalty: float = 1.0,
    random_state: int = 42,
    return_estimators: Literal[False] = False,
) -> TuneResult: ...


@overload
def tune_experiment(
    config: ExperimentConfig,
    *,
    n_trials: int = 20,
    calibration_penalty: float = 1.0,
    random_state: int = 42,
    return_estimators: Literal[True],
) -> tuple[TuneResult, dict[str, Any]]: ...


def tune_experiment(
    config: ExperimentConfig,
    *,
    n_trials: int = 20,
    calibration_penalty: float = 1.0,
    random_state: int = 42,
    return_estimators: bool = False,
) -> TuneResult | tuple[TuneResult, dict[str, Any]]:
    """Run an optuna study per named model; return a ``TuneResult`` whose
    ``run`` refits every selected model on outer training data and scores outer test.

    ``calibration_penalty`` scales ``|1 - op_ratio_test|`` to be commensurate
    with ``deviance_test`` -- tune it to your portfolio's deviance magnitude
    (a unitless ratio penalty is invisible against a six-figure Tweedie
    deviance; raise the penalty until calibration loss shows up in the trial
    ordering).

    ``return_estimators=True`` also returns ``{name: fitted_estimator}`` from
    the final ``run_experiment`` (mirror of the same kwarg on
    ``run_experiment``; needed by ``export_tariff`` after a tuned run).
    """
    if n_trials < 1:
        raise ValueError(f"n_trials must be >= 1; got {n_trials}")
    unsupported = [
        name for name, spec in config.models.items() if spec.kind == "frequency_severity"
    ]
    if unsupported:
        raise ValueError(f"tuning frequency_severity models is not supported: {unsupported}")
    try:
        import optuna
    except ImportError as e:
        raise ImportError(
            "azoic.tune.tune_experiment requires the `tune` extra "
            "(`uv sync --extra tune`); optuna could not be imported."
        ) from e
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    df = load_data(config.data_path, spec=config.spec)
    if len(df) == 0:
        raise ValueError("loaded dataset is empty")
    _validate_portfolio(config, df)
    outer_train_idx, outer_test_idx = _split_indices(config, df)
    inner_train_rel, inner_test_rel = _split_indices(config, df.iloc[outer_train_idx])
    inner_train_idx = outer_train_idx[inner_train_rel]
    inner_test_idx = outer_train_idx[inner_test_rel]

    best_params: dict[str, dict[str, Any]] = {}
    best_values: dict[str, float] = {}
    for i, (name, spec) in enumerate(config.models.items()):
        study = optuna.create_study(
            direction="minimize", sampler=optuna.samplers.TPESampler(seed=random_state + i)
        )
        study.optimize(
            _make_objective(
                config,
                name,
                spec,
                calibration_penalty,
                df,
                inner_train_idx,
                inner_test_idx,
            ),
            n_trials=n_trials,
        )
        best_trial = study.best_trial
        if best_trial.value is None:
            raise RuntimeError("optuna study completed without a best trial value")
        best_params[name] = dict(best_trial.params)
        best_values[name] = float(best_trial.value)

    # Re-run with the merged best + identity params -- the canonical fresh Run
    # feeds model_card / export_tariff / log_run unchanged.
    final_models = {
        name: spec.model_copy(update={"params": {**spec.params, **best_params.get(name, {})}})
        for name, spec in config.models.items()
    }
    final_config = config.model_copy(update={"models": final_models})

    if return_estimators:
        run, estimators = _evaluate_split(
            final_config,
            df,
            outer_train_idx,
            outer_test_idx,
            return_estimators=True,
        )
        return (
            TuneResult(
                best_params=best_params,
                best_values=best_values,
                n_trials=int(n_trials),
                run=run,
            ),
            estimators,
        )
    run = _evaluate_split(final_config, df, outer_train_idx, outer_test_idx)
    return TuneResult(
        best_params=best_params,
        best_values=best_values,
        n_trials=int(n_trials),
        run=run,
    )
