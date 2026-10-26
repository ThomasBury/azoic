"""Multiplicative tariff export for a fitted ``RiskGLM``.

A log-link GLM (Tweedie / Poisson / Gamma) is a multiplicative model:

    predict(X) = exp(intercept + sum_numeric coef * x + sum_cat coef[level])
               = base * prod_numeric exp(coef * x) * prod_cat factor[level]

glum encodes categoricals as full one-hot (``drop_first=False``); the actuary
picks a reference level per categorical feature, folds its coefficient into
the base rate, and applies every other level as a relativity to that
reference. ``extract_tariff`` returns that structure; ``apply_tariff``
applies it back to data; ``export_tariff`` writes a 3-sheet xlsx.

Three sheets per the PRD section 3 ``base / factors / mappings`` contract:
    * ``base_rate``        -- one row with the multiplicative base (intercept
      folded with reference-level factors) plus the GLM family / link and the
      recalibration flag. When ``(X, y, exposure_col)`` and
      ``recalibrate=True`` are given, the base is shifted so the tariff
      reproduces the observed portfolio total claim amount.
    * ``factors``          -- one row per (feature, level). Numeric features
      carry a single ``_per_unit`` row (apply as ``factor ** value``);
      categorical features carry one row per level (apply as the matching
      factor, reference level = ``1.0``).
    * ``mappings``         -- self-documenting feature encoding the GLM saw
      (feature / dtype / role / levels / reference_level).
"""

from __future__ import annotations

from collections.abc import Hashable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from math import fsum
from numbers import Real
from pathlib import Path
from stat import S_IMODE
from tempfile import NamedTemporaryFile
from typing import Any

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer
from sklearn.utils.validation import check_array, check_consistent_length

import azoic
from azoic.data import EXPOSURE_FLOOR
from azoic.metrics import mean_tweedie_deviance
from azoic.models import RiskGBM, RiskGLM
from azoic.preprocessing import AutoBinner, AutoGrouper

__all__ = [
    "export_production",
    "RevisedTariff",
    "revise_tariff",
    "distill_gbm",
    "export_tariff",
    "extract_tariff",
    "apply_tariff",
    "recalibrate_for_total",
]


def distill_gbm(
    teacher: RiskGBM | Pipeline,
    X_fit: pd.DataFrame,
    X_validation: pd.DataFrame,
) -> RiskGLM | Pipeline:
    """Fit an exportable log-link GLM to a fitted positive-objective GBM.

    The student is a ``RiskGLM`` that inherits the teacher's objective as its
    family (tweedie, poisson, or gamma) and, for tweedie, the teacher's
    ``tweedie_variance_power``; it fits with the ``RiskGLM`` default
    ``alpha=0.001``. The fit frame teaches the student; the separate
    validation frame supplies only held-out fidelity metrics. Both use the
    teacher's exposure column as sample weight, and both frames must yield
    positive, finite exposure and teacher predictions. A pipeline result
    contains copied, already-fitted upstream preprocessing (bins and group
    mappings are not relearned) and exposes the metrics in
    ``distillation_metrics_``.

    Callers must supply disjoint observations for fitting and validation.
    The object-identity guard only rejects reuse of the same frame object;
    distinct frames (including copies) do not prove row independence. The CLI
    uses the run's stored training and test positions.
    """
    if not isinstance(X_fit, pd.DataFrame) or not isinstance(X_validation, pd.DataFrame):
        raise TypeError("distill_gbm requires pandas DataFrame fit and validation frames")
    if X_fit.empty or X_validation.empty or X_fit is X_validation:
        raise ValueError("distill_gbm requires non-empty, separate fit and validation frames")

    gbm = teacher.steps[-1][1] if isinstance(teacher, Pipeline) else teacher
    if not isinstance(gbm, RiskGBM):
        raise ValueError("distill_gbm requires a RiskGBM or a pipeline ending in RiskGBM")
    if not hasattr(gbm, "backend_"):
        raise ValueError("distill_gbm requires a fitted RiskGBM teacher")
    if gbm.objective not in {"tweedie", "poisson", "gamma"}:
        raise ValueError(
            "distill_gbm supports only tweedie, poisson, and gamma objectives; "
            f"got {gbm.objective!r}"
        )
    if gbm.exposure_col is None:
        raise ValueError("distill_gbm requires the teacher to define exposure_col")

    for name, frame in (("fit", X_fit), ("validation", X_validation)):
        if gbm.exposure_col not in frame:
            raise ValueError(f"distill_gbm {name} frame is missing {gbm.exposure_col!r}")
        exposure = frame[gbm.exposure_col].to_numpy(dtype=float)
        if not np.isfinite(exposure).all() or np.any(exposure <= 0):
            raise ValueError(f"distill_gbm {name} exposure must be positive and finite")

    fit_frame, validation_frame = X_fit, X_validation
    if isinstance(teacher, Pipeline) and len(teacher.steps) > 1:
        fit_frame = teacher[:-1].transform(X_fit)
        validation_frame = teacher[:-1].transform(X_validation)
    teacher_fit = np.asarray(gbm.predict(fit_frame), dtype=float)
    teacher_validation = np.asarray(gbm.predict(validation_frame), dtype=float)
    for name, prediction in (("fit", teacher_fit), ("validation", teacher_validation)):
        if not np.isfinite(prediction).all() or np.any(prediction <= 0):
            raise ValueError(f"distill_gbm teacher {name} predictions must be positive and finite")

    student = RiskGLM(
        family=gbm.objective,
        link="log",
        exposure_col=gbm.exposure_col,
        tweedie_power=(gbm.tweedie_variance_power if gbm.objective == "tweedie" else None),
    ).fit(fit_frame, teacher_fit)
    student_validation = np.asarray(student.predict(validation_frame), dtype=float)
    if not np.isfinite(student_validation).all() or np.any(student_validation <= 0):
        raise ValueError("distill_gbm student validation predictions must be positive and finite")

    exposure_validation = X_validation[gbm.exposure_col].to_numpy(dtype=float)
    power = {
        "poisson": 1.0,
        "gamma": 2.0,
        "tweedie": gbm.tweedie_variance_power,
    }[gbm.objective]
    metrics = {
        "teacher_student_deviance": float(
            mean_tweedie_deviance(
                teacher_validation,
                student_validation,
                sample_weight=exposure_validation,
                power=power,
            )
        ),
        "student_teacher_total_ratio": float(
            np.dot(student_validation, exposure_validation)
            / np.dot(teacher_validation, exposure_validation)
        ),
    }
    student.distillation_metrics_ = metrics
    if not isinstance(teacher, Pipeline):
        return student
    distilled = Pipeline(
        [*deepcopy(teacher.steps[:-1]), (teacher.steps[-1][0], student)],
        memory=teacher.memory,
        verbose=teacher.verbose,
    )
    vars(distilled)["distillation_metrics_"] = metrics
    return distilled


def _require_log_link(backend) -> None:
    """Multiplicative composition is exact only for a log link. Glum may keep
    ``backend.link == "auto"`` post-fit, so verify the resolved ``link_instance``
    class rather than the stored string."""
    inst = getattr(backend, "link_instance", None)
    cls = type(inst).__name__ if inst is not None else ""
    if cls.endswith("LogLink"):
        return
    link_str = getattr(backend, "link", "")
    raise ValueError(
        "export_tariff requires a log-link GLM (multiplicative tariff); "
        f"got backend.link={link_str!r} resolved to {cls!r}. "
        "Pass `link='log'` when constructing RiskGLM."
    )


def _positive_exp(log_value, name):
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        value = np.exp(log_value)
    if not np.isfinite(value).all() or np.any(value <= 0):
        raise ValueError(f"{name} must be representable as positive and finite values")
    return value


def extract_tariff(glm: RiskGLM, *, reference: dict[str, Hashable] | None = None) -> dict:
    """Decompose a fitted ``RiskGLM`` into a multiplicative tariff structure.

    Returns a dict with keys:
        ``base_rate``   -- structural base (intercept folded with the
            reference-level coefficients for each categorical feature).
        ``reference``   -- ``{categorical_feature: chosen_reference_level}``.
        ``numeric``      -- ``{numeric_feature: coefficient}``.
        ``categorical`` -- ``{categorical_feature: {level: multiplicative_factor
            relative to reference}}`` (reference level has factor ``1.0``).
        ``mapping``     -- ``pd.DataFrame`` describing the feature encoding.

    The returned ``base_rate`` is *structural* (intercept + ref levels only);
    pass the returned dict through ``recalibrate_for_total`` (or call
    ``export_tariff`` with the ``(X, y, exposure_col, recalibrate=True)``
    quadruple) to shift the base so the tariff reproduces an observed
    portfolio total.

    Coefficients must be finite; the structural base and categorical factors
    must be representable as positive, finite floats. Numeric coefficients
    remain in log space; workbook export additionally requires representable
    per-unit factors.
    """
    if not hasattr(glm, "backend_"):
        raise ValueError("extract_tariff: glm must be fitted (no `backend_` attr).")
    backend = glm.backend_
    _require_log_link(backend)

    coefs = np.asarray(backend.coef_, dtype=float)
    intercept = float(backend.intercept_)
    if not np.isfinite(coefs).all() or not np.isfinite(intercept):
        raise ValueError("extract_tariff: coefficients and intercept must be finite")
    term_names = list(getattr(backend, "term_names_", []) or [])
    cat_levels: dict[str, list[Hashable]] = dict(getattr(backend, "categorical_levels_", {}) or {})
    if len(term_names) != len(coefs):
        raise ValueError(
            "extract_tariff: glum metadata mismatch: "
            f"term_names_ has {len(term_names)} entries but coef_ has {len(coefs)}."
        )
    for feat, levels in cat_levels.items():
        if not levels:
            raise ValueError(
                "extract_tariff: glum metadata mismatch for categorical feature "
                f"{feat!r}: categorical_levels_ is empty."
            )
        count = term_names.count(feat)
        if count != len(levels):
            raise ValueError(
                "extract_tariff: glum metadata mismatch for categorical feature "
                f"{feat!r}: term_names_ has {count} entries but categorical_levels_ has "
                f"{len(levels)}."
            )

    numeric: dict[str, float] = {}
    raw_cat: dict[str, dict[Hashable, float]] = {feat: {} for feat in cat_levels}
    positions = dict.fromkeys(cat_levels, 0)
    for term, coef in zip(term_names, coefs, strict=True):
        if term not in cat_levels:
            if term in numeric:
                raise ValueError(
                    f"extract_tariff: glum metadata mismatch: duplicate numeric term {term!r}."
                )
            numeric[term] = float(coef)
            continue
        position = positions[term]
        raw_cat[term][cat_levels[term][position]] = float(coef)
        positions[term] += 1

    chosen_ref: dict[str, Hashable] = {}
    reference = dict(reference or {})
    for feat, levels in cat_levels.items():
        if feat in reference:
            ref = reference[feat]
            if not any(type(ref) is type(level) and ref == level for level in levels):
                raise ValueError(
                    f"reference level {ref!r} not in feature {feat!r} levels {list(levels)}"
                )
            chosen_ref[feat] = ref
        else:
            chosen_ref[feat] = levels[0]

    base_rate = float(
        _positive_exp(
            fsum([intercept, *(raw_cat[feat][ref] for feat, ref in chosen_ref.items())]),
            "extract_tariff: structural base",
        )
    )

    categorical: dict[str, dict[Hashable, float]] = {}
    for feat, levels in cat_levels.items():
        level_coefs = raw_cat[feat]
        ref_coef = level_coefs[chosen_ref[feat]]
        categorical[feat] = {
            level: float(
                _positive_exp(
                    level_coefs[level] - ref_coef,
                    f"extract_tariff: categorical factor {feat!r}/{level!r}",
                )
            )
            for level in levels
        }

    return {
        "base_rate": base_rate,
        "reference": chosen_ref,
        "numeric": numeric,
        "categorical": categorical,
        "mapping": _mapping_frame(backend, cat_levels=cat_levels, reference=chosen_ref),
    }


def _mapping_frame(backend, *, cat_levels, reference) -> pd.DataFrame:
    term_names = list(getattr(backend, "term_names_", []) or [])
    cat_set = set(cat_levels)
    rows: list[dict] = []
    seen: set[str] = set()
    for term in term_names:
        if term in seen:
            continue
        seen.add(term)
        if term in cat_set:
            levels = list(cat_levels[term])
            rows.append(
                {
                    "feature": term,
                    "role": "categorical",
                    "dtype": "category",
                    "levels": ", ".join(map(str, levels)),
                    "n_levels": len(levels),
                    "reference_level": str(reference[term]),
                }
            )
        else:
            rows.append(
                {
                    "feature": term,
                    "role": "numeric",
                    "dtype": "",
                    "levels": "",
                    "n_levels": 0,
                    "reference_level": "",
                }
            )
    return pd.DataFrame(
        rows,
        columns=pd.Index(["feature", "role", "dtype", "levels", "n_levels", "reference_level"]),
    )


def _factors_frame(tariff: dict) -> pd.DataFrame:
    """One row per (feature, level): numeric gets `_per_unit`, categorical
    gets one row per level."""
    rows: list[dict] = []
    for feat, coef in tariff["numeric"].items():
        rows.append(
            {
                "feature": feat,
                "level": "_per_unit",
                "multiplicative_factor": float(
                    _positive_exp(coef, f"export_tariff: per-unit factor {feat!r}")
                ),
                "application": "raise_factor ** value",
            }
        )
    for feat, lvl_factors in tariff["categorical"].items():
        for lvl, f in lvl_factors.items():
            if not np.isfinite(f) or f <= 0:
                raise ValueError("export_tariff: categorical factors must be positive and finite")
            rows.append(
                {
                    "feature": feat,
                    "level": lvl,
                    "multiplicative_factor": float(f),
                    "application": "multiply_by_factor_matching_level",
                }
            )
    return pd.DataFrame(
        rows,
        columns=pd.Index(["feature", "level", "multiplicative_factor", "application"]),
    ).assign(level=pd.Series([row["level"] for row in rows], dtype=object))


def apply_tariff(tariff: dict, X: pd.DataFrame) -> np.ndarray:
    """Per-row pure-premium rate under the multiplicative tariff on ``X``.

    Equivalent to ``RiskGLM.predict(X)`` when ``tariff`` has not been
    recalibrated. Numeric inputs must be finite and categorical levels must
    have been seen when the tariff was extracted. The linear predictor is
    summed before exponentiation. Invalid factors and unrepresentable rates
    raise ``ValueError``; a zero recalibrated base produces zero rates.
    """
    if not isinstance(X, pd.DataFrame):
        raise TypeError("apply_tariff requires a pandas DataFrame X.")
    base = float(tariff["base_rate"])
    if not np.isfinite(base) or base < 0:
        raise ValueError("apply_tariff: base rate must be non-negative and finite")
    linear = np.full(len(X), np.log(base) if base > 0 else 0.0, dtype=float)

    for feat, coef in tariff["numeric"].items():
        if feat not in X.columns:
            raise KeyError(f"apply_tariff: numeric feature {feat!r} not in X.columns")
        values = X[feat].to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValueError(f"apply_tariff: numeric feature {feat!r} must be finite")
        if not np.isfinite(coef):
            raise ValueError(f"apply_tariff: numeric coefficient {feat!r} must be finite")
        with np.errstate(over="ignore", invalid="ignore"):
            linear += coef * values

    for feat, lvl_factors in tariff["categorical"].items():
        if feat not in X.columns:
            raise KeyError(f"apply_tariff: categorical feature {feat!r} not in X.columns")
        level_values = np.asarray(list(lvl_factors.values()), dtype=float)
        if not np.isfinite(level_values).all() or np.any(level_values <= 0):
            raise ValueError(
                f"apply_tariff: categorical factors {feat!r} must be positive and finite"
            )
        factors = X[feat].map(
            pd.Series(level_values, index=pd.Index(list(lvl_factors), dtype=object))
        )
        if factors.isna().any():
            unknown = X.loc[factors.isna(), feat].drop_duplicates().tolist()
            raise ValueError(
                f"apply_tariff: categorical feature {feat!r} has unknown levels: {unknown}"
            )
        with np.errstate(over="ignore", invalid="ignore"):
            linear += np.log(factors.to_numpy(dtype=float))

    if base == 0:
        return np.zeros(len(X), dtype=float)
    return _positive_exp(linear, "apply_tariff: rates")


def recalibrate_for_total(
    tariff: dict,
    *,
    predicted_total: float,
    observed_total: float,
) -> float:
    """Shift the tariff base so it reproduces an observed portfolio total.

    ``predicted_total`` is the sum of model-predicted pure premium times
    exposure; ``observed_total`` is the sum of observed aggregate claim amount.
    Returns the new base rate. A zero observed total returns zero; otherwise
    an unrepresentable adjusted base raises ``ValueError``.
    """
    if not np.isfinite(predicted_total) or predicted_total <= 0:
        raise ValueError("recalibrate: model predicted total must be positive and finite")
    if not np.isfinite(observed_total) or observed_total < 0:
        raise ValueError("recalibrate: observed total must be non-negative and finite")
    base = float(tariff["base_rate"])
    if not np.isfinite(base) or base < 0:
        raise ValueError("recalibrate: base rate must be non-negative and finite")
    if observed_total == 0 or base == 0:
        return 0.0
    return float(
        _positive_exp(
            fsum([np.log(base), np.log(observed_total), -np.log(predicted_total)]),
            "recalibrate: base rate",
        )
    )


def _pipeline_parts(estimator, X):
    if not isinstance(estimator, Pipeline):
        return estimator, X, pd.DataFrame()

    from azoic.workflow import _drop_columns

    rows = []
    transformed = X
    for name, step in estimator.steps[:-1]:
        if step is None or (isinstance(step, str) and step == "passthrough"):
            continue
        if type(step) is AutoBinner:
            for feature, edges in step.mapping_.items():
                levels = list(step.category_dtypes_[feature].categories)
                rows.append(
                    {
                        "feature": feature,
                        "role": "binned",
                        "dtype": "category",
                        "levels": ", ".join(map(str, levels)),
                        "n_levels": len(levels),
                        "reference_level": "",
                        "mapping": ", ".join(map(str, edges)),
                        "interval_closure": step.closure_[feature],
                        "missing_destination": str(levels[step.missing_[feature]]),
                    }
                )
        elif type(step) is AutoGrouper:
            for feature, mapping in step.mapping_.items():
                levels = list(step.category_dtypes_[feature].categories)
                rows.append(
                    {
                        "feature": feature,
                        "role": "grouped",
                        "dtype": "category",
                        "levels": ", ".join(map(str, levels)),
                        "n_levels": len(levels),
                        "reference_level": "",
                        "mapping": "; ".join(
                            f"{level!r} -> {group!r}"
                            for level, group in sorted(
                                mapping.items(),
                                key=lambda item: str(item[0]),
                            )
                        ),
                        "missing_destination": str(step.missing_[feature]),
                        "unseen_destination": str(
                            step.unseen_.get(feature, step.missing_[feature])
                        ),
                    }
                )
        elif (
            type(step) is FunctionTransformer
            and step.func is _drop_columns
            and not step.validate
            and step.feature_names_out is None
        ):
            columns = step.kw_args["columns"]
            if isinstance(columns, str):
                columns = [columns]
            rows.extend({"feature": column, "role": "dropped"} for column in columns)
        else:
            raise ValueError(
                f"export_tariff: unsupported preprocessing step {name!r} "
                f"({type(step).__name__}); only AutoBinner, AutoGrouper, workflow "
                "column removal, None and 'passthrough' can be represented in the workbook"
            )
        if transformed is not None:
            transformed = step.transform(transformed)
    return estimator.steps[-1][1], transformed, pd.DataFrame(rows)


@dataclass(frozen=True)
class RevisedTariff:
    """A post-fit tariff, separate from its source model; created by ``revise_tariff``.

    This is a scoring artifact, not an estimator to fit or tune. Containers are
    caller-mutable, like Run containers. Use the factory to validate revisions.
    """

    source: RiskGLM | Pipeline
    tariff: dict
    revision: dict

    @property
    def feature_names_in_(self) -> np.ndarray:
        return self.source.feature_names_in_

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Predict revised pure-premium rates on raw feature columns."""
        X = X[[column for column in self.feature_names_in_ if column in X]]
        _, transformed, _ = _pipeline_parts(self.source, X)
        return apply_tariff(self.tariff, transformed)


def revise_tariff(
    model: RiskGLM | Pipeline | RevisedTariff,
    replacements: list[dict],
    *,
    X: pd.DataFrame | None = None,
    y: pd.Series | np.ndarray | None = None,
    exposure_col: str | None = None,
    recalibrate: bool = True,
) -> RevisedTariff:
    """Copy a fitted tariff, replace factors with reasons and optionally recalibrate.

    Each replacement has feature, level, factor and reason. Numeric per-unit
    factors use level ``_per_unit``. Category levels retain their scalar types.
    Callers must declare the training population with X/aggregate y/exposure_col;
    workflow.revise_run verifies it against saved identity and train positions.
    """
    previous = model if isinstance(model, RevisedTariff) else None
    source = deepcopy(model.source if isinstance(model, RevisedTariff) else model)
    glm, _, _ = _pipeline_parts(source, None)
    if not isinstance(glm, RiskGLM):
        raise ValueError("revise_tariff requires a fitted RiskGLM or supported GLM pipeline")
    tariff = deepcopy(previous.tariff) if previous is not None else extract_tariff(glm)
    if previous is not None:
        tariff["base_rate"] = previous.revision["structural_base"]
    changes = deepcopy(previous.revision["changes"]) if previous is not None else []
    if not isinstance(replacements, list):
        raise ValueError("factor replacements must be a list of records")
    seen = set()
    for replacement in replacements:
        if not isinstance(replacement, dict) or set(replacement) != {
            "feature",
            "level",
            "factor",
            "reason",
        }:
            raise ValueError("factor replacements require feature, level, factor and reason")
        feature, level = replacement["feature"], replacement["level"]
        reason, factor = replacement["reason"], replacement["factor"]
        if not isinstance(feature, str) or not feature:
            raise ValueError("replacement feature must be a nonempty string")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("each factor replacement requires a nonempty reason")
        if (
            isinstance(factor, bool)
            or not isinstance(factor, Real)
            or not np.isfinite(factor)
            or factor <= 0
        ):
            raise ValueError("replacement factors must be positive finite numbers")
        key = (feature, type(level), level)
        if key in seen:
            raise ValueError("factor replacements must not repeat a feature/level")
        seen.add(key)
        if feature in tariff["numeric"]:
            if level != "_per_unit":
                raise ValueError("numeric replacement level must be '_per_unit'")
            original = float(_positive_exp(tariff["numeric"][feature], "original per-unit factor"))
            tariff["numeric"][feature] = float(np.log(factor))
        elif feature in tariff["categorical"]:
            levels = tariff["categorical"][feature]
            if not any(type(level) is type(known) and level == known for known in levels):
                raise ValueError(f"unknown typed replacement level for feature {feature!r}")
            original = levels[level]
            levels[level] = float(factor)
        else:
            raise ValueError(f"unknown replacement feature {feature!r}")
        changes.append({**deepcopy(replacement), "original_factor": original})
    structural_base = tariff["base_rate"]
    calibration = {"applied": False, "multiplier": 1.0}
    if recalibrate:
        if X is None or y is None or exposure_col is None:
            raise ValueError(
                "revision recalibration requires training X, aggregate y and exposure_col"
            )
        exposure, amounts = _calibration_arrays(X, y, exposure_col)
        predictors = X[[column for column in source.feature_names_in_ if column in X]]
        _, transformed, _ = _pipeline_parts(source, predictors)
        predicted_total = float(np.dot(apply_tariff(tariff, transformed), exposure))
        observed_total = float(amounts.sum())
        tariff["base_rate"] = recalibrate_for_total(
            tariff, predicted_total=predicted_total, observed_total=observed_total
        )
        multiplier = observed_total / predicted_total
        if not np.isfinite(multiplier):
            raise ValueError("revision calibration multiplier must be finite")
        calibration = {
            "applied": True,
            "multiplier": multiplier,
            "predicted_total_before": predicted_total,
            "observed_total": observed_total,
            "n_rows": len(X),
            "exposure_total": float(exposure.sum()),
        }
    revision = {
        "changes": changes,
        "structural_base": structural_base,
        "calibration": calibration,
    }
    return RevisedTariff(source, tariff, revision)


def _calibration_arrays(X, y, exposure_col):
    exposure = np.asarray(X[exposure_col].to_numpy(), dtype=float)
    amounts = check_array(y, dtype=float, ensure_2d=False, input_name="y")
    if amounts.ndim != 1:
        raise ValueError("recalibrate: y must be one-dimensional")
    check_consistent_length(X, amounts)
    if not np.isfinite(exposure).all() or np.any(exposure <= 0):
        raise ValueError("recalibrate: exposure must contain only positive finite values")
    if np.any(exposure < EXPOSURE_FLOOR):
        raise ValueError("recalibrate: exposure must be at least 1/366 (one day)")
    if np.any(amounts < 0):
        raise ValueError("recalibrate: y must contain only non-negative values")
    return exposure, amounts


def export_tariff(
    glm: RiskGLM | Pipeline | RevisedTariff,
    path: str | Path,
    *,
    X: pd.DataFrame | None = None,
    y: pd.Series | np.ndarray | None = None,
    exposure_col: str | None = None,
    reference: dict[str, Hashable] | None = None,
    recalibrate: bool = True,
) -> Path:
    """Write a multiplicative-tariff xlsx from a fitted ``RiskGLM`` or pipeline.

    Three sheets per PRD section 3: ``base_rate`` / ``factors`` / ``mappings``.
    By default ``recalibrate=True`` and an ``(X, y, exposure_col)`` triple is
    expected; the base is shifted so the tariff reproduces the observed
    portfolio total claim amount. Pass ``recalibrate=False`` for the structural
    tariff (intercept + reference levels only).

    ``y`` must be a finite, non-negative one-dimensional vector of aggregate
    claim amounts with one value per row of ``X``. Library callers choose this
    calibration frame explicitly; keep evaluation observations separate. The
    CLI recalibrates only on the run's stored training positions.

    Base and factors must be representable as finite floats (strictly positive
    except for a zero-total recalibrated base). User text is written as literal
    Excel strings; numeric and boolean level labels retain their types.

    Pipeline preprocessing is limited to native ``AutoBinner`` / ``AutoGrouper``
    steps, workflow column removal, ``None`` and ``"passthrough"``. Other
    transforms (including scalers, arbitrary functions and column transformers)
    raise ``ValueError`` before any workbook is opened. Preprocessing mapping
    rows retain pipeline order; removed columns have role ``"dropped"``.

    A sibling temporary workbook is fully written and closed before replacing
    the destination, preserving an existing destination's permission bits.
    Serialization, save, permission or replacement failures leave an existing
    destination unchanged and remove the temporary file.
    """
    revised = glm if isinstance(glm, RevisedTariff) else None
    if revised is not None and recalibrate:
        raise ValueError(
            "revised tariffs already record calibration; export with recalibrate=False"
        )
    if recalibrate and (X is None or y is None or exposure_col is None):
        raise ValueError(
            "recalibrate=True requires X, y, and exposure_col; "
            "pass recalibrate=False for the structural (model-predictive) tariff."
        )

    distillation_metrics = getattr(
        revised.source if revised is not None else glm, "distillation_metrics_", None
    )
    glm, transformed_X, upstream_mappings = _pipeline_parts(revised.source if revised else glm, X)
    if not isinstance(glm, RiskGLM):
        raise ValueError("export_tariff requires a RiskGLM or a pipeline ending in RiskGLM")
    if revised is not None and reference is not None:
        raise ValueError("revised tariff reference is frozen; omit reference")
    tariff = (
        deepcopy(revised.tariff)
        if revised is not None
        else extract_tariff(glm, reference=reference)
    )

    recalibrated = False
    if recalibrate and X is not None and y is not None and exposure_col is not None:
        exposure, y_arr = _calibration_arrays(X, y, exposure_col)
        pred_total = float((np.asarray(glm.predict(transformed_X), dtype=float) * exposure).sum())
        obs_total = float(y_arr.sum())
        tariff["base_rate"] = recalibrate_for_total(
            tariff, predicted_total=pred_total, observed_total=obs_total
        )
        recalibrated = True

    backend = glm.backend_
    base_row = {
        "base_rate": float(tariff["base_rate"]),
        "family": str(getattr(glm, "family", "")),
        "link": str(getattr(backend, "link", "")),
        "intercept_": float(backend.intercept_),
        "recalibrated": bool(recalibrated),
    }
    if revised is not None:
        base_row.update(
            {
                "candidate_type": "revised",
                "recalibrated": revised.revision["calibration"]["applied"],
                "calibration_multiplier": revised.revision["calibration"]["multiplier"],
            }
        )
    if distillation_metrics is not None:
        base_row.update(
            {
                "distilled_from": "RiskGBM",
                "teacher_objective": str(getattr(glm, "family", "")),
                **distillation_metrics,
            }
        )
    base_sheet = pd.DataFrame([base_row])

    if not np.isfinite(tariff["base_rate"]) or tariff["base_rate"] < 0:
        raise ValueError("export_tariff: base rate must be non-negative and finite")
    factors_sheet = _factors_frame(tariff)
    if revised is not None:
        factors_sheet["original_factor"] = factors_sheet["multiplicative_factor"]
        factors_sheet["reason"] = ""
        first_changes = set()
        for change in revised.revision["changes"]:
            key = (change["feature"], type(change["level"]), change["level"])
            mask = (factors_sheet.feature == change["feature"]) & factors_sheet.level.map(
                lambda value, level=change["level"]: type(value) is type(level) and value == level
            )
            if key not in first_changes:
                factors_sheet.loc[mask, "original_factor"] = change["original_factor"]
            previous_reason = factors_sheet.loc[mask, "reason"]
            factors_sheet.loc[mask, "reason"] = previous_reason.map(
                lambda value, reason=change["reason"]: f"{value}; {reason}" if value else reason
            )
            first_changes.add(key)
    mapping_sheet = tariff["mapping"]
    if not upstream_mappings.empty:
        mapping_sheet = pd.concat([mapping_sheet, upstream_mappings], ignore_index=True)

    p = Path(path)
    with NamedTemporaryFile(
        dir=p.parent, prefix=f".{p.stem}-", suffix=p.suffix, delete=False
    ) as temporary_file:
        temporary = Path(temporary_file.name)
    try:
        with (
            temporary.open("wb") as workbook,
            pd.ExcelWriter(workbook, engine="openpyxl") as writer,
        ):
            base_sheet.to_excel(writer, sheet_name="base_rate", index=False)
            factors_sheet.to_excel(writer, sheet_name="factors", index=False)
            mapping_sheet.to_excel(writer, sheet_name="mappings", index=False)
            for sheet in writer.sheets.values():
                for row in sheet:
                    for cell in row:
                        if isinstance(cell.value, str):
                            cell.data_type = "s"
        if p.exists():
            temporary.chmod(S_IMODE(p.stat().st_mode))
        temporary.replace(p)
    finally:
        temporary.unlink(missing_ok=True)
    return p


def export_production(
    run: azoic.Run,
    estimators: Mapping[str, Any],
    *,
    cases: pd.DataFrame,
    feature_units: Mapping[str, str],
    out: str | Path,
) -> Path:
    """Deliver a production GLM to a new directory, without fitting or calibration.

    ``cases`` must be caller-authored synthetic predictors (never portfolio rows).
    They seed automatically added boundaries/neighbors, missing/unseen levels,
    categorical levels and nonfinite numeric rejection cases. JSON cases retain
    unrounded expected rates or explicit rejection. Declare a unit for every
    predictor, including 'category' or 'dimensionless' where appropriate.
    Returns specification.json. This is an engine agreement contract, not a
    deployment system or evidence that a receiving engine has been validated.
    """
    import hashlib
    import json
    import tempfile

    from azoic.workflow import _fitted_fingerprint, _validate_candidates, save_run

    destination = Path(out)
    if destination.exists():
        raise FileExistsError(f"production output already exists: {destination}")
    _validate_candidates(run, estimators)
    if not run.production or run.final_evaluation or len(estimators) != 1:
        raise ValueError("handoff requires one explicit production-refit candidate")
    model, estimator = next(iter(estimators.items()))
    if _fitted_fingerprint(estimator) != run.production["fitted_fingerprint"]:
        raise ValueError("production fitted state changed after refit")
    if set(feature_units) != set(run.feature_names) or any(
        not isinstance(unit, str) or not unit.strip() for unit in feature_units.values()
    ):
        raise ValueError("declare a nonempty unit for every selected feature")
    if cases.empty or not cases.columns.is_unique or set(cases.columns) != set(run.feature_names):
        raise ValueError("supply nonempty synthetic cases with exactly the selected predictors")
    source = estimator.source if isinstance(estimator, RevisedTariff) else estimator
    glm, _, _ = _pipeline_parts(source, None)
    if not isinstance(glm, RiskGLM):
        raise ValueError("production workbook handoff requires a log-link GLM tariff")
    tariff = estimator.tariff if isinstance(estimator, RevisedTariff) else extract_tariff(glm)
    transforms: list[dict[str, Any]] = []
    if isinstance(source, Pipeline):
        for name, step in source.steps[:-1]:
            if isinstance(step, AutoBinner):
                transforms.append(
                    {
                        "step": name,
                        "type": "bins",
                        "features": {
                            feature: {
                                "edges": edges.tolist(),
                                "closure": step.closure_[feature],
                                "missing_bin": step.missing_[feature],
                                "labels": list(step.category_dtypes_[feature].categories),
                            }
                            for feature, edges in step.mapping_.items()
                        },
                    }
                )
            elif isinstance(step, AutoGrouper):
                transforms.append(
                    {
                        "step": name,
                        "type": "groups",
                        "features": {
                            feature: {
                                "groups": [
                                    {"level": level, "group": group}
                                    for level, group in mapping.items()
                                ],
                                "missing": step.missing_[feature],
                                "unseen": step.unseen_.get(feature, step.missing_[feature]),
                            }
                            for feature, mapping in step.mapping_.items()
                        },
                    }
                )
    probes = [(f"synthetic-{i}", row) for i, row in enumerate(cases.to_dict("records"))]
    baseline = probes[0][1]
    for transform in transforms:
        for feature, mapping in transform["features"].items():
            if transform["type"] == "bins":
                for edge in mapping["edges"]:
                    for label, value in (
                        ("below", np.nextafter(edge, -np.inf)),
                        ("at", edge),
                        ("above", np.nextafter(edge, np.inf)),
                    ):
                        probes.append((f"{feature}-{edge}-{label}", {**baseline, feature: value}))
            else:
                for i, group in enumerate(mapping["groups"]):
                    probes.append((f"{feature}-level-{i}", {**baseline, feature: group["level"]}))
    for feature in run.feature_names:
        probes.append((f"{feature}-missing", {**baseline, feature: None}))
        if feature in tariff["numeric"] or any(
            transform["type"] == "bins" and feature in transform["features"]
            for transform in transforms
        ):
            probes.append((f"{feature}-nonfinite", {**baseline, feature: float("inf")}))
        else:
            unknown = "__azoic_unseen__"
            known = set(cases[feature].dropna())
            for transform in transforms:
                mapping = transform["features"].get(feature, {})
                known.update(entry["level"] for entry in mapping.get("groups", []))
            known.update(tariff["categorical"].get(feature, {}))
            while unknown in known:
                unknown += "_"
            probes.append((f"{feature}-unseen", {**baseline, feature: unknown}))
            for i, level in enumerate(tariff["categorical"].get(feature, {})):
                if not any(feature in transform["features"] for transform in transforms):
                    probes.append((f"{feature}-level-{i}", {**baseline, feature: level}))
    agreement = []
    for label, values in probes:
        frame = pd.DataFrame([values])
        try:
            expected = np.asarray(estimator.predict(frame), dtype=float)
            if expected.shape != (1,) or not np.isfinite(expected).all() or (expected < 0).any():
                raise ValueError("invalid predicted rate")
        except (ValueError, TypeError) as error:
            if label.startswith("synthetic-"):
                raise ValueError(f"supplied synthetic case cannot be scored: {label}") from error
            agreement.append(
                {"case": label, "input": values, "outcome": "reject", "error": type(error).__name__}
            )
        else:
            _, transformed, _ = _pipeline_parts(source, frame)
            if not np.allclose(apply_tariff(tariff, transformed), expected, rtol=1e-12, atol=0):
                raise ValueError("tariff arithmetic disagrees with fitted synthetic rates")
            agreement.append(
                {
                    "case": label,
                    "input": values,
                    "outcome": "rate",
                    "expected_rate": float(expected[0]),
                }
            )
    specification = {
        "format": "azoic.production.1",
        "model": model,
        "evidence": "production_refit; no independent final-test score for this fit",
        "features": [
            {
                "name": feature,
                "input_kind": "numeric"
                if feature in tariff["numeric"]
                or any(
                    transform["type"] == "bins" and feature in transform["features"]
                    for transform in transforms
                )
                else "typed_category",
                "synthetic_dtype": str(cases[feature].dtype),
                "unit": feature_units[feature],
            }
            for feature in run.feature_names
        ],
        "portfolio_basis": run.config.spec.model_dump(),
        "prediction_unit": "claim currency per exposure year",
        "period_cost": "predicted_rate * exposure_years; no rounding",
        "numeric_terms": [
            {"feature": feature, "log_coefficient": coefficient}
            for feature, coefficient in tariff["numeric"].items()
        ],
        "categorical_terms": [
            {
                "feature": feature,
                "levels": [{"level": level, "factor": factor} for level, factor in levels.items()],
            }
            for feature, levels in tariff["categorical"].items()
        ],
        "base_rate": tariff["base_rate"],
        "transformations": transforms,
        "formula": "base_rate * exp(sum(log_coefficient * value)) * product(category factors)",
        "input_rules": (
            "ordered transformations first; reject unseen raw GLM levels and nonfinite "
            "numerics; explicit native missing/unseen routes above"
        ),
        "calibration_application": "already included in base_rate; do not multiply again",
        "interval_rules": "right: upper-inclusive <=; left: lower-inclusive >=",
        "calibration": run.models[model].revision.get(
            "calibration", {"applied": False, "multiplier": 1.0}
        ),
        "revisions": run.models[model].revision,
        "production": run.production,
        "training_metrics": run.models[model].metrics,
        "runtime_versions": run.runtime_versions,
        "config": run.config.model_dump(),
        "resolved_params": run.models[model].resolved_params,
        "comparison_tolerance": {"rtol": 1e-12, "atol": 0.0},
        "special_values": (
            "JSON {$float: inf|-inf|nan} means that IEEE floating value; null means missing"
        ),
        "ownership": (
            "Receiving engine validation, deployment, release and rollback belong downstream."
        ),
    }

    def encode(value):
        if isinstance(value, np.generic):
            value = value.item()
        if isinstance(value, float) and not np.isfinite(value):
            return {"$float": str(value)}
        if isinstance(value, Mapping):
            return {str(key): encode(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, np.ndarray)):
            return [encode(item) for item in value]
        return value

    with tempfile.TemporaryDirectory(
        dir=destination.parent, prefix=".azoic-production-"
    ) as temporary:
        staging = Path(temporary) / "bundle"
        staging.mkdir()
        save_run(run, estimators, staging / "production.pkl")
        export_tariff(estimator, staging / "tariff.xlsx", recalibrate=False)
        (staging / "agreement.json").write_text(
            json.dumps(encode(agreement), indent=2, allow_nan=False), encoding="utf-8"
        )
        (staging / "score.py").write_text(_BATCH_SCORING_RECIPE, encoding="utf-8")
        specification["files_sha256"] = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in staging.iterdir()
        }
        (staging / "specification.json").write_text(
            json.dumps(encode(specification), indent=2, allow_nan=False), encoding="utf-8"
        )
        staging.rename(destination)
    return destination / "specification.json"


_BATCH_SCORING_RECIPE = '''"""Trusted matching-environment scoring.
Usage: python score.py input.parquet output.csv.
With no arguments, verify the synthetic agreement cases. Rates remain unrounded.
"""
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from azoic import load_run

root = Path(__file__).resolve().parent
run, estimators = load_run(root / "production.pkl")
model = next(iter(estimators.values()))
if len(sys.argv) == 1:
    def decode(value):
        return float(value["$float"]) if isinstance(value, dict) and "$float" in value else value
    for case in json.loads((root / "agreement.json").read_text()):
        frame = pd.DataFrame([{key: decode(value) for key, value in case["input"].items()}])
        try:
            rate = model.predict(frame)
        except (ValueError, TypeError):
            assert case["outcome"] == "reject", case["case"]
        else:
            assert case["outcome"] == "rate", case["case"]
            np.testing.assert_allclose(rate, [case["expected_rate"]], rtol=1e-12, atol=0)
    print("Synthetic agreement cases passed; receiving-engine agreement remains downstream.")
else:
    if len(sys.argv) != 3:
        raise SystemExit("usage: python score.py [input.parquet output.csv]")
    frame = pd.read_parquet(sys.argv[1])
    rates = np.asarray(model.predict(frame[run.feature_names]), dtype=float)
    if rates.shape != (len(frame),) or not np.isfinite(rates).all() or (rates < 0).any():
        raise ValueError("expected one finite nonnegative rate per row")
    output = pd.DataFrame({"predicted_rate": rates})
    id_col = run.config.spec.id_col
    if id_col and id_col in frame:
        output.insert(0, id_col, frame[id_col].to_numpy())
    exposure_col = run.config.spec.exposure
    if exposure_col in frame:
        exposure = frame[exposure_col].to_numpy(dtype=float)
        if not np.isfinite(exposure).all() or (exposure < 0).any():
            raise ValueError("period exposure must be finite and nonnegative")
        output["predicted_period_cost"] = rates * exposure
    output.to_csv(sys.argv[2], index=False)
'''
