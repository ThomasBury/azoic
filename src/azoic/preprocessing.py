"""Auto-binning and auto-grouping transformers for tariff preprocessing.

AutoBinner: numeric columns -> actuarially-credible interval bins
    ("tree" weighted LightGBM leaves, or "quantile" equal-exposure edges).
AutoGrouper: categorical columns -> credibility-stable level groups
    ("similarity" native LightGBM groups, or "rare" floor-based).

Both follow the scikit-learn transformer API and survive
`sklearn.utils.estimator_checks.parametrize_with_checks`. Special columns
(exposure, claim_count, target) travel inside X per AGENTS.md rule 8.
`mapping_` is overridable via `set_mapping`; `transform` honours the override.
"""

from __future__ import annotations

import warnings
from collections.abc import Hashable, Mapping, Sequence
from numbers import Integral, Real
from typing import Any, Self, overload

import lightgbm as lgb
import numpy as np
import pandas as pd
from numpy.typing import ArrayLike
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.isotonic import isotonic_regression
from sklearn.utils.validation import (
    check_array,
    check_consistent_length,
    check_is_fitted,
    validate_data,
)

from azoic.data import EXPOSURE_FLOOR, MIN_EXPOSURE
from azoic.validation import _weighted_quantile_edges

__all__ = ["AutoBinner", "AutoGrouper"]


def _fixed_specs(fixed, cols):
    if fixed is None:
        return {}
    if not isinstance(fixed, Mapping) or set(fixed) - set(cols):
        raise ValueError("fixed mappings must name selected transformer columns")
    if any(not isinstance(spec, Mapping) for spec in fixed.values()):
        raise ValueError("each fixed feature must contain a mapping specification")
    return fixed


def _fixed_level(value):
    if type(value) not in (str, int, float, bool) or (
        isinstance(value, float) and not np.isfinite(value)
    ):
        raise ValueError(
            "fixed levels and destinations must be finite scalar strings/numbers/bools"
        )
    return value


def _check_min_exposure(min_exposure, exp) -> None:
    """``min_exposure`` is an exposure-unit floor: below one day (1/366) is
    meaningless, and without a real exposure column it silently becomes a
    row-count floor."""
    if min_exposure is None:
        return
    if (
        not isinstance(min_exposure, Real)
        or isinstance(min_exposure, bool)
        or not np.isfinite(min_exposure)
        or min_exposure < MIN_EXPOSURE
    ):
        raise ValueError(f"min_exposure must be at least 1/366 (one day); got {min_exposure}")
    if exp is None:
        raise ValueError("min_exposure requires exposure_col in X")


def _to_frame(X, *, required_columns=()):
    """Return (DataFrame, was_dataframe). Names: real or f'x{i}' for ndarray.

    ``np.asarray`` unwraps sklearn's ``_NotAnArray`` and ``list`` payloads.
    """
    was_df = isinstance(X, pd.DataFrame)
    if was_df:
        frame = X
    else:
        arr = np.asarray(X)
        frame = pd.DataFrame(arr, columns=pd.Index([f"x{i}" for i in range(arr.shape[1])]))
    missing = [col for col in required_columns if col not in frame.columns]
    if missing:
        raise ValueError(
            f"transform input is missing fitted mapping columns: {missing}; "
            "use the same column names as during fit (arrays use x0, x1, ...)"
        )
    return frame, was_df


def _validate_transform_input(estimator, X):
    check_is_fitted(estimator, "mapping_")
    names = getattr(estimator, "feature_names_in_", None)
    specials = {
        c for c in (estimator.exposure_col, estimator.claim_count_col, estimator.target_col) if c
    }
    if isinstance(X, pd.DataFrame) and names is not None:
        expected = [name for name in names if name not in specials or name in X.columns]
        if len(expected) != len(names):
            if list(X.columns) != expected:
                raise ValueError(f"Transform predictors must match fit names and order: {expected}")
            check_array(X, dtype=None, ensure_all_finite=False)
            return
    validate_data(estimator, X, reset=False, dtype=None, ensure_all_finite=False)


def _column_array(X, name, *, required=False, minimum=0):
    if name and name in X.columns:
        values = X[name].to_numpy(dtype=float)
        if required:
            values = check_array(values, dtype=float, ensure_2d=False, input_name=name)
            if values.ndim != 1:
                raise ValueError(f"column {name!r} must be one-dimensional")
            if np.any(values < minimum):
                bound = "at least 1/366 (one day)" if minimum == EXPOSURE_FLOOR else "non-negative"
                raise ValueError(f"column {name!r} must contain only {bound} values")
        return values
    if name is not None and required:
        raise ValueError(f"configured column {name!r} not found in X")
    return None


def _resolve_target(X, y, target_col, exposure):
    target = _column_array(X, target_col)
    if target is not None and exposure is not None:
        target = target / exposure
    elif target is None:
        target = y
    if target is None:
        return None
    target = check_array(target, dtype=float, ensure_2d=False, input_name="target")
    if target.ndim != 1:
        raise ValueError("target must be one-dimensional")
    check_consistent_length(X, target)
    return target


def _check_controls(estimator, exp, cc):
    _check_min_exposure(estimator.min_exposure, exp)
    if estimator.min_claims is not None:
        if (
            not isinstance(estimator.min_claims, Real)
            or isinstance(estimator.min_claims, bool)
            or not np.isfinite(estimator.min_claims)
            or estimator.min_claims < 0
        ):
            raise ValueError("min_claims must be finite and non-negative")
        if cc is None:
            raise ValueError("min_claims requires claim_count_col in X")


def _feature_names(estimator, input_features):
    check_is_fitted(estimator, "n_features_in_")
    names = getattr(
        estimator,
        "feature_names_in_",
        np.asarray([f"x{i}" for i in range(estimator.n_features_in_)]),
    )
    if input_features is not None and not np.array_equal(input_features, names):
        raise ValueError("input_features must match fitted feature names")
    return names


def _leaf_predictions(tree, values):
    return np.asarray(tree.predict(values.reshape(-1, 1), pred_leaf=True, num_threads=1)).ravel()


def _fit_tree(
    values, target, exp, cc, limit, min_exposure, min_claims, *, categorical=False, seed=42
):
    """One weighted regression tree, with sibling subtrees pooled for both floors.

    Inspired by ARFS TreeDiscretizer's univariate regression core; all rows stay
    inside the caller's training boundary. Counts constrain groups, never weights.
    """
    weights = np.ones(len(values)) if exp is None else exp
    target = check_array(target, dtype=np.float32, ensure_2d=False, input_name="target")
    check_array(weights, dtype=np.float32, ensure_2d=False, input_name="exposure")
    tree = lgb.train(
        {
            "objective": "regression",
            "num_leaves": max(2, int(limit)),
            # LightGBM's Hessian-based row estimate can reject low-exposure leaves.
            "min_data_in_leaf": 0,
            "min_sum_hessian_in_leaf": 1e-3 if min_exposure is None else min_exposure,
            "min_data_in_bin": 1,
            "min_data_per_group": 1,
            "max_cat_to_onehot": 1,
            "cat_smooth": 0,
            "cat_l2": 10,
            "verbosity": -1,
            "num_threads": 1,
            "seed": seed,
        },
        lgb.Dataset(
            values.reshape(-1, 1),
            label=target,
            weight=weights,
            categorical_feature=[0] if categorical else [],
        ),
        num_boost_round=1,
    )
    leaves = _leaf_predictions(tree, values).astype(int)
    model = tree.dump_model()["tree_info"][0]
    n_leaves = model["num_leaves"]
    exposure = np.bincount(leaves, weights=weights, minlength=n_leaves)
    claims = np.bincount(leaves, weights=cc, minlength=n_leaves) if cc is not None else None

    def credible(group):
        return (min_exposure is None or exposure[group].sum() >= min_exposure) and (
            min_claims is None or (claims is not None and claims[group].sum() >= min_claims)
        )

    def prune(node):
        if "split_index" not in node:
            return [[node.get("leaf_index", 0)]], []
        left, left_edges = prune(node["left_child"])
        right, right_edges = prune(node["right_child"])
        groups = left + right
        if limit == 1 or not all(credible(group) for group in groups):
            return [[leaf for group in groups for leaf in group]], []
        return groups, left_edges + [node["threshold"]] + right_edges

    groups, edges = prune(model["tree_structure"])
    leaf_groups = {leaf: i for i, group in enumerate(groups) for leaf in group}
    return tree, leaf_groups, edges


def _merge_small_bins(values, weights, edges, min_weight):
    """Iteratively merge bins below the weight floor into an adjacent bin."""
    if min_weight is None or len(edges) == 0:
        return edges
    total = float(weights.sum())
    if total < min_weight:
        return np.array([])  # impossible to satisfy any floor; single bin
    edges = list(edges)
    codes = np.searchsorted(np.asarray(edges), values, side="right")
    bin_weights = np.bincount(codes, weights=weights, minlength=len(edges) + 1).tolist()
    while edges:
        small = next((i for i, weight in enumerate(bin_weights) if weight < min_weight), None)
        if small is None:
            break
        if small == 0:
            edges.pop(0)
            bin_weights[0] += bin_weights.pop(1)
        elif small >= len(edges):
            edges.pop(-1)
            last_weight = bin_weights.pop()
            bin_weights[-1] += last_weight
        else:
            edges.pop(small)
            bin_weights[small] += bin_weights.pop(small + 1)
    return np.array(edges, dtype=float)


class AutoBinner(TransformerMixin, BaseEstimator):
    """Bin numeric columns into actuarially-credible tariff bins.

    Binned columns become ordered interval categoricals (DataFrame input) or
    integer bin codes (ndarray input). Non-target columns pass through
    unchanged. Learned tree edges include their upper boundary (``<=``);
    quantile and manual edges include their lower boundary. Tree NaNs follow
    the fitted missing route; quantile NaNs use a reserved ``"Missing"`` bin.
    Transform input must contain every fitted mapping column; arrays use
    ``x0``, ``x1``, etc. Unmatched column names raise ``ValueError``.

    Parameters
    ----------
    cols : list[str] | None
        Columns to bin. None -> all numeric columns found in fit.
    strategy : {"tree", "quantile"}, default="tree"
        "tree" = one exposure-weighted LightGBM regression tree on rates.
        Requires a target. "quantile" = weighted equal-frequency edges.
    max_bins : int
        Maximum number of bins per column (>=1).
    min_exposure : float | None
        Minimum total exposure per group. Tree sibling subtrees collapse below
        either floor; quantile bins merge with neighbours.
        Requires a real ``exposure_col`` column and must be >= 1/366 (one
        day); raises otherwise (a count-unit fallback would change units).
    min_claims : float | None
        Minimum aggregate claim count per bin; smaller bins merge into neighbours.
    exposure_col, claim_count_col, target_col : str | None
        Configured exposure and claim-count columns must exist at fit and
        contain finite values; exposures must be at least one day (1/366,
        with day-count tolerance), and claim counts must be non-negative.
        Without ``exposure_col``, binning is unweighted. For tree binning, the target is
        ``target_col / exposure_col`` (pure premium) when both are set, else
        ``target_col``, else ``y``. Supplied outcomes must be finite after
        numeric and unit conversion; missing outcomes are never treated as zero.
    monotonic : False | True | "increasing" | "decreasing"
        When set, bin means are smoothed to be monotonic in the target via
        ``isotonic_regression`` and adjacent bins with the same smoothed mean
        merge. No-op without a target. False = off, True / "increasing" =
        non-decreasing bin means, "decreasing" = non-increasing. Native tree
        means include missing rows in their routed group. Pooling preserves floors.
    random_state : int | None
        Tree strategy seed, a non-negative 32-bit integer or None.
    fixed : mapping | None
        Per-feature ``{edges: [...], closure: 'left'|'right', missing: bin_index}``.
        Fixed features do not learn edges or enforce learned credibility floors.
        Use an existing bin index or len(edges) + 1 for a separate Missing bin.
        Other selected features learn normally.

    Attributes
    ----------
    mapping_ : dict[str, np.ndarray]
        Bin edges per binned column (length n_bins - 1).
    category_dtypes_ : dict[str, pd.CategoricalDtype]
        Stable ordered output vocabularies for DataFrame inputs.
    missing_ : dict[str, int]
        Fitted missing destination, as a zero-based bin index.
    closure_ : dict[str, str]
        "right" for native trees, "left" for quantile/manual edges.
    bin_cols_ : list[str]
    n_features_in_ : int
    feature_names_in_ : list[str] | None
    """

    mapping_: dict[str, np.ndarray]
    missing_: dict[str, int]
    category_dtypes_: dict[str, pd.CategoricalDtype]
    feature_names_in_: np.ndarray
    n_features_in_: int

    def __init__(
        self,
        cols: Sequence[str] | None = None,
        strategy: str = "tree",
        max_bins: int = 8,
        min_exposure: float | None = None,
        min_claims: float | None = None,
        exposure_col: str | None = None,
        claim_count_col: str | None = None,
        target_col: str | None = None,
        monotonic: bool | str = False,
        random_state: int | None = 42,
        fixed: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        self.cols = cols
        self.strategy = strategy
        self.max_bins = max_bins
        self.min_exposure = min_exposure
        self.min_claims = min_claims
        self.exposure_col = exposure_col
        self.claim_count_col = claim_count_col
        self.target_col = target_col
        self.monotonic = monotonic
        self.random_state = random_state
        self.fixed = fixed

    def __sklearn_tags__(self):
        tags = super().__sklearn_tags__()
        tags.input_tags.allow_nan = True
        tags.input_tags.string = True
        return tags

    def fit(self, X: pd.DataFrame | ArrayLike, y: ArrayLike | None = None) -> Self:
        if self.strategy not in ("quantile", "tree"):
            raise ValueError(f"strategy must be 'quantile' or 'tree'; got {self.strategy!r}")
        if (
            not isinstance(self.max_bins, Integral)
            or isinstance(self.max_bins, bool)
            or self.max_bins < 1
        ):
            raise ValueError(f"max_bins must be an integer at least 1; got {self.max_bins!r}")
        self._mono_direction()
        if self.random_state is not None and (
            not isinstance(self.random_state, Integral)
            or isinstance(self.random_state, bool)
            or not 0 <= self.random_state <= np.iinfo(np.int32).max
        ):
            raise ValueError("random_state must be None or a non-negative 32-bit integer")
        validate_data(self, X, dtype=None, ensure_all_finite=False)
        X_df, _ = _to_frame(X)
        cols = self._select_cols(X_df)
        fixed = _fixed_specs(self.fixed, cols)
        exp = _column_array(X_df, self.exposure_col, required=True, minimum=EXPOSURE_FLOOR)
        cc = _column_array(X_df, self.claim_count_col, required=True)
        _check_controls(self, exp, cc)
        target = _resolve_target(X_df, y, self.target_col, exp)
        if self.strategy == "tree" and target is None and set(cols) - set(fixed):
            raise ValueError("tree binning requires a target (target_col in X or y)")
        self.mapping_ = {}
        self.trees_ = {}
        self.leaf_groups_ = {}
        self.missing_ = {}
        self.closure_ = {}
        self.tree_mappings_ = {}
        for col in cols:
            values = self._column_values(X_df, col)
            if col in fixed:
                spec = fixed[col]
                if set(spec) != {"edges", "closure", "missing"}:
                    raise ValueError("fixed bins require exactly edges, closure and missing")
                edges = check_array(
                    spec["edges"], dtype=float, ensure_2d=False, ensure_min_samples=0, copy=True
                )
                if edges.ndim != 1 or np.any(np.diff(edges) <= 0):
                    raise ValueError("fixed bin edges must be a strictly increasing finite vector")
                route = spec["missing"]
                if (
                    isinstance(route, bool)
                    or not isinstance(route, Integral)
                    or not 0 <= route <= len(edges) + 1
                ):
                    raise ValueError(
                        "fixed missing destination must be a bin index or the Missing bin"
                    )
                if spec["closure"] not in ("left", "right"):
                    raise ValueError("fixed bin closure must be 'left' or 'right'")
                self.mapping_[col] = edges
                self.missing_[col] = int(route)
                self.closure_[col] = spec["closure"]
                continue
            if self.strategy == "tree":
                tree, groups, thresholds = _fit_tree(
                    values,
                    target,
                    exp,
                    cc,
                    self.max_bins,
                    self.min_exposure,
                    self.min_claims,
                    seed=self.random_state,
                )
                edges = np.asarray(thresholds, dtype=float)
                if self._mono_direction() is not None and len(edges):
                    codes = np.array([groups[leaf] for leaf in _leaf_predictions(tree, values)])
                    w = np.ones(len(values)) if exp is None else exp
                    sums = np.bincount(codes, weights=w, minlength=len(edges) + 1)
                    means = np.bincount(codes, weights=w * target) / sums
                    smoothed = isotonic_regression(
                        means, increasing=self._mono_direction(), sample_weight=sums
                    )
                    keep = smoothed[:-1] != smoothed[1:]
                    pooled = np.r_[0, np.cumsum(keep)]
                    groups = {leaf: int(pooled[group]) for leaf, group in groups.items()}
                    edges = edges[keep]
                self.trees_[col] = tree
                self.leaf_groups_[col] = groups
                self.missing_[col] = groups[_leaf_predictions(tree, np.array([np.nan]))[0]]
                self.closure_[col] = "right"
                self.tree_mappings_[col] = edges.copy()
            else:
                edges = self._edges(values, target, exp, cc)
                self.missing_[col] = len(edges) + 1
                self.closure_[col] = "left"
            self.mapping_[col] = edges
        self.category_dtypes_ = {
            col: self._category_dtype(
                edges,
                closure=self.closure_[col],
                missing=col not in self.trees_ and self.missing_[col] > len(edges),
            )
            for col, edges in self.mapping_.items()
        }
        self.bin_cols_ = cols
        return self

    def _select_cols(self, X):
        specials = {c for c in (self.exposure_col, self.claim_count_col, self.target_col) if c}
        if self.cols is not None:
            invalid = sorted(set(self.cols) & specials)
            if invalid:
                raise ValueError(f"cols contains special columns: {invalid}")
            missing = sorted(set(self.cols) - set(X.columns))
            if missing:
                raise ValueError(f"cols not found in X: {missing}")
            return list(self.cols)
        return [
            c
            for c in X.columns
            if c not in specials
            and pd.api.types.is_numeric_dtype(X[c])
            and not pd.api.types.is_bool_dtype(X[c])
        ]

    def _edges(self, values, target, exp, cc):
        mask = ~np.isnan(values)
        v = values[mask]
        if len(v) == 0:
            return np.array([])
        w = exp[mask] if exp is not None else None
        edges = self._quantile_edges(v, w)
        if target is not None and self._mono_direction() is not None:
            t = target[mask]
            edges = self._enforce_monotonic(edges, v, w, t)
        edges = _merge_small_bins(v, w, edges, self.min_exposure)
        return _merge_small_bins(v, cc[mask] if cc is not None else None, edges, self.min_claims)

    def _mono_direction(self):
        """True=increasing, False=decreasing, None=off; raise on garbage."""
        m = self.monotonic
        if m is False or m is None:
            return None
        if m is True or (isinstance(m, str) and m == "increasing"):
            return True
        if isinstance(m, str) and m == "decreasing":
            return False
        raise ValueError(f"monotonic must be False, True, 'increasing', or 'decreasing'; got {m!r}")

    def _enforce_monotonic(self, edges, values, weights, target):
        """Smooth bin means with isotonic regression and merge equal-adjacent.

        Adjacent bins whose isotonic-smoothed mean matches collapse; the
        surviving edges form a strictly monotonic binning. Exposure-weighted
        when ``weights`` is given.
        """
        if len(edges) == 0:
            return edges
        codes = np.searchsorted(edges, values, side="right")
        n_bins = len(edges) + 1
        w = weights if weights is not None else np.ones_like(values)
        tgt_sum = np.bincount(codes, weights=target * w, minlength=n_bins)
        w_sum = np.bincount(codes, weights=w, minlength=n_bins)
        occupied = np.flatnonzero(w_sum > 0)
        bin_means = tgt_sum[occupied] / w_sum[occupied]
        increasing = self._mono_direction()
        smoothed = isotonic_regression(
            bin_means, increasing=increasing, sample_weight=w_sum[occupied]
        )
        keep = occupied[:-1][smoothed[:-1] != smoothed[1:]]
        return edges[keep]

    def _quantile_edges(self, v, w):
        if w is None:
            edges = np.unique(np.quantile(v, np.linspace(0, 1, self.max_bins + 1)[1:-1]))
        else:
            edges = _weighted_quantile_edges(v, w, n_quantiles=self.max_bins)
        return edges[edges > v.min()]

    @overload
    def transform(self, X: pd.DataFrame) -> pd.DataFrame: ...

    @overload
    def transform(self, X: ArrayLike) -> np.ndarray: ...

    def transform(self, X: pd.DataFrame | ArrayLike) -> pd.DataFrame | np.ndarray:
        _validate_transform_input(self, X)
        X_df, was_df = _to_frame(X, required_columns=self.mapping_)
        out = X_df.copy()
        for col, edges in self.mapping_.items():
            values = self._column_values(out, col)
            if col in self.trees_:
                leaves = _leaf_predictions(self.trees_[col], values)
                codes = np.array([self.leaf_groups_[col][leaf] for leaf in leaves])
            else:
                side = "left" if self.closure_[col] == "right" else "right"
                codes = np.searchsorted(edges, values, side=side)
                codes[np.isnan(values)] = self.missing_[col]
            if was_df:
                out[col] = pd.Categorical.from_codes(codes, dtype=self.category_dtypes_[col])
            else:
                out[col] = codes.astype(float)
        return out if was_df else out.to_numpy()

    @staticmethod
    def _column_values(X: pd.DataFrame, col: str) -> np.ndarray:
        values = X[col].to_numpy(dtype=float)
        if np.isinf(values).any():
            raise ValueError(
                f"column {col!r} contains infinite values; binned columns must be finite or NaN"
            )
        return values

    @staticmethod
    def _codes(values, edges):
        codes = np.searchsorted(edges, values, side="right")
        codes = np.where(np.isnan(values), len(edges) + 1, codes)
        return codes.astype(int)

    @staticmethod
    def _labels(codes, edges, *, closure="left"):
        n = len(edges)
        edge_labels = [f"{edge:g}" for edge in edges]
        # Keep distinct fitted boundaries distinguishable when display rounding collides.
        if len(set(edge_labels)) < n:
            edge_labels = [repr(float(edge)) for edge in edges]
        labels = np.empty(len(codes), dtype=object)
        lower, upper = ("(", "]") if closure == "right" else ("[", ")")
        for i, c in enumerate(codes):
            if c > n:
                labels[i] = "Missing"
            elif n == 0:
                labels[i] = "(-inf, inf)"
            elif c == 0:
                labels[i] = f"(-inf, {edge_labels[0]}{upper}"
            elif c >= n:
                labels[i] = f"{lower}{edge_labels[-1]}, inf)"
            else:
                labels[i] = f"{lower}{edge_labels[c - 1]}, {edge_labels[c]}{upper}"
        return labels

    @staticmethod
    def _category_dtype(edges, *, closure="left", missing=True):
        categories = AutoBinner._labels(
            np.arange(len(edges) + 1 + int(missing)), edges, closure=closure
        ).tolist()
        return pd.CategoricalDtype(categories, ordered=True)

    def get_feature_names_out(
        self, input_features: Sequence[str] | np.ndarray | None = None
    ) -> np.ndarray:
        return _feature_names(self, input_features)

    def set_mapping(
        self, mapping: Mapping[str, ArrayLike], *, missing: Mapping[str, int] | None = None
    ) -> None:
        """Replace fitted bin mappings with finite, strictly increasing edge vectors.

        Keys must name currently binned columns. Omitted columns pass through.
        Changed tree mappings require ``missing={column: bin_index}``. An
        unchanged round-trip preserves native routing; manual edges are lower-
        inclusive. Manual decisions replace learned floor/monotonic guarantees.
        Invalid overrides leave the fitted mappings and vocabularies intact.
        """
        check_is_fitted(self, "mapping_")
        unknown = set(mapping) - set(self.bin_cols_)
        if unknown:
            raise ValueError(f"mapping columns were not binned: {sorted(unknown)}")
        replacement = {}
        for col, edges in mapping.items():
            edges = check_array(
                edges, dtype=float, ensure_2d=False, ensure_min_samples=0, copy=True
            )
            if edges.ndim != 1 or np.any(np.diff(edges) <= 0):
                raise ValueError(
                    f"bin edges for {col!r} must be one-dimensional and strictly increasing"
                )
            replacement[col] = edges
        missing = {} if missing is None else dict(missing)
        if set(missing) - set(replacement):
            raise ValueError("missing destinations must name mapping columns")
        trees, leaf_groups, routes, closures, dtypes = {}, {}, {}, {}, {}
        for col, edges in replacement.items():
            unchanged = np.array_equal(edges, self.tree_mappings_.get(col, self.mapping_[col]))
            if col in self.trees_ and unchanged and col not in missing:
                trees[col] = self.trees_[col]
                leaf_groups[col] = self.leaf_groups_[col]
                routes[col] = self.missing_[col]
                closures[col] = self.closure_[col]
                dtypes[col] = self.category_dtypes_[col]
                continue
            if col not in self.trees_ and unchanged and col not in missing:
                routes[col] = self.missing_[col]
                closures[col] = self.closure_[col]
                dtypes[col] = self.category_dtypes_[col]
                continue
            if col in self.trees_ and col not in missing:
                raise ValueError(
                    f"changed tree mapping for {col!r} requires an explicit missing destination"
                )
            route = missing.get(col, len(edges) + 1)
            if (
                not isinstance(route, Integral)
                or isinstance(route, bool)
                or not 0 <= route <= len(edges) + int(col not in missing)
            ):
                raise ValueError(f"invalid missing bin index for {col!r}")
            routes[col] = route
            closures[col] = "left"
            dtypes[col] = self._category_dtype(edges, missing=col not in missing)
        self.mapping_ = replacement
        self.category_dtypes_ = dtypes
        self.trees_, self.leaf_groups_ = trees, leaf_groups
        self.missing_, self.closure_ = routes, closures
        self.tree_mappings_ = {col: self.tree_mappings_[col] for col in trees}
        self.bin_cols_ = list(mapping.keys())


class AutoGrouper(TransformerMixin, BaseEstimator):
    """Group categorical levels into credibility-stable groups.

    Strategies
    ----------
    "rare"        Levels below ``min_exposure`` / ``min_claims`` -> ``other_label``.
                  ``min_exposure`` requires a real ``exposure_col`` column and
                  must be >= 1/366 (one day).
    "similarity"  One exposure-weighted LightGBM regression tree on rates.
                  Nominal levels use native categorical splits, ordered levels
                  use numeric codes to preserve contiguous groups. Sibling
                  subtrees collapse when either credibility floor fails.
                  If portfolio floors are impossible, one group remains.

    ``mapping_`` is ``{col: {original_level: group_label}}``. Tree missing and
    unseen levels follow the fitted missing route; unseen levels warn. The rare
    strategy uses ``other_label``. Output vocabularies are frozen during fit.
    Transform input must contain every fitted mapping column; arrays use
    ``x0``, ``x1``, etc. Unmatched column names raise ``ValueError``.

    Configured exposure and claim-count columns must exist at fit and contain
    finite values; exposures must be at least one day (1/366, with day-count
    tolerance), and claim counts must be non-negative. Without ``exposure_col``,
    grouping uses unit row weights. When exposure is configured, ``target_col``
    contains aggregate claims divided by exposure for tree training. Otherwise
    it contains rates. When absent, ``y`` supplies strictly one-dimensional rates.
    Supplied outcomes must be finite after numeric and unit conversion;
    missing outcomes are never treated as zero.

    ``fixed`` accepts per-feature ``{groups: [{level: ..., group: ...}], missing:
    ..., unseen: ...}``. Scalar category types are retained; missing/unseen
    destinations are explicit. Equal numeric/boolean aliases are rejected.

    Attributes
    ----------
    mapping_, category_dtypes_, group_cols_, n_features_in_, feature_names_in_.
    missing_ : dict[str, object]
        Fitted group label used for missing and unseen levels.
    unseen_ : dict[str, object]
        Explicit unseen destinations for fixed mappings; otherwise uses missing_.
    """

    mapping_: dict[str, dict[Hashable, Hashable]]
    missing_: dict[str, Hashable]
    category_dtypes_: dict[str, pd.CategoricalDtype]
    feature_names_in_: np.ndarray
    n_features_in_: int

    def __init__(
        self,
        cols: Sequence[str] | None = None,
        strategy: str = "similarity",
        max_groups: int = 10,
        min_exposure: float | None = None,
        min_claims: float | None = None,
        exposure_col: str | None = None,
        claim_count_col: str | None = None,
        target_col: str | None = None,
        other_label: str = "Other",
        fixed: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        self.cols = cols
        self.strategy = strategy
        self.max_groups = max_groups
        self.min_exposure = min_exposure
        self.min_claims = min_claims
        self.exposure_col = exposure_col
        self.claim_count_col = claim_count_col
        self.target_col = target_col
        self.other_label = other_label
        self.fixed = fixed

    def __sklearn_tags__(self):
        tags = super().__sklearn_tags__()
        tags.input_tags.allow_nan = True
        tags.input_tags.string = True
        return tags

    def fit(self, X: pd.DataFrame | ArrayLike, y: ArrayLike | None = None) -> Self:
        if self.strategy not in ("rare", "similarity"):
            raise ValueError(f"strategy must be 'rare' or 'similarity'; got {self.strategy!r}")
        if (
            not isinstance(self.max_groups, Integral)
            or isinstance(self.max_groups, bool)
            or self.max_groups < 1
        ):
            raise ValueError(
                f"max_groups must be at least 1 and an integer; got {self.max_groups!r}"
            )
        validate_data(self, X, dtype=None, ensure_all_finite=False)
        X_df, _ = _to_frame(X)
        cols = self._select_cols(X_df)
        exp = _column_array(X_df, self.exposure_col, required=True, minimum=EXPOSURE_FLOOR)
        cc = _column_array(X_df, self.claim_count_col, required=True)
        _check_controls(self, exp, cc)
        target = _resolve_target(X_df, y, self.target_col, exp)
        fixed = _fixed_specs(self.fixed, cols)
        if self.strategy == "similarity" and target is None and set(cols) - set(fixed):
            raise ValueError("similarity grouping requires a target (target_col in X or y)")
        self.mapping_ = {}
        self.category_dtypes_ = {}
        self.trees_ = {}
        self.leaf_groups_ = {}
        self.levels_ = {}
        self.missing_ = {}
        self.unseen_ = {}
        self.tree_mappings_ = {}
        for col in cols:
            series = X_df[col]
            if col in fixed:
                spec = fixed[col]
                if set(spec) != {"groups", "missing", "unseen"} or not isinstance(
                    spec["groups"], list
                ):
                    raise ValueError(
                        "fixed groups require groups (level/group records), missing and unseen"
                    )
                mapping = {}
                for entry in spec["groups"]:
                    if not isinstance(entry, Mapping) or set(entry) != {"level", "group"}:
                        raise ValueError("fixed groups must contain level/group records")
                    level, group = _fixed_level(entry["level"]), _fixed_level(entry["group"])
                    if level in mapping:
                        raise ValueError(
                            "fixed group levels must be unique, including equal numeric/bool values"
                        )
                    mapping[level] = group
                missing, unseen = _fixed_level(spec["missing"]), _fixed_level(spec["unseen"])
                categories = list(dict.fromkeys([*mapping.values(), missing, unseen]))
                for value in [*mapping.values(), missing, unseen]:
                    if not any(
                        type(value) is type(other) and value == other for other in categories
                    ):
                        raise ValueError(
                            "fixed group destinations must not alias across scalar types"
                        )
                self.mapping_[col] = mapping
                self.missing_[col] = missing
                self.unseen_[col] = unseen
                self.category_dtypes_[col] = pd.CategoricalDtype(
                    categories,
                    ordered=isinstance(series.dtype, pd.CategoricalDtype) and series.cat.ordered,
                )
                continue
            ordered_levels = (
                list(series.cat.categories)
                if isinstance(series.dtype, pd.CategoricalDtype) and series.cat.ordered
                else None
            )
            if self.strategy == "similarity":
                levels = (
                    [level for level in ordered_levels if level in series.values]
                    if ordered_levels is not None
                    else series.dropna().unique().tolist()
                )
                values = self._encoded(series, levels)
                tree, groups, _ = _fit_tree(
                    values,
                    target,
                    exp,
                    cc,
                    self.max_groups,
                    self.min_exposure,
                    self.min_claims,
                    categorical=ordered_levels is None,
                )
                level_groups = (
                    [
                        groups[leaf]
                        for leaf in _leaf_predictions(tree, np.arange(len(levels), dtype=float))
                    ]
                    if levels
                    else []
                )
                labels = {}
                taken = set(levels) | {self.other_label}
                for i in sorted(set(groups.values())):
                    members = [
                        level
                        for level, group in zip(levels, level_groups, strict=True)
                        if group == i
                    ]
                    label = members[0] if len(members) == 1 else f"group_{i}"
                    if len(members) != 1:
                        while label in taken:
                            label += "_"
                    taken.add(label)
                    labels[i] = label
                mapping = {
                    level: labels[group] for level, group in zip(levels, level_groups, strict=True)
                }
                self.trees_[col] = tree
                self.tree_mappings_[col] = mapping.copy()
                self.leaf_groups_[col] = {leaf: labels[group] for leaf, group in groups.items()}
                self.levels_[col] = levels
                self.missing_[col] = self.leaf_groups_[col][
                    _leaf_predictions(tree, np.array([np.nan]))[0]
                ]
                self.category_dtypes_[col] = pd.CategoricalDtype(
                    list(labels.values()), ordered=ordered_levels is not None
                )
            else:
                stats = self._level_stats(series, exp, cc)
                if ordered_levels is not None:
                    stats = stats.reindex(
                        [level for level in ordered_levels if level in stats.index]
                    )
                mapping = self._rare_mapping(stats)
                self.missing_[col] = self.other_label
                self.category_dtypes_[col] = self._category_dtype(
                    mapping, ordered=ordered_levels is not None
                )
            self.mapping_[col] = mapping
        self.group_cols_ = cols
        return self

    def _select_cols(self, X):
        specials = {c for c in (self.exposure_col, self.claim_count_col, self.target_col) if c}
        if self.cols is not None:
            invalid = sorted(set(self.cols) & specials)
            if invalid:
                raise ValueError(f"cols contains special columns: {invalid}")
            missing = sorted(set(self.cols) - set(X.columns))
            if missing:
                raise ValueError(f"cols not found in X: {missing}")
            return list(self.cols)
        return [
            c for c in X.columns if c not in specials and not pd.api.types.is_numeric_dtype(X[c])
        ]

    def _level_stats(self, values, exp, cc):
        df = pd.DataFrame({"lvl": values})
        df["exp"] = exp if exp is not None else 1.0
        g = df.groupby("lvl", observed=True, sort=False)
        stats = pd.DataFrame({"exp": g["exp"].sum()})
        if cc is not None:
            df["cc"] = cc
            stats["cc"] = df.groupby("lvl", observed=True, sort=False)["cc"].sum()
        return stats

    def _rare_mapping(self, stats):
        mp = {}
        for lvl, row in stats.iterrows():
            keep = True
            if self.min_exposure is not None and float(row["exp"]) < self.min_exposure:
                keep = False
            if self.min_claims is not None and "cc" in stats and float(row["cc"]) < self.min_claims:
                keep = False
            mp[lvl] = lvl if keep else self.other_label
        return mp

    @staticmethod
    def _encoded(series, levels):
        codes = pd.Index(levels).get_indexer(series).astype(float)
        codes[codes < 0] = np.nan
        return codes

    def _category_dtype(self, mapping, *, ordered):
        categories = [
            level for level in dict.fromkeys(mapping.values()) if level != self.other_label
        ]
        return pd.CategoricalDtype([*categories, self.other_label], ordered=ordered)

    @overload
    def transform(self, X: pd.DataFrame) -> pd.DataFrame: ...

    @overload
    def transform(self, X: ArrayLike) -> np.ndarray: ...

    def transform(self, X: pd.DataFrame | ArrayLike) -> pd.DataFrame | np.ndarray:
        _validate_transform_input(self, X)
        X_df, was_df = _to_frame(X, required_columns=self.mapping_)
        out = X_df.copy()
        unseen = {}
        for col, mp in self.mapping_.items():
            unknown = ~out[col].isin(mp)
            if self.strategy == "similarity":
                unknown &= out[col].notna()
            if unknown.any():
                unseen[col] = out.loc[unknown, col].drop_duplicates().tolist()
            if col in self.trees_:
                values = self._encoded(out[col], self.levels_[col])
                out[col] = pd.Categorical(
                    [
                        self.leaf_groups_[col][leaf]
                        for leaf in _leaf_predictions(self.trees_[col], values)
                    ],
                    dtype=self.category_dtypes_[col],
                )
            else:
                out[col] = (
                    out[col]
                    .astype(object)
                    .map(mp)
                    .mask(out[col].isna(), self.missing_[col])
                    .fillna(self.unseen_.get(col, self.missing_[col]))
                    .astype(self.category_dtypes_[col])
                )
        if unseen:
            details = "; ".join(f"{column}={levels!r}" for column, levels in unseen.items())
            destination = (
                "explicit unseen destinations" if self.unseen_ else "fitted missing destinations"
            )
            warnings.warn(
                f"AutoGrouper mapped unseen levels to {destination}: {details}",
                UserWarning,
                stacklevel=2,
            )
        return out if was_df else out.to_numpy()

    def get_feature_names_out(
        self, input_features: Sequence[str] | np.ndarray | None = None
    ) -> np.ndarray:
        return _feature_names(self, input_features)

    def set_mapping(
        self,
        mapping: Mapping[str, Mapping[Hashable, Hashable]],
        *,
        missing: Mapping[str, Hashable] | None = None,
    ) -> None:
        """Replace fitted groups: ``{col: {level: group_label}}``.

        Keys must name currently grouped columns. Omitted columns pass through.
        Changed tree mappings require ``missing={column: group_label}``, also
        used for unseen levels. An unchanged round-trip preserves native routing.
        Manual decisions replace learned credibility guarantees.
        Invalid overrides leave the fitted mappings and vocabularies intact.
        """
        check_is_fitted(self, "mapping_")
        unknown = set(mapping) - set(self.group_cols_)
        if unknown:
            raise ValueError(f"mapping columns were not grouped: {sorted(unknown)}")
        replacement = {c: dict(m) for c, m in mapping.items()}
        missing = {} if missing is None else dict(missing)
        if set(missing) - set(replacement):
            raise ValueError("missing destinations must name mapping columns")
        trees, leaf_groups, levels, routes, dtypes = {}, {}, {}, {}, {}
        for col, values in replacement.items():
            unchanged = values == self.tree_mappings_.get(col, self.mapping_[col])
            if col in self.trees_ and unchanged and col not in missing:
                trees[col] = self.trees_[col]
                leaf_groups[col] = self.leaf_groups_[col]
                levels[col] = self.levels_[col]
                routes[col] = self.missing_[col]
                dtypes[col] = self.category_dtypes_[col]
                continue
            if col not in self.trees_ and unchanged and col not in missing:
                routes[col] = self.missing_[col]
                dtypes[col] = self.category_dtypes_[col]
                continue
            if col in self.trees_ and col not in missing:
                raise ValueError(
                    f"changed tree mapping for {col!r} requires an explicit missing destination"
                )
            route = missing.get(col, self.other_label)
            categories = list(dict.fromkeys([*values.values(), route]))
            dtypes[col] = pd.CategoricalDtype(
                categories, ordered=self.category_dtypes_[col].ordered
            )
            routes[col] = route
        unseen_routes = {
            col: self.unseen_.get(col, routes[col])
            if replacement[col] == self.mapping_[col] and col not in missing
            else routes[col]
            for col in replacement
        }
        self.mapping_ = replacement
        self.category_dtypes_ = dtypes
        self.trees_, self.leaf_groups_, self.levels_ = trees, leaf_groups, levels
        self.missing_, self.unseen_ = routes, unseen_routes
        self.tree_mappings_ = {col: self.tree_mappings_[col] for col in trees}
        self.group_cols_ = list(mapping.keys())
