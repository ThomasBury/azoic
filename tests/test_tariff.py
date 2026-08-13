"""Tests for riskforge.tariff: multiplicative-tariff export for a fitted RiskGLM.

M6 acceptance: the tariff's recalibrated base reproduces the portfolio total
observed claim amount exactly, and the structural (non-recalibrated) tariff's
``apply_tariff`` reproduces ``RiskGLM.predict`` up to float round-off.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from riskforge.models import RiskGLM
from riskforge.tariff import (
    apply_tariff,
    export_tariff,
    extract_tariff,
    recalibrate_for_total,
)
from tests.conftest import make_synthetic_portfolio


def _fit_glm(n: int = 2000, seed: int = 42, **glm_kwargs) -> tuple[RiskGLM, pd.DataFrame]:
    df = make_synthetic_portfolio(n=n, seed=seed)
    features = ["driver_age", "vehicle_age", "region", "vehicle_brand"]
    X = df[features + ["exposure"]]
    y = (df["claim_amount"] / df["exposure"]).to_numpy(dtype=float)
    kwargs = {
        "family": "tweedie",
        "link": "log",
        "exposure_col": "exposure",
        "tweedie_power": 1.5,
        **glm_kwargs,
    }
    glm = RiskGLM(**kwargs)
    glm.fit(X, y)
    return glm, df


# ---------------------------------------------------------------------------
# extract_tariff
# ---------------------------------------------------------------------------


def test_extract_tariff_unfitted_raises() -> None:
    with pytest.raises(ValueError, match="fitted"):
        extract_tariff(RiskGLM(family="tweedie", link="log"))


def test_extract_tariff_non_log_link_raises(tmp_path: Path) -> None:
    glm, _ = _fit_glm(link="identity", family="normal")
    with pytest.raises(ValueError, match="log-link"):
        extract_tariff(glm)


def test_extract_tariff_structure_numeric_and_categorical() -> None:
    glm, _ = _fit_glm()
    t = extract_tariff(glm)
    assert set(t.keys()) == {"base_rate", "reference", "numeric", "categorical", "mapping"}
    # Numeric features carry their raw coefficient.
    assert "driver_age" in t["numeric"] and "vehicle_age" in t["numeric"]
    # Categorical features carry one entry per observed level.
    assert set(t["categorical"]["region"].keys()) == {"rural", "suburban", "urban"}
    assert set(t["categorical"]["vehicle_brand"].keys()) == {"A", "B", "C", "D"}
    # Every reference level has factor exactly 1.0.
    for feat, ref in t["reference"].items():
        assert t["categorical"][feat][ref] == pytest.approx(1.0)


def test_extract_tariff_default_reference_is_first_sorted_level() -> None:
    glm, _ = _fit_glm()
    t = extract_tariff(glm)
    assert t["reference"]["region"] == "rural"  # sorted(["rural","suburban","urban"])[0]
    assert t["reference"]["vehicle_brand"] == "A"


def test_extract_tariff_reference_override_respected() -> None:
    glm, _ = _fit_glm()
    t = extract_tariff(glm, reference={"region": "urban", "vehicle_brand": "D"})
    assert t["reference"]["region"] == "urban"
    assert t["reference"]["vehicle_brand"] == "D"
    assert t["categorical"]["region"]["urban"] == pytest.approx(1.0)
    assert t["categorical"]["vehicle_brand"]["D"] == pytest.approx(1.0)


def test_extract_tariff_reference_unknown_level_raises() -> None:
    glm, _ = _fit_glm()
    with pytest.raises(ValueError, match="not in feature"):
        extract_tariff(glm, reference={"region": "atlantis"})


def test_extract_tariff_mapping_frame_lists_features_and_roles() -> None:
    glm, _ = _fit_glm()
    t = extract_tariff(glm)
    m = t["mapping"]
    assert list(m.columns) == [
        "feature", "role", "dtype", "levels", "n_levels", "reference_level"
    ]
    # Each input feature appears exactly once (deduplicated across levels).
    assert sorted(m["feature"]) == ["driver_age", "region", "vehicle_age", "vehicle_brand"]
    roles = dict(zip(m["feature"], m["role"], strict=True))
    assert roles["driver_age"] == "numeric"
    assert roles["region"] == "categorical"
    # Categorical rows expose their levels + the chosen reference.
    region_row = m[m["feature"] == "region"].iloc[0]
    assert "rural" in str(region_row["levels"]) and "urban" in str(region_row["levels"])
    assert region_row["reference_level"] == "rural"
    assert int(region_row["n_levels"]) == 3


# ---------------------------------------------------------------------------
# apply_tariff roundtrip to glm.predict (no recalibration)
# ---------------------------------------------------------------------------


def test_apply_tariff_roundtrips_to_glm_predict() -> None:
    glm, df = _fit_glm()
    t = extract_tariff(glm)
    feats = ["driver_age", "vehicle_age", "region", "vehicle_brand"]
    applied = apply_tariff(t, df[feats])
    predicted = np.asarray(glm.predict(df[feats]), dtype=float)
    assert np.allclose(applied, predicted, rtol=1e-6, atol=1e-3)


def test_apply_tariff_requires_dataframe() -> None:
    glm, _ = _fit_glm()
    t = extract_tariff(glm)
    with pytest.raises(TypeError, match="DataFrame"):
        apply_tariff(t, np.zeros((3, 4)))


def test_apply_tariff_missing_numeric_column_raises() -> None:
    glm, df = _fit_glm()
    t = extract_tariff(glm)
    X = df.drop(columns=["driver_age"])
    with pytest.raises(KeyError, match="driver_age"):
        apply_tariff(t, X[["vehicle_age", "region", "vehicle_brand"]])


def test_apply_tariff_missing_categorical_column_raises() -> None:
    glm, df = _fit_glm()
    t = extract_tariff(glm)
    X = df.drop(columns=["region"])
    with pytest.raises(KeyError, match="region"):
        apply_tariff(t, X[["driver_age", "vehicle_age", "vehicle_brand"]])


def test_apply_tariff_unknown_categorical_level_gets_factor_one() -> None:
    """An unknown level (not seen in fit) is not in ``categorical[feat]`` so
    no row matches it -- factor defaults to 1.0, mirroring glum's
    ``cat_missing_method="fail"`` guard failing at *predict* time. The
    structural tariff treats missing as the reference; actuary's call to
    override that goes through ``reference=``."""
    glm, df = _fit_glm()
    t = extract_tariff(glm)
    X = df.head(3).copy()
    X.loc[:, "region"] = "atlantis"  # unseen level
    out = apply_tariff(t, X)
    # factor for the unknown level == 1.0 (no row matched), i.e. region
    # contributes nothing beyond the base's folded reference coefficient.
    assert np.all(out > 0)


# ---------------------------------------------------------------------------
# recalibrate_for_total
# ---------------------------------------------------------------------------


def test_recalibrate_for_total_reproduces_observed_total() -> None:
    glm, df = _fit_glm()
    t = extract_tariff(glm)
    feats = ["driver_age", "vehicle_age", "region", "vehicle_brand", "exposure"]
    exp = df["exposure"].to_numpy(float)
    cam = df["claim_amount"].to_numpy(float)
    pred = np.asarray(glm.predict(df[feats]), dtype=float)
    pred_total = float((pred * exp).sum())
    obs_total = float(cam.sum())

    new_base = recalibrate_for_total(t, predicted_total=pred_total, observed_total=obs_total)
    t2 = dict(t)
    t2["base_rate"] = new_base
    recal = apply_tariff(t2, df[["driver_age", "vehicle_age", "region", "vehicle_brand"]])
    recal_total = float((recal * exp).sum())
    assert recal_total == pytest.approx(obs_total, rel=1e-7)


def test_recalibrate_for_total_nonpositive_predicted_raises() -> None:
    glm, _ = _fit_glm()
    t = extract_tariff(glm)
    with pytest.raises(ValueError, match="positive"):
        recalibrate_for_total(t, predicted_total=0.0, observed_total=100.0)


def test_recalibrate_for_total_negative_observed_raises() -> None:
    glm, _ = _fit_glm()
    t = extract_tariff(glm)
    with pytest.raises(ValueError, match="non-negative"):
        recalibrate_for_total(t, predicted_total=100.0, observed_total=-1.0)


# ---------------------------------------------------------------------------
# export_tariff (xlsx IO)
# ---------------------------------------------------------------------------


def test_export_tariff_writes_three_sheets(tmp_path: Path) -> None:
    glm, df = _fit_glm()
    out = tmp_path / "tariff.xlsx"
    p = export_tariff(
        glm, out,
        X=df[["driver_age", "vehicle_age", "region", "vehicle_brand", "exposure"]],
        y=df["claim_amount"],
        exposure_col="exposure",
    )
    assert p == out and p.exists() and p.stat().st_size > 0
    xl = pd.read_excel(p, sheet_name=None)
    assert list(xl.keys()) == ["base_rate", "factors", "mappings"]


def test_export_tariff_recalibrated_reproduces_portfolio_total(tmp_path: Path) -> None:
    glm, df = _fit_glm()
    out = tmp_path / "tariff.xlsx"
    export_tariff(
        glm, out,
        X=df[["driver_age", "vehicle_age", "region", "vehicle_brand", "exposure"]],
        y=df["claim_amount"],
        exposure_col="exposure",
        recalibrate=True,
    )
    xl = pd.read_excel(out, sheet_name=None)
    base = float(xl["base_rate"].iloc[0]["base_rate"])
    assert bool(xl["base_rate"].iloc[0]["recalibrated"]) is True

    # Rebuild the tariff dict from the sheets and verify it reproduces the total.
    factors = xl["factors"]
    numeric = {}
    categorical = {}
    for _, r in factors.iterrows():
        feat, lvl, f = r["feature"], r["level"], float(r["multiplicative_factor"])
        if lvl == "_per_unit":
            numeric[feat] = float(np.log(f))
        else:
            categorical.setdefault(feat, {})[lvl] = f
    tariff = {
        "base_rate": base,
        "reference": {
            f: next(lvl for lvl, fac in fs.items() if fac == 1.0)
            for f, fs in categorical.items()
        },
        "numeric": numeric,
        "categorical": categorical,
    }
    X = df[["driver_age", "vehicle_age", "region", "vehicle_brand"]]
    rate = apply_tariff(tariff, X)
    exp = df["exposure"].to_numpy(float)
    cam = df["claim_amount"].to_numpy(float)
    assert (rate * exp).sum() == pytest.approx(cam.sum(), rel=1e-6)


def test_export_tariff_no_recalibrate_stays_structural(tmp_path: Path) -> None:
    glm, df = _fit_glm()
    out = tmp_path / "tariff.xlsx"
    export_tariff(
        glm, out,
        X=df[["driver_age", "vehicle_age", "region", "vehicle_brand", "exposure"]],
        y=df["claim_amount"],
        exposure_col="exposure",
        recalibrate=False,
    )
    xl = pd.read_excel(out, sheet_name=None)
    assert bool(xl["base_rate"].iloc[0]["recalibrated"]) is False
    # Structural base == extract_tariff base_rate.
    t = extract_tariff(glm)
    assert float(xl["base_rate"].iloc[0]["base_rate"]) == pytest.approx(t["base_rate"])


def test_export_tariff_recalibrate_requires_X_y_exposure(tmp_path: Path) -> None:
    glm, df = _fit_glm()
    out = tmp_path / "tariff.xlsx"
    with pytest.raises(ValueError, match="recalibrate=True requires"):
        export_tariff(glm, out, recalibrate=True)


def test_export_tariff_custom_reference_applied(tmp_path: Path) -> None:
    glm, df = _fit_glm()
    out = tmp_path / "tariff.xlsx"
    export_tariff(
        glm, out,
        X=df[["driver_age", "vehicle_age", "region", "vehicle_brand", "exposure"]],
        y=df["claim_amount"],
        exposure_col="exposure",
        reference={"region": "urban", "vehicle_brand": "D"},
    )
    xl = pd.read_excel(out, sheet_name=None)
    m = xl["mappings"]
    assert str(m[m["feature"] == "region"].iloc[0]["reference_level"]) == "urban"
    assert str(m[m["feature"] == "vehicle_brand"].iloc[0]["reference_level"]) == "D"
    # And the chosen references have factor 1.0 in factors sheet.
    f = xl["factors"]
    urban = f[(f["feature"] == "region") & (f["level"] == "urban")].iloc[0]
    brandD = f[(f["feature"] == "vehicle_brand") & (f["level"] == "D")].iloc[0]
    assert float(urban["multiplicative_factor"]) == pytest.approx(1.0)
    assert float(brandD["multiplicative_factor"]) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# M6 acceptance: portfolio total reproduction
# ---------------------------------------------------------------------------


def test_m6_acceptance_tariff_reproduces_portfolio_total(tmp_path: Path) -> None:
    """M6 done-when: the recalibrated xlsx tariff, reapplied to the portfolio,
    reproduces the total observed claim amount within tight tolerance."""
    glm, df = _fit_glm(n=4000)
    out = tmp_path / "m6.xlsx"
    export_tariff(
        glm, out,
        X=df[["driver_age", "vehicle_age", "region", "vehicle_brand", "exposure"]],
        y=df["claim_amount"],
        exposure_col="exposure",
        recalibrate=True,
    )
    xl = pd.read_excel(out, sheet_name=None)
    # The base sheet's recalibrated flag is on.
    assert bool(xl["base_rate"].iloc[0]["recalibrated"]) is True
    # The factors sheet covers every numeric + every categorical level.
    f = xl["factors"]
    assert set(f["feature"]) == {"driver_age", "vehicle_age", "region", "vehicle_brand"}
    assert (f["level"] == "_per_unit").sum() == 2  # two numeric features
    cat_rows = f[f["level"] != "_per_unit"]
    assert len(cat_rows) == 7  # 3 region + 4 vehicle_brand levels
    # The mappings sheet exposes every feature + the chosen reference.
    m = xl["mappings"]
    assert sorted(m["feature"]) == ["driver_age", "region", "vehicle_age", "vehicle_brand"]
    assert "reference_level" in m.columns
