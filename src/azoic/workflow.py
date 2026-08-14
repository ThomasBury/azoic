"""Run an actuarial modelling experiment from a YAML config.

``ExperimentConfig`` (pydantic) captures data + spec + split + models. ``run_experiment``
loads the data, splits it (random or temporal), fits every named model, and
returns a ``Run`` carrying per-model diagnostics (Gini / O-P ratio / Tweedie
deviance / calibration table + the fitted estimator).

Pure-premium convention (PRD sec. 5 rule 1): estimator is fit on
``y = claim_amount / exposure`` with ``sample_weight = exposure`` (the exposure
column is popped inside ``RiskGLM`` / ``RiskGBM``); diagnostics use aggregate
``claim_amount`` as ``y_true`` and the predicted pure premium (rate) as
``y_pred`` with ``sample_weight = exposure``.

"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer

from azoic.data import DatasetSpec, load_data
from azoic.metrics import (
    calibration_table,
    gini,
    mean_tweedie_deviance,
    op_ratio,
)
from azoic.models import FrequencySeverityModel, RiskGBM, RiskGLM
from azoic.preprocessing import AutoBinner, AutoGrouper
from azoic.validation import temporal_split

__all__ = [
    "PreprocessingSpec",
    "ModelSpec",
    "ExperimentConfig",
    "ModelResult",
    "Run",
    "run_experiment",
]


class PreprocessingSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    binner: dict[str, Any] | None = None
    grouper: dict[str, Any] | None = None

    def build_steps(self, spec: DatasetSpec) -> list[tuple[str, Any]]:
        special = {
            "exposure_col": spec.exposure,
            "claim_count_col": spec.claim_count,
            "target_col": spec.target,
        }
        fit_columns = [spec.target]
        if spec.claim_count is not None:
            fit_columns.append(spec.claim_count)
        steps = [
            ("fit_columns", FunctionTransformer(_ensure_columns, kw_args={"columns": fit_columns}))
        ]
        if self.binner is not None:
            steps.append(("binner", AutoBinner(**{**self.binner, **special})))
        if self.grouper is not None:
            steps.append(("grouper", AutoGrouper(**{**self.grouper, **special})))
        return steps


class ModelSpec(BaseModel):
    """One estimator spec inside an ExperimentConfig.

    ``kind`` selects the wrapper class; ``params`` are forwarded verbatim to its
    constructor (``family``/``link``/``exposure_col`` for GLM,
    ``objective``/``tweedie_variance_power``/``n_estimators`` for GBM, ...).
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["glm", "gbm", "frequency_severity"] = "glm"
    params: dict[str, Any] = Field(default_factory=dict)
    frequency: ModelSpec | None = None
    severity: ModelSpec | None = None

    @model_validator(mode="after")
    def _validate_nested_specs(self):
        nested = self.frequency is not None or self.severity is not None
        if self.kind == "frequency_severity":
            if self.frequency is None or self.severity is None:
                raise ValueError("frequency_severity requires frequency and severity specs")
            if (
                self.frequency.kind == "frequency_severity"
                or self.severity.kind == "frequency_severity"
            ):
                raise ValueError("nested frequency_severity models are not supported")
        elif nested:
            raise ValueError("frequency and severity specs require kind=frequency_severity")
        return self

    def build(self, dataset_spec: DatasetSpec | None = None):
        """Construct the (unfitted) estimator from this spec."""
        if self.kind == "frequency_severity":
            if (
                dataset_spec is None
                or dataset_spec.claim_count is None
                or self.frequency is None
                or self.severity is None
            ):
                raise ValueError("frequency_severity requires spec.claim_count")
            return FrequencySeverityModel(
                freq=self.frequency.build(),
                sev=self.severity.build(),
                exposure_col=dataset_spec.exposure,
                claim_count_col=dataset_spec.claim_count,
                claim_amount_col=dataset_spec.target,
            )
        params = dict(self.params)
        if dataset_spec is not None:
            params["exposure_col"] = dataset_spec.exposure
        if self.kind == "glm":
            return RiskGLM(**params)
        return RiskGBM(**params)


class ExperimentConfig(BaseModel):
    """End-to-end modelling experiment: data + spec + split + named models.

    Load with ``ExperimentConfig.from_yaml(path)``. The data path is stored as
    a string so the config round-trips YAML cleanly; ``run_experiment`` resolves
    it through ``azoic.data.load_data`` (local + s3 paths via fsspec).
    """

    model_config = ConfigDict(extra="forbid")

    name: str = "experiment"
    data_path: str
    spec: DatasetSpec
    features: list[str] | None = None
    preprocessing: PreprocessingSpec | None = None
    split: Literal["random", "temporal"] = "random"
    test_size: float = 0.2
    random_state: int = 42
    models: dict[str, ModelSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_features(self):
        if self.features is None:
            return self
        duplicates = sorted({name for name in self.features if self.features.count(name) > 1})
        if duplicates:
            raise ValueError(f"features must be unique; duplicates: {duplicates}")
        special_features = sorted(set(self.features) & set(self.spec.required_columns()))
        if special_features:
            raise ValueError(f"features contains special columns: {special_features}")
        return self

    @classmethod
    def from_yaml(cls, path: str | Path) -> ExperimentConfig:
        with open(path, "rb") as fh:
            return cls.model_validate(yaml.safe_load(fh))

    def feature_columns(self, df: pd.DataFrame) -> list[str]:
        """Resolve the feature-column list: explicit ``features`` if given,
        else every column that is not a special (spec-required) column."""
        if self.features is not None:
            missing = [c for c in self.features if c not in df.columns]
            if missing:
                raise ValueError(f"features not in data: {missing}")
            return list(self.features)
        specials = set(self.spec.required_columns())
        return [c for c in df.columns if c not in specials]


class ModelResult(BaseModel):
    """Diagnostics for one fitted model inside a Run.

    Frozen + slots for cheap, hashable values; the fitted estimator stays on
    the parent ``Run`` (sklearn estimators are mutable, not pydantic-friendly).
    """

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    kind: str
    params: dict[str, Any]
    metrics: dict[str, float]
    calibration_table: pd.DataFrame


class Run(BaseModel):
    """The full result of a single ``run_experiment`` invocation."""

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    config: ExperimentConfig
    data_fingerprint: str
    n_rows: int
    n_train: int
    n_test: int
    feature_names: list[str]
    models: dict[str, ModelResult]


def _split_indices(config: ExperimentConfig, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """(train_idx, test_idx) positional indices into ``df``."""
    if config.split == "temporal":
        time_col = config.spec.time_col
        if time_col is None:
            raise ValueError("`split: temporal` requires `spec.time_col`")
        return temporal_split(df, time_col, test_size=config.test_size)
    rng = np.random.default_rng(config.random_state)
    perm = rng.permutation(len(df))
    n_test = int(round(len(df) * config.test_size))
    if not 0 < n_test < len(df):
        raise ValueError(f"`test_size` resolves to {n_test}; must be 1..{len(df) - 1}")
    return perm[n_test:], perm[:n_test]


def _data_fingerprint(df: pd.DataFrame) -> str:
    digest = hashlib.sha256()
    digest.update(str(df.shape).encode())
    digest.update(pd.util.hash_pandas_object(df.columns, index=False).to_numpy().tobytes())
    digest.update("\0".join(map(str, df.dtypes)).encode())
    digest.update(pd.util.hash_pandas_object(df, index=True).to_numpy().tobytes())
    return digest.hexdigest()


def _deviance_test(
    *,
    obs_rate: np.ndarray,
    pred_rate: np.ndarray,
    exposure: np.ndarray,
) -> float:
    """Exposure-weighted mean Tweedie deviance with fixed pure-premium power 1.5."""
    return float(
        mean_tweedie_deviance(
            obs_rate,
            pred_rate,
            sample_weight=exposure,
            power=1.5,
        )
    )


def _validate_portfolio(config: ExperimentConfig, df: pd.DataFrame) -> None:
    exposure = df[config.spec.exposure].to_numpy(dtype=float)
    target = df[config.spec.target].to_numpy(dtype=float)
    if not np.isfinite(exposure).all() or np.any(exposure <= 0):
        raise ValueError("exposure must contain only positive finite values")
    if not np.isfinite(target).all() or np.any(target < 0):
        raise ValueError("target must contain only non-negative finite values")
    if config.spec.claim_count is None:
        return
    claim_count = df[config.spec.claim_count].to_numpy(dtype=float)
    if not np.isfinite(claim_count).all() or np.any(claim_count < 0):
        raise ValueError("claim_count must contain only non-negative finite values")
    if np.any((claim_count == 0) != (target == 0)):
        raise ValueError("claim_count and target rows must be zero or positive together")


def _ensure_columns(X: pd.DataFrame, *, columns: list[str]) -> pd.DataFrame:
    missing = {column: 0.0 for column in columns if column not in X.columns}
    return X.assign(**missing)


def _drop_columns(X: pd.DataFrame, *, columns: list[str]) -> pd.DataFrame:
    return X.drop(columns=columns, errors="ignore")


def _evaluate_split(
    config: ExperimentConfig,
    df: pd.DataFrame,
    train_idx: np.ndarray,
    test_idx: np.ndarray,
    *,
    return_estimators: bool = False,
):
    """Fit and score one explicit train/test partition."""
    feature_names = config.feature_columns(df)
    if not feature_names:
        raise ValueError("no feature columns resolved; check `features` / `spec`")
    train_df, test_df = df.iloc[train_idx], df.iloc[test_idx]

    target = config.spec.target
    exposure_col = config.spec.exposure
    if target not in df.columns:
        raise ValueError(f"spec.target {target!r} not in data columns")

    y_train = (train_df[target] / train_df[exposure_col]).to_numpy(dtype=float)
    obs_train_agg = train_df[target].to_numpy(dtype=float)
    obs_test_agg = test_df[target].to_numpy(dtype=float)
    exp_train = train_df[exposure_col].to_numpy(dtype=float)
    exp_test = test_df[exposure_col].to_numpy(dtype=float)

    results: dict[str, ModelResult] = {}
    estimators: dict[str, Any] = {}
    for name, spec in config.models.items():
        columns = [*feature_names, exposure_col]
        if config.preprocessing is not None or spec.kind == "frequency_severity":
            columns.append(target)
            if config.spec.claim_count is not None:
                columns.append(config.spec.claim_count)
        columns = list(dict.fromkeys(columns))
        X_train = train_df[columns]
        X_test = test_df[columns]

        estimator = spec.build(config.spec)
        if config.preprocessing is not None:
            steps = config.preprocessing.build_steps(config.spec)
            if spec.kind != "frequency_severity":
                specials = [target]
                if config.spec.claim_count is not None:
                    specials.append(config.spec.claim_count)
                steps.append(
                    (
                        "drop_specials",
                        FunctionTransformer(_drop_columns, kw_args={"columns": specials}),
                    )
                )
            estimator = Pipeline([*steps, ("model", estimator)])
        estimator.fit(X_train, y_train)
        pred_train = np.asarray(estimator.predict(X_train), dtype=float)
        pred_test = np.asarray(estimator.predict(X_test), dtype=float)

        metrics = {
            "gini_train": float(gini(obs_train_agg, pred_train, sample_weight=exp_train)),
            "gini_test": float(gini(obs_test_agg, pred_test, sample_weight=exp_test)),
            "op_ratio_test": float(op_ratio(obs_test_agg, pred_test, sample_weight=exp_test)),
            "deviance_test": _deviance_test(
                obs_rate=obs_test_agg / exp_test,
                pred_rate=pred_test,
                exposure=exp_test,
            ),
        }
        cal = calibration_table(obs_test_agg, pred_test, exp_test, n_bins=10)
        params = dict(spec.params)
        if spec.kind == "frequency_severity":
            if spec.frequency is None or spec.severity is None:
                raise ValueError("frequency_severity requires frequency and severity specs")
            params["frequency"] = spec.frequency.model_dump(exclude_none=True)
            params["severity"] = spec.severity.model_dump(exclude_none=True)
        results[name] = ModelResult(
            kind=spec.kind,
            params=params,
            metrics=metrics,
            calibration_table=cal,
        )
        estimators[name] = estimator

    run = Run(
        config=config,
        data_fingerprint=_data_fingerprint(df),
        n_rows=int(len(df)),
        n_train=int(len(train_df)),
        n_test=int(len(test_df)),
        feature_names=list(feature_names),
        models=results,
    )
    if return_estimators:
        return run, estimators
    return run


def run_experiment(config: ExperimentConfig, *, return_estimators: bool = False):
    """Load, validate, split, fit, and score an experiment."""
    df = load_data(config.data_path, spec=config.spec)
    if len(df) == 0:
        raise ValueError("loaded dataset is empty")
    _validate_portfolio(config, df)
    train_idx, test_idx = _split_indices(config, df)
    return _evaluate_split(
        config,
        df,
        train_idx,
        test_idx,
        return_estimators=return_estimators,
    )
