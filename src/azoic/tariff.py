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

from collections.abc import Hashable
from copy import deepcopy
from math import fsum
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.utils.validation import check_array, check_consistent_length

from azoic.data import EXPOSURE_FLOOR
from azoic.metrics import mean_tweedie_deviance
from azoic.models import RiskGBM, RiskGLM
from azoic.preprocessing import AutoBinner, AutoGrouper

__all__ = [
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

    _, fit_frame, _ = _pipeline_parts(teacher, X_fit)
    _, validation_frame, _ = _pipeline_parts(teacher, X_validation)
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
    )


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
        factors = X[feat].map(lvl_factors)
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

    rows = []
    transformed = X
    for _, step in estimator.steps[:-1]:
        if isinstance(step, AutoBinner):
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
                    }
                )
        elif isinstance(step, AutoGrouper):
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
                    }
                )
        if transformed is not None:
            transformed = step.transform(transformed)
    return estimator.steps[-1][1], transformed, pd.DataFrame(rows)


def export_tariff(
    glm: RiskGLM | Pipeline,
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
    """
    if recalibrate and (X is None or y is None or exposure_col is None):
        raise ValueError(
            "recalibrate=True requires X, y, and exposure_col; "
            "pass recalibrate=False for the structural (model-predictive) tariff."
        )

    distillation_metrics = getattr(glm, "distillation_metrics_", None)
    glm, transformed_X, upstream_mappings = _pipeline_parts(glm, X)
    if not isinstance(glm, RiskGLM):
        raise ValueError("export_tariff requires a RiskGLM or a pipeline ending in RiskGLM")
    tariff = extract_tariff(glm, reference=reference)

    recalibrated = False
    if recalibrate and X is not None and y is not None and exposure_col is not None:
        exposure = np.asarray(X[exposure_col].to_numpy(), dtype=float)
        y_arr = check_array(y, dtype=float, ensure_2d=False, input_name="y")
        if y_arr.ndim != 1:
            raise ValueError("recalibrate: y must be one-dimensional")
        check_consistent_length(X, y_arr)
        if not np.isfinite(exposure).all() or np.any(exposure <= 0):
            raise ValueError("recalibrate: exposure must contain only positive finite values")
        if np.any(exposure < EXPOSURE_FLOOR):
            raise ValueError("recalibrate: exposure must be at least 1/366 (one day)")
        if np.any(y_arr < 0):
            raise ValueError("recalibrate: y must contain only non-negative values")
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
    if distillation_metrics is not None:
        base_row.update(
            {
                "distilled_from": "RiskGBM",
                "teacher_objective": str(getattr(glm, "family", "")),
                **distillation_metrics,
            }
        )
    base_sheet = pd.DataFrame([base_row])

    factors_sheet = _factors_frame(tariff)
    mapping_sheet = tariff["mapping"]
    if not upstream_mappings.empty:
        mapping_sheet = pd.concat([mapping_sheet, upstream_mappings], ignore_index=True)

    p = Path(path)
    with pd.ExcelWriter(p, engine="openpyxl") as writer:
        base_sheet.to_excel(writer, sheet_name="base_rate", index=False)
        factors_sheet.to_excel(writer, sheet_name="factors", index=False)
        mapping_sheet.to_excel(writer, sheet_name="mappings", index=False)
        for sheet in writer.sheets.values():
            for row in sheet:
                for cell in row:
                    if isinstance(cell.value, str):
                        cell.data_type = "s"
    return p
