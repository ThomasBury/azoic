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

Deliberate ceilings (ponytail):
  * ModelSpec supports ``glm`` and ``gbm`` only. ``FrequencySeverityModel``
    needs nested freq/sev sub-specs -- add when a config wants it.
  * No preprocessing in the config -- raw features feed the estimator directly.
    ``AutoBinner`` / ``AutoGrouper`` step wiring is M6 territory (tariff
    pipeline).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict, Field

from riskforge.data import DatasetSpec, load_data
from riskforge.metrics import (
    calibration_table,
    gini,
    mean_poisson_deviance,
    mean_tweedie_deviance,
    op_ratio,
)
from riskforge.models import RiskGBM, RiskGLM
from riskforge.validation import temporal_split

__all__ = [
    "ModelSpec",
    "ExperimentConfig",
    "ModelResult",
    "Run",
    "run_experiment",
]


class ModelSpec(BaseModel):
    """One estimator spec inside an ExperimentConfig.

    ``kind`` selects the wrapper class; ``params`` are forwarded verbatim to its
    constructor (``family``/``link``/``exposure_col`` for GLM,
    ``objective``/``tweedie_variance_power``/``n_estimators`` for GBM, ...).
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["glm", "gbm"] = "glm"
    params: dict[str, Any] = Field(default_factory=dict)

    def build(self):
        """Construct the (unfitted) estimator from this spec."""
        if self.kind == "glm":
            return RiskGLM(**self.params)
        return RiskGBM(**self.params)


class ExperimentConfig(BaseModel):
    """End-to-end modelling experiment: data + spec + split + named models.

    Load with ``ExperimentConfig.from_yaml(path)``. The data path is stored as
    a string so the config round-trips YAML cleanly; ``run_experiment`` resolves
    it through ``riskforge.data.load_data`` (local + s3 paths via fsspec).
    """

    model_config = ConfigDict(extra="forbid")

    name: str = "experiment"
    data_path: str
    spec: DatasetSpec
    features: list[str] | None = None
    split: Literal["random", "temporal"] = "random"
    test_size: float = 0.2
    random_state: int = 42
    models: dict[str, ModelSpec]

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

    name: str
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

    def __getitem__(self, name: str) -> ModelResult:
        return self.models[name]


def _split_indices(
    config: ExperimentConfig, df: pd.DataFrame
) -> tuple[np.ndarray, np.ndarray]:
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
    family_hint: str,
    obs_rate: np.ndarray,
    pred_rate: np.ndarray,
    exposure: np.ndarray,
) -> float:
    """Tweedie (p=1.5) deviance for GLM/GBM Tweedie fits, Poisson for Poisson
    frequency fits -- otherwise default to Tweedie p=1.5 (pure premium)."""
    if "poisson" in family_hint and "tweedie" not in family_hint:
        return float(mean_poisson_deviance(obs_rate, pred_rate, sample_weight=exposure))
    return float(mean_tweedie_deviance(obs_rate, pred_rate, sample_weight=exposure))


def run_experiment(config: ExperimentConfig, *, return_estimators: bool = False):
    """Execute an ``ExperimentConfig`` end-to-end. Returns a ``Run``.

    Pipeline: ``load_data`` -> split (random or temporal) -> for each named
    model spec, build + fit on the train rows -> predict on both sets ->
    metrics + calibration table on the test set. ``return_estimators=True``
    also returns ``{name: fitted_estimator}`` alongside the ``Run`` so callers
    (CLI export, M6 tariff) can reach the fitted estimator.
    """
    df = load_data(config.data_path, spec=config.spec)
    if len(df) == 0:
        raise ValueError("loaded dataset is empty")

    feature_names = config.feature_columns(df)
    if not feature_names:
        raise ValueError("no feature columns resolved; check `features` / `spec`")

    train_idx, test_idx = _split_indices(config, df)
    train_df, test_df = df.iloc[train_idx], df.iloc[test_idx]

    target = config.spec.target
    exposure_col = config.spec.exposure
    if target not in df.columns:
        raise ValueError(f"spec.target {target!r} not in data columns")

    X_train = train_df[feature_names + [exposure_col]]
    X_test = test_df[feature_names + [exposure_col]]
    y_train = (train_df[target] / train_df[exposure_col]).to_numpy(dtype=float)
    obs_train_agg = train_df[target].to_numpy(dtype=float)
    obs_test_agg = test_df[target].to_numpy(dtype=float)
    exp_train = train_df[exposure_col].to_numpy(dtype=float)
    exp_test = test_df[exposure_col].to_numpy(dtype=float)

    results: dict[str, ModelResult] = {}
    estimators: dict[str, Any] = {}
    for name, spec in config.models.items():
        estimator = spec.build()
        estimator.fit(X_train, y_train)
        pred_train = np.asarray(estimator.predict(X_train), dtype=float)
        pred_test = np.asarray(estimator.predict(X_test), dtype=float)

        metrics = {
            "gini_train": float(gini(obs_train_agg, pred_train, sample_weight=exp_train)),
            "gini_test": float(gini(obs_test_agg, pred_test, sample_weight=exp_test)),
            "op_ratio_test": float(op_ratio(obs_test_agg, pred_test, sample_weight=exp_test)),
            "deviance_test": _deviance_test(
                family_hint=str(spec.params.get("family") or spec.params.get("objective", "")),
                obs_rate=obs_test_agg / exp_test,
                pred_rate=pred_test,
                exposure=exp_test,
            ),
        }
        cal = calibration_table(obs_test_agg, pred_test, exp_test, n_bins=10)
        results[name] = ModelResult(
            name=name,
            kind=spec.kind,
            params=dict(spec.params),
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
