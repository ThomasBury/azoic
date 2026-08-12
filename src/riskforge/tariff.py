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
      (feature / dtype / role / levels / reference_level). Caller-supplied
      mappings (e.g. an ``AutoBinner.mapping_`` / ``AutoGrouper.mapping_``)
      are concatenated when supplied via the ``mappings`` kwarg.

ponytail: ceiling -- the upstream binning / grouping mapping lives in
``AutoBinner`` / ``AutoGrouper`` of ``preprocessing.py``; v1 ``workflow.run_experiment``
feeds raw features straight to the GLM so the CLI ships no upstream mapping.
Wire the ``mappings`` arg through once a real pipeline wants it.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from riskforge.models import RiskGLM

__all__ = ["export_tariff", "extract_tariff", "apply_tariff", "recalibrate_for_total"]


# glum encodes categorical columns as ``feature[level]``; numeric columns keep
# their plain name. The regex splits an encoded column name into
# (original_feature, level).
_ENCODED = re.compile(r"^(.+?)\[(.+)\]$")


def _split_encoded(name: str) -> tuple[str, str | None]:
    m = _ENCODED.match(name)
    if not m:
        return name, None
    return m.group(1), m.group(2)


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


def extract_tariff(
    glm: RiskGLM, *, reference: dict[str, str] | None = None
) -> dict:
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
    """
    if not hasattr(glm, "backend_"):
        raise ValueError("extract_tariff: glm must be fitted (no `backend_` attr).")
    backend = glm.backend_
    _require_log_link(backend)

    feature_names = list(backend.feature_names_)
    coefs = np.asarray(backend.coef_, dtype=float)
    intercept = float(backend.intercept_)
    cat_levels: dict = dict(getattr(backend, "categorical_levels_", {}) or {})

    numeric: dict[str, float] = {}
    raw_cat: dict[str, dict[str, float]] = {}
    for name, c in zip(feature_names, coefs, strict=True):
        feat, level = _split_encoded(name)
        if level is None:
            numeric[feat] = float(c)
        else:
            raw_cat.setdefault(feat, {})[level] = float(c)

    chosen_ref: dict[str, str] = {}
    reference = dict(reference or {})
    for feat, lvls in cat_levels.items():
        if feat in reference:
            ref = reference[feat]
            if ref not in lvls:
                raise ValueError(
                    f"reference level {ref!r} not in feature {feat!r} "
                    f"levels {list(lvls)}"
                )
            chosen_ref[feat] = ref
        else:
            # Default reference = first-sorted level (deterministic, no data peek).
            chosen_ref[feat] = sorted(lvls, key=str)[0]

    # base = exp(intercept) * Π_cat exp(coef[ref_level])
    base_rate = float(np.exp(intercept))
    for feat, ref in chosen_ref.items():
        base_rate *= float(np.exp(raw_cat.get(feat, {}).get(ref, 0.0)))

    # Categorical factors relative to the reference; reference -> 1.0.
    categorical: dict[str, dict[str, float]] = {}
    for feat, lvl_coefs in raw_cat.items():
        ref = chosen_ref[feat]
        c_ref = lvl_coefs.get(ref, 0.0)
        categorical[feat] = {
            lvl: float(np.exp(c - c_ref)) for lvl, c in lvl_coefs.items()
        }

    mapping = _mapping_frame(
        backend,
        cat_levels=cat_levels,
        reference=chosen_ref,
    )
    return {
        "base_rate": base_rate,
        "reference": chosen_ref,
        "numeric": numeric,
        "categorical": categorical,
        "mapping": mapping,
    }


def _mapping_frame(backend, *, cat_levels, reference) -> pd.DataFrame:
    term_names = list(getattr(backend, "term_names_", []) or [])
    encoded_names = list(backend.feature_names_)
    # glum deprecated `feature_dtypes_` in favour of `categorical_levels_`; the
    # post-fit dtype of numeric columns is no longer exposed, so the `dtype` column
    # records only the categorical features' kind ("category"). ponytail: the
    # dtype column is self-documenting metadata -- drop it entirely if a future
    # caller needs the real numeric dtype.
    cat_set = set(cat_levels.keys())

    rows: list[dict] = []
    seen: set[str] = set()
    for term, enc in zip(term_names, encoded_names, strict=True):
        _, level = _split_encoded(enc)
        is_categorical = level is not None
        if term in seen:
            continue
        seen.add(term)
        if is_categorical:
            lvls = list(cat_levels.get(term, []))
            rows.append(
                {
                    "feature": term,
                    "role": "categorical",
                    "dtype": "category" if term in cat_set else "",
                    "levels": ", ".join(str(lvl) for lvl in lvls),
                    "n_levels": len(lvls),
                    "reference_level": str(reference.get(term, "")),
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
        columns=[
            "feature",
            "role",
            "dtype",
            "levels",
            "n_levels",
            "reference_level",
        ],
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
                "multiplicative_factor": float(np.exp(coef)),
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
        columns=["feature", "level", "multiplicative_factor", "application"],
    )


def apply_tariff(tariff: dict, X: pd.DataFrame) -> np.ndarray:
    """Per-row pure-premium rate under the multiplicative tariff on ``X``.

    Equivalent to ``RiskGLM.predict(X)`` when ``tariff`` has not been
    recalibrated (the multiplicative decomposition reconstructs the log-link
    GLM prediction up to float-rounding in the exponent order).
    """
    if not isinstance(X, pd.DataFrame):
        raise TypeError("apply_tariff requires a pandas DataFrame X.")
    rate = np.full(len(X), float(tariff["base_rate"]), dtype=float)

    for feat, coef in tariff["numeric"].items():
        if feat not in X.columns:
            raise KeyError(f"apply_tariff: numeric feature {feat!r} not in X.columns")
        rate = rate * np.power(np.exp(coef), X[feat].to_numpy(dtype=float))

    for feat, lvl_factors in tariff["categorical"].items():
        if feat not in X.columns:
            raise KeyError(f"apply_tariff: categorical feature {feat!r} not in X.columns")
        vals = X[feat].to_numpy()
        lvl_arr = np.ones(len(vals), dtype=float)
        for lvl, factor in lvl_factors.items():
            lvl_arr = np.where(vals == lvl, float(factor), lvl_arr)
        rate = rate * lvl_arr

    return rate


def recalibrate_for_total(
    tariff: dict,
    *,
    predicted_total: float,
    observed_total: float,
) -> float:
    """Shift the tariff base so it reproduces an observed portfolio total.

    ``predicted_total`` is the sum of model-predicted pure premium times
    exposure; ``observed_total`` is the sum of observed aggregate claim amount.
    Returns the new base rate.
    """
    if predicted_total <= 0:
        raise ValueError("recalibrate: model predicted total must be positive")
    if observed_total < 0:
        raise ValueError("recalibrate: observed total must be non-negative")
    return float(tariff["base_rate"] * (observed_total / predicted_total))


def export_tariff(
    glm: RiskGLM,
    path: str | Path,
    *,
    X: pd.DataFrame | None = None,
    y: pd.Series | np.ndarray | None = None,
    exposure_col: str | None = None,
    reference: dict[str, str] | None = None,
    recalibrate: bool = True,
    mappings: pd.DataFrame | dict[str, pd.DataFrame] | None = None,
) -> Path:
    """Write a multiplicative-tariff xlsx from a fitted ``RiskGLM``.

    Three sheets per PRD section 3: ``base_rate`` / ``factors`` / ``mappings``.
    By default ``recalibrate=True`` and an ``(X, y, exposure_col)`` triple is
    expected; the base is shifted so the tariff reproduces the observed
    portfolio total claim amount. Pass ``recalibrate=False`` for the structural
    tariff (intercept + reference levels only).
    """
    if recalibrate and (X is None or y is None or exposure_col is None):
        raise ValueError(
            "recalibrate=True requires X, y, and exposure_col; "
            "pass recalibrate=False for the structural (model-predictive) tariff."
        )

    tariff = extract_tariff(glm, reference=reference)

    recalibrated = False
    if recalibrate:
        exposure = np.asarray(X[exposure_col].to_numpy(), dtype=float)
        y_arr = np.asarray(y, dtype=float)
        pred_total = float((np.asarray(glm.predict(X), dtype=float) * exposure).sum())
        obs_total = float(y_arr.sum())
        tariff["base_rate"] = recalibrate_for_total(
            tariff, predicted_total=pred_total, observed_total=obs_total
        )
        recalibrated = True

    backend = glm.backend_
    base_sheet = pd.DataFrame(
        [
            {
                "base_rate": float(tariff["base_rate"]),
                "family": str(getattr(glm, "family", "")),
                "link": str(getattr(backend, "link", "")),
                "intercept_": float(backend.intercept_),
                "recalibrated": bool(recalibrated),
            }
        ]
    )

    factors_sheet = _factors_frame(tariff)
    mapping_sheet = tariff["mapping"]
    if mappings is not None:
        if isinstance(mappings, dict):
            extras = list(mappings.values())
            extra = pd.concat(extras, ignore_index=False) if len(extras) > 1 else extras[0]
        else:
            extra = mappings
        mapping_sheet = pd.concat([mapping_sheet, extra], ignore_index=False)

    p = Path(path)
    with pd.ExcelWriter(p, engine="openpyxl") as writer:
        base_sheet.to_excel(writer, sheet_name="base_rate", index=False)
        factors_sheet.to_excel(writer, sheet_name="factors", index=False)
        mapping_sheet.to_excel(writer, sheet_name="mappings", index=False)
    return p
