"""Pure-premium model estimators: GLM (glum), GBM (LightGBM), freq x severity.

Special columns travel inside X per AGENTS.md rule 8 so pipelines, GridSearchCV
and cross_val_score keep working: pass ``exposure_col`` (and, for the
FrequencySeverityModel, ``claim_count_col`` / ``claim_amount_col``) to the
estimator and it pops those columns from X inside ``fit`` / ``predict``.

The ``exposure_col`` on a sub-estimator is really a *weight* column -- popped
from X and routed to the backend as ``sample_weight``. The pure-premium
convention (PRD section 5 rule 1): ``y = claim_amount / exposure`` and
``sample_weight = exposure``.

FrequencySeverityModel.fit applies the actuarial severity filter (claim_count
> 0, since Gamma needs y > 0) -- never in user code (rule 3).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from glum import GeneralizedLinearRegressor
from glum._distribution import TweedieDistribution
from lightgbm import LGBMRegressor
from sklearn.base import BaseEstimator, RegressorMixin, clone
from sklearn.metrics import d2_tweedie_score
from sklearn.utils.validation import check_is_fitted, validate_data

__all__ = ["RiskGLM", "RiskGBM", "FrequencySeverityModel"]


_GLM_POSITIVE_FAMILIES = {"poisson", "gamma", "tweedie"}
_GBM_POSITIVE_OBJECTIVES = {"poisson", "gamma", "tweedie"}
_GBM_OBJECTIVE_POWER = {"poisson": 1.0, "gamma": 2.0, "regression": 0.0, "rmse": 0.0}


def _pop_weight(X, exposure_col, sample_weight):
    """Return (X_features, weight_array_or_None).

    Drops ``exposure_col`` from a DataFrame ``X`` when it would otherwise leak
    as a feature. The popped column becomes ``sample_weight`` unless the caller
    passed an explicit ``sample_weight`` (used by FrequencySeverityModel to
    route ``claim_count`` as the severity weight).
    """
    if not isinstance(X, pd.DataFrame) or exposure_col is None or exposure_col not in X.columns:
        return X, sample_weight
    features = X.drop(columns=[exposure_col])
    if sample_weight is None:
        return features, X[exposure_col].to_numpy(dtype=float)
    return features, np.asarray(sample_weight, dtype=float)


def _store_fit_meta(estimator, X):
    """Set ``feature_names_in_`` and ``n_features_in_`` on the public estimator.

    DataFrame inputs are trusted as-is (glum/LightGBM accept categorical columns
    natively). ndarray inputs go through ``validate_data`` so sparse/complex
    payloads raise the message wording sklearn's estimator checks expect.
    """
    if isinstance(X, pd.DataFrame):
        estimator.feature_names_in_ = list(X.columns)
        estimator.n_features_in_ = X.shape[1]
    else:
        allow_nan = bool(estimator.__sklearn_tags__().input_tags.allow_nan)
        validate_data(estimator, X=X, ensure_all_finite=not allow_nan)


def _check_predict_meta(estimator, X):
    """At predict-time, enforce consistent n_features_in_ on ndarray input."""
    if not isinstance(X, pd.DataFrame):
        allow_nan = bool(estimator.__sklearn_tags__().input_tags.allow_nan)
        validate_data(estimator, X=X, reset=False, ensure_all_finite=not allow_nan)


def _categorize_strings(X):
    """Cast object-dtype DataFrame columns to ``category`` so glum and LightGBM
    route them through their native categorical encoding.

    ponytail: only touches ``object`` dtype -- ``category`` / numeric columns
    pass through unchanged.
    """
    if not isinstance(X, pd.DataFrame):
        return X
    obj_cols = [c for c in X.columns if pd.api.types.is_object_dtype(X[c])]
    if not obj_cols:
        return X
    out = X.copy()
    for c in obj_cols:
        out[c] = out[c].astype("category")
    return out


def _check_all_zero_weight(sample_weight):
    if (
        sample_weight is not None
        and np.asarray(sample_weight).size > 0
        and np.all(np.asarray(sample_weight) == 0)
    ):
        raise ValueError("All sample_weight entries are zero; cannot fit a weighted model.")


class RiskGLM(RegressorMixin, BaseEstimator):
    """Generalized linear model on top of ``glum.GeneralizedLinearRegressor``.

    Parameters
    ----------
    family : str
        Glum family name: ``"normal"``, ``"poisson"``, ``"gamma"``, ``"tweedie"``,
        ``"binomial"``, ``"inverse.gaussian"``, ``"negative.binomial"``. ``"tweedie"`
        defaults to power 1.5 unless ``tweedie_power`` is given.
    link : str
        Glum link: ``"auto"``, ``"log"``, ``"identity"``, ``"sqrt"``, ...
    exposure_col : str | None
        Column in X to pop and forward to glum as ``sample_weight`` (the
        exposure-weight pure-premium convention). Other special columns
        (e.g. ``claim_count`` / ``claim_amount``) are NOT auto-stripped -- drop
        them up-front (or wrap in a ``ColumnTransformer``) so they don't leak
        as features.
    tweedie_power : float | None
        Tweedie variance power (used only when ``family == "tweedie"``).
    alpha, l1_ratio : float
        Regularization strength and Elastic-Net mixing. Default ``0.001`` adds a
        vanishing ridge so glum stays well-conditioned on wide designs; pass
        ``alpha=0.0`` for an unpenalized MLE.
    fit_intercept : bool
    max_iter, gradient_tol : int | float | None
        Glum solver controls.
    random_state : int | None

    Attributes
    ----------
    backend_ : GeneralizedLinearRegressor
        The fitted glum estimator.
    coef_, intercept_ : np.ndarray | float
        Re-exposed from the backend for tarification (M6).
    feature_names_in_, n_features_in_
    """

    def __init__(
        self,
        family="normal",
        link="auto",
        exposure_col=None,
        tweedie_power=None,
        alpha=0.001,
        l1_ratio=0.0,
        fit_intercept=True,
        max_iter=100,
        gradient_tol=None,
        random_state=None,
    ):
        self.family = family
        self.link = link
        self.exposure_col = exposure_col
        self.tweedie_power = tweedie_power
        self.alpha = alpha
        self.l1_ratio = l1_ratio
        self.fit_intercept = fit_intercept
        self.max_iter = max_iter
        self.gradient_tol = gradient_tol
        self.random_state = random_state

    def __sklearn_tags__(self):
        tags = super().__sklearn_tags__()
        if self.family in _GLM_POSITIVE_FAMILIES:
            tags.target_tags.positive_only = True
            tags.regressor_tags.poor_score = True
        return tags

    def _make_backend(self):
        family = self.family
        if family == "tweedie" and self.tweedie_power is not None:
            family = TweedieDistribution(self.tweedie_power)
        return GeneralizedLinearRegressor(
            family=family,
            link=self.link,
            alpha=self.alpha,
            l1_ratio=self.l1_ratio,
            fit_intercept=self.fit_intercept,
            max_iter=self.max_iter,
            gradient_tol=self.gradient_tol,
            random_state=self.random_state,
        )

    def fit(self, X, y, sample_weight=None):
        _store_fit_meta(self, X)
        X_features, w = _pop_weight(X, self.exposure_col, sample_weight)
        _check_all_zero_weight(w)
        backend = self._make_backend()
        backend.fit(_categorize_strings(X_features), np.asarray(y, dtype=float), sample_weight=w)
        self.backend_ = backend
        self.coef_ = backend.coef_
        self.intercept_ = backend.intercept_
        self.n_iter_ = backend.n_iter_
        return self

    def predict(self, X):
        check_is_fitted(self, "backend_")
        _check_predict_meta(self, X)
        X_features, _ = _pop_weight(X, self.exposure_col, None)
        return self.backend_.predict(_categorize_strings(X_features))

    def score(self, X, y, sample_weight=None):
        check_is_fitted(self, "backend_")
        _check_predict_meta(self, X)
        X_features, w = _pop_weight(X, self.exposure_col, sample_weight)
        return self.backend_.score(
            _categorize_strings(X_features), np.asarray(y, dtype=float), sample_weight=w
        )


class RiskGBM(RegressorMixin, BaseEstimator):
    """Gradient boosted tree model on top of ``lightgbm.LGBMRegressor``.

    Parameters
    ----------
    objective : str
        LightGBM objective: ``"tweedie"`` (pure-premium default), ``"poisson"``,
        ``"gamma"``, ``"regression"``, ``"rmse"``, ...
    exposure_col : str | None
        Column in X popped and forwarded to LightGBM as ``sample_weight``.
    tweedie_variance_power : float
        Tweedie power; validated in ``__init__`` to lie in ``[1.0, 2.0)``
        (PRD rule 4) when ``objective == "tweedie"``.
    monotone_constraints : dict[str, int] | sequence[int] | None
        Per-feature monotonicity for LightGBM's tree splits. ``dict`` keys are
        feature names (resolved against ``X.columns`` at fit time, missing
        keys default to 0); ``sequence`` is interpreted in the order LightGBM
        sees the features. Values must be in ``{-1, 0, 1}`` (``1`` = increasing,
        ``-1`` = decreasing, ``0`` = unconstrained). ``None`` = no constraints.
        Dict shape is validated in ``__init__``; list shape and unknown dict
        keys are validated at fit time.
    num_leaves, max_depth, learning_rate, n_estimators, min_child_samples,
    subsample, subsample_freq, colsample_bytree, reg_alpha, reg_lambda,
    random_state, n_jobs, verbose
        Forwarded explicitly to LightGBM (no ``**kwargs``; LightGBM kwargs break
        ``get_params`` per AGENTS.md).

    Attributes
    ----------
    backend_ : LGBMRegressor
        The fitted LightGBM estimator.
    feature_names_in_, n_features_in_
    """

    def __init__(
        self,
        objective="tweedie",
        exposure_col=None,
        tweedie_variance_power=1.5,
        num_leaves=31,
        max_depth=-1,
        learning_rate=0.1,
        n_estimators=100,
        min_child_samples=20,
        subsample=1.0,
        subsample_freq=0,
        colsample_bytree=1.0,
        reg_alpha=0.0,
        reg_lambda=0.0,
        monotone_constraints=None,
        random_state=None,
        n_jobs=None,
        verbose=-1,
    ):
        # PRD rule 4: validate tweedie_variance_power "in __init__" when we can
        # safely. sklearn's check_do_not_raise_errors_in_init_or_set_params feeds
        # arbitrary non-scalar values to every parameter; we guard the guard so
        # hot-garbage payloads Fallon through to fit where _make_backend re-checks.
        if (
            isinstance(objective, str)
            and objective == "tweedie"
            and isinstance(tweedie_variance_power, (int, float))
            and not (1.0 <= tweedie_variance_power < 2.0)
        ):
            raise ValueError(
                f"tweedie_variance_power must be in [1.0, 2.0); got {tweedie_variance_power}"
            )
        if isinstance(monotone_constraints, dict):
            bad = {
                k: v for k, v in monotone_constraints.items() if v not in (-1, 0, 1)
            }
            if bad:
                raise ValueError(
                    f"monotone_constraints dict values must be in {{-1, 0, 1}}; got {bad}"
                )
        self.objective = objective
        self.exposure_col = exposure_col
        self.tweedie_variance_power = tweedie_variance_power
        self.num_leaves = num_leaves
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.n_estimators = n_estimators
        self.min_child_samples = min_child_samples
        self.subsample = subsample
        self.subsample_freq = subsample_freq
        self.colsample_bytree = colsample_bytree
        self.reg_alpha = reg_alpha
        self.reg_lambda = reg_lambda
        self.monotone_constraints = monotone_constraints
        self.random_state = random_state
        self.n_jobs = n_jobs
        self.verbose = verbose

    def __sklearn_tags__(self):
        tags = super().__sklearn_tags__()
        tags.input_tags.allow_nan = True  # LightGBM handles NaN natively.
        if self.objective in _GBM_POSITIVE_OBJECTIVES:
            tags.target_tags.positive_only = True
            tags.regressor_tags.poor_score = True
        return tags

    def _make_backend(self, *, pre_pop_names=None, post_pop_names=None):
        if self.objective == "tweedie" and not (1.0 <= self.tweedie_variance_power < 2.0):
            raise ValueError(
                f"tweedie_variance_power must be in [1.0, 2.0); got {self.tweedie_variance_power}"
            )
        return LGBMRegressor(
            objective=self.objective,
            tweedie_variance_power=self.tweedie_variance_power,
            num_leaves=self.num_leaves,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            n_estimators=self.n_estimators,
            min_child_samples=self.min_child_samples,
            subsample=self.subsample,
            subsample_freq=self.subsample_freq,
            colsample_bytree=self.colsample_bytree,
            reg_alpha=self.reg_alpha,
            reg_lambda=self.reg_lambda,
            monotone_constraints=self._resolve_monotone_constraints(
                pre_pop_names=pre_pop_names, post_pop_names=post_pop_names
            ),
            random_state=self.random_state,
            n_jobs=self.n_jobs,
            verbose=self.verbose,
        )

    def _resolve_monotone_constraints(self, *, pre_pop_names, post_pop_names):
        """Translate ``monotone_constraints`` into a list aligned with the
        feature matrix LightGBM sees (``post_pop_names`` -- ``exposure_col``
        is popped and routed as ``sample_weight`` before the backend fits).
        """
        mc = self.monotone_constraints
        if mc is None:
            return None
        if isinstance(mc, dict):
            if pre_pop_names is None:
                raise ValueError(
                    "monotone_constraints as a dict requires a DataFrame X with column names."
                )
            unknown = sorted(set(mc.keys()) - set(pre_pop_names))
            if unknown:
                raise ValueError(
                    f"monotone_constraints references unknown columns: {unknown}"
                )
            return [int(mc.get(name, 0)) for name in post_pop_names]
        try:
            arr = np.asarray(mc, dtype=int)
        except (TypeError, ValueError) as e:
            raise ValueError(
                "monotone_constraints must be a dict or a sequence of int in "
                f"{{-1, 0, 1}}; got {mc!r}"
            ) from e
        if not np.all(np.isin(arr, [-1, 0, 1])):
            raise ValueError(
                f"monotone_constraints values must be in {{-1, 0, 1}}; got {arr.tolist()}"
            )
        if pre_pop_names is not None and self.exposure_col in pre_pop_names:
            arr = np.delete(arr, pre_pop_names.index(self.exposure_col))
        return arr.tolist()

    def fit(self, X, y, sample_weight=None):
        _store_fit_meta(self, X)
        X_features, w = _pop_weight(X, self.exposure_col, sample_weight)
        _check_all_zero_weight(w)
        pre_pop_names = list(X.columns) if isinstance(X, pd.DataFrame) else None
        post_pop_names = (
            list(X_features.columns) if isinstance(X_features, pd.DataFrame) else None
        )
        backend = self._make_backend(
            pre_pop_names=pre_pop_names, post_pop_names=post_pop_names
        )
        backend.fit(_categorize_strings(X_features), np.asarray(y, dtype=float), sample_weight=w)
        self.backend_ = backend
        self.n_iter_ = self.n_estimators
        return self

    def predict(self, X):
        check_is_fitted(self, "backend_")
        _check_predict_meta(self, X)
        X_features, _ = _pop_weight(X, self.exposure_col, None)
        return self.backend_.predict(_categorize_strings(X_features))

    def _objective_power(self):
        if self.objective == "tweedie":
            return self.tweedie_variance_power
        return _GBM_OBJECTIVE_POWER.get(self.objective, self.tweedie_variance_power)

    def score(self, X, y, sample_weight=None):
        check_is_fitted(self, "backend_")
        _check_predict_meta(self, X)
        X_features, w = _pop_weight(X, self.exposure_col, sample_weight)
        y = np.asarray(y, dtype=float)
        y_pred = self.backend_.predict(_categorize_strings(X_features))
        return d2_tweedie_score(y, y_pred, power=self._objective_power(), sample_weight=w)


class FrequencySeverityModel(RegressorMixin, BaseEstimator):
    """Frequency x severity pure-premium meta-estimator.

    Fits ``freq`` on per-row claim frequency (``claim_count / exposure``,
    sample_weight ``exposure``) and ``sev`` on per-claim severity
    (``claim_amount / claim_count``, sample_weight ``claim_count``) using only
    rows where ``claim_count > 0`` (Gamma needs y > 0). The filter lives here
    per AGENTS.md rule 3, never in user code.

    Sub-estimators are duck-typed: anything exposing
    ``fit(X, y, sample_weight=...)`` and ``predict(X)`` works -- ``RiskGLM``,
    ``RiskGBM``, sklearn's own GLM estimators, etc.

    Parameters
    ----------
    freq, sev : estimator
        Sub-estimators for frequency and severity. Required.
    exposure_col, claim_count_col, claim_amount_col : str
        Names of the special columns inside X.

    Attributes
    ----------
    freq_, sev_ : fitted sub-estimators (clones of ``freq`` / ``sev``)
    n_features_in_, feature_names_in_
    """

    def __init__(
        self,
        freq=None,
        sev=None,
        exposure_col="exposure",
        claim_count_col="claim_count",
        claim_amount_col="claim_amount",
    ):
        self.freq = freq
        self.sev = sev
        self.exposure_col = exposure_col
        self.claim_count_col = claim_count_col
        self.claim_amount_col = claim_amount_col

    def __sklearn_tags__(self):
        tags = super().__sklearn_tags__()
        tags.target_tags.positive_only = True
        tags.regressor_tags.poor_score = True
        tags.input_tags.allow_nan = True
        tags.input_tags.string = True
        return tags

    def _strip_specials(self, X):
        if not isinstance(X, pd.DataFrame):
            return X
        specials = (self.exposure_col, self.claim_count_col, self.claim_amount_col)
        drop = [c for c in specials if c in X.columns]
        return X.drop(columns=drop)

    def _require_specials(self, X):
        if not isinstance(X, pd.DataFrame):
            raise TypeError("FrequencySeverityModel requires a pandas DataFrame X (special cols).")
        missing = [
            c
            for c in (self.exposure_col, self.claim_count_col, self.claim_amount_col)
            if c not in X.columns
        ]
        if missing:
            raise ValueError(f"FrequencySeverityModel.fit: missing special columns: {missing}")

    def fit(self, X, y=None):
        if self.freq is None or self.sev is None:
            raise ValueError("FrequencySeverityModel requires both `freq` and `sev`.")
        self._require_specials(X)
        _store_fit_meta(self, X)

        exposure = X[self.exposure_col].to_numpy(dtype=float)
        cc = X[self.claim_count_col].to_numpy(dtype=float)
        ca = X[self.claim_amount_col].to_numpy(dtype=float)
        X_features = self._strip_specials(X)

        with np.errstate(divide="ignore", invalid="ignore"):
            y_freq = np.where(exposure > 0, cc / exposure, 0.0)

        pos = cc > 0
        y_sev = ca[pos] / cc[pos] if pos.any() else np.zeros(0)

        self.freq_ = clone(self.freq)
        self.freq_.fit(X_features, y_freq, sample_weight=exposure)

        self.sev_ = clone(self.sev)
        self.sev_positive_rows_ = int(pos.sum())
        if self.sev_positive_rows_ > 0:
            self.sev_.fit(X_features[pos], y_sev, sample_weight=cc[pos])
        return self

    def predict(self, X):
        check_is_fitted(self, "freq_")
        X_features = self._strip_specials(X) if isinstance(X, pd.DataFrame) else X
        freq_pred = np.maximum(self.freq_.predict(X_features), 0.0)
        if self.sev_positive_rows_ > 0:
            sev_pred = np.maximum(self.sev_.predict(X_features), 0.0)
            return freq_pred * sev_pred
        return np.zeros_like(freq_pred)

    def score(self, X, y, sample_weight=None):
        """D^2 (Tweedie, p=1.5) of predicted claim_amount vs observed.

        ``y`` is claim_amount (aggregate per row); exposition from PRD section 5.
        """
        check_is_fitted(self, "freq_")
        if not isinstance(X, pd.DataFrame):
            raise TypeError("FrequencySeverityModel.score requires a pandas DataFrame X.")
        exposure = X[self.exposure_col].to_numpy(dtype=float)
        y = np.asarray(y, dtype=float)
        if sample_weight is None:
            sample_weight = exposure
        y_pred = self.predict(X) * exposure
        return d2_tweedie_score(y, y_pred, power=1.5, sample_weight=sample_weight)
