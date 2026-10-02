"""Auto-binning and auto-grouping transformers for tariff preprocessing.

AutoBinner: numeric columns -> actuarially-credible interval bins
    ("quantile" equal-exposure edges, or "tree" decision-tree edges on y).
AutoGrouper: categorical columns -> credibility-stable level groups
    ("rare" floor-based, or "similarity" greedy 1D merging on pure premium).

Both follow the scikit-learn transformer API and survive
`sklearn.utils.estimator_checks.parametrize_with_checks`. Special columns
(exposure, claim_count, target) travel inside X per AGENTS.md rule 8.
`mapping_` is overridable via `set_mapping`; `transform` honours the override.
"""

from __future__ import annotations

import warnings
from numbers import Integral

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.isotonic import isotonic_regression
from sklearn.tree import DecisionTreeRegressor
from sklearn.utils.validation import check_array, check_is_fitted, validate_data

from azoic.data import EXPOSURE_FLOOR, MIN_EXPOSURE
from azoic.validation import _weighted_quantile_edges

__all__ = ["AutoBinner", "AutoGrouper"]


def _check_min_exposure(min_exposure, exp) -> None:
    """``min_exposure`` is an exposure-unit floor: below one day (1/366) is
    meaningless, and without a real exposure column it silently becomes a
    row-count floor."""
    if min_exposure is None:
        return
    if min_exposure < MIN_EXPOSURE:
        raise ValueError(f"min_exposure must be at least 1/366 (one day); got {min_exposure}")
    if exp is None:
        raise ValueError("min_exposure requires exposure_col in X")


def _to_frame(X):
    """Return (DataFrame, was_dataframe). Names: real or f'x{i}' for ndarray.

    ``np.asarray`` unwraps sklearn's ``_NotAnArray`` and ``list`` payloads.
    """
    if isinstance(X, pd.DataFrame):
        return X, True
    arr = np.asarray(X)
    n = arr.shape[1]
    return pd.DataFrame(arr, columns=pd.Index([f"x{i}" for i in range(n)])), False


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
        return target / exposure
    if target is not None:
        return target
    return None if y is None else np.asarray(y, dtype=float)


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
    unchanged. Finite bin edges are lower-inclusive and upper-exclusive.
    NaN is assigned to a reserved ``"Missing"`` category.

    Parameters
    ----------
    cols : list[str] | None
        Columns to bin. None -> all numeric columns found in fit.
    strategy : {"quantile", "tree"}
        "quantile" = (exposure-)weighted equal-frequency edges.
        "tree" = DecisionTreeRegressor(max_leaf_nodes=max_bins) on the target.
    max_bins : int
        Maximum number of bins per column (>=2).
    min_exposure : float | None
        Minimum total exposure per bin; smaller bins merged into neighbours.
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
        ``target_col``, else ``y``.
    monotonic : False | True | "increasing" | "decreasing"
        When set, bin means are smoothed to be monotonic in the target via
        ``isotonic_regression`` and adjacent bins with the same smoothed mean
        merge. No-op without a target. False = off, True / "increasing" =
        non-decreasing bin means, "decreasing" = non-increasing. Applied
        after the strategy and before the ``min_exposure`` small-bin merge.
    random_state : int
        Tree strategy reproducibility.

    Attributes
    ----------
    mapping_ : dict[str, np.ndarray]
        Bin edges per binned column (length n_bins - 1).
    category_dtypes_ : dict[str, pd.CategoricalDtype]
        Stable ordered output vocabularies for DataFrame inputs.
    bin_cols_ : list[str]
    n_features_in_ : int
    feature_names_in_ : list[str] | None
    """

    def __init__(
        self,
        cols=None,
        strategy="quantile",
        max_bins=8,
        min_exposure=None,
        min_claims=None,
        exposure_col=None,
        claim_count_col=None,
        target_col=None,
        monotonic=False,
        random_state=42,
    ):
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

    def __sklearn_tags__(self):
        tags = super().__sklearn_tags__()
        tags.input_tags.allow_nan = True
        tags.input_tags.string = True
        return tags

    def fit(self, X, y=None):
        if self.strategy not in ("quantile", "tree"):
            raise ValueError(f"strategy must be 'quantile' or 'tree'; got {self.strategy!r}")
        if (
            not isinstance(self.max_bins, Integral)
            or isinstance(self.max_bins, bool)
            or self.max_bins < 2
        ):
            raise ValueError(f"max_bins must be an integer at least 2; got {self.max_bins!r}")
        validate_data(self, X, y=y, dtype=None, ensure_all_finite=False)
        X_df, _ = _to_frame(X)
        cols = self._select_cols(X_df)
        exp = _column_array(X_df, self.exposure_col, required=True, minimum=EXPOSURE_FLOOR)
        cc = _column_array(X_df, self.claim_count_col, required=True)
        _check_min_exposure(self.min_exposure, exp)
        if self.min_claims is not None and cc is None:
            raise ValueError("min_claims requires claim_count_col in X")
        target = _resolve_target(X_df, y, self.target_col, exp)
        self.mapping_ = {}
        for col in cols:
            edges = self._edges(X_df[col].to_numpy(dtype=float), target, exp, cc)
            self.mapping_[col] = edges
        self.category_dtypes_ = {
            col: self._category_dtype(edges) for col, edges in self.mapping_.items()
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
        return [c for c in X.columns if c not in specials and pd.api.types.is_numeric_dtype(X[c])]

    def _edges(self, values, target, exp, cc):
        mask = ~np.isnan(values)
        v = values[mask]
        if len(v) == 0:
            return np.array([])
        w = exp[mask] if exp is not None else None
        if self.strategy == "tree" and target is not None:
            ym = target[mask] if target is not None else None
            if ym is not None and not np.all(np.isnan(ym)):
                ym = np.nan_to_num(ym, nan=0.0)
                edges = self._tree_edges(v, ym, w)
            else:
                edges = self._quantile_edges(v, w)
        else:
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
        with np.errstate(divide="ignore", invalid="ignore"):
            bin_means = np.where(w_sum > 0, tgt_sum / w_sum, 0.0)
        sw = w_sum if np.any(w_sum > 0) else None
        increasing = self._mono_direction()
        smoothed = isotonic_regression(bin_means, increasing=increasing, sample_weight=sw)
        keep = np.where(smoothed[:-1] != smoothed[1:])[0]
        return edges[keep]

    def _quantile_edges(self, v, w):
        if w is None:
            return np.unique(np.quantile(v, np.linspace(0, 1, self.max_bins + 1)[1:-1]))
        return _weighted_quantile_edges(v, w, n_quantiles=self.max_bins)

    def _tree_edges(self, v, y, w):
        tree = DecisionTreeRegressor(
            max_leaf_nodes=self.max_bins, min_samples_leaf=1, random_state=self.random_state
        )
        tree.fit(v.reshape(-1, 1), y, sample_weight=w)
        thr = tree.tree_.threshold
        internal = tree.tree_.children_left != -1
        edges = np.unique(thr[internal])
        edges = edges[(edges > v.min()) & (edges < v.max())]
        return edges

    def transform(self, X):
        validate_data(self, X, reset=False, dtype=None, ensure_all_finite=False)
        X_df, was_df = _to_frame(X)
        feature_names = getattr(self, "feature_names_in_", None)
        if feature_names is not None and all(c in X_df.columns for c in feature_names):
            X_df = X_df[feature_names]
        out = X_df.copy()
        for col, edges in self.mapping_.items():
            if col not in out.columns:
                continue
            codes = self._codes(out[col].to_numpy(dtype=float), edges)
            if was_df:
                out[col] = pd.Categorical.from_codes(codes, dtype=self.category_dtypes_[col])
            else:
                out[col] = codes.astype(float)
        return out if was_df else out.to_numpy()

    @staticmethod
    def _codes(values, edges):
        codes = np.searchsorted(edges, values, side="right")
        codes = np.where(np.isnan(values), len(edges) + 1, codes)
        return codes.astype(int)

    @staticmethod
    def _labels(codes, edges):
        n = len(edges)
        edge_labels = [repr(float(edge)) for edge in edges]
        labels = np.empty(len(codes), dtype=object)
        for i, c in enumerate(codes):
            if c > n:
                labels[i] = "Missing"
            elif n == 0:
                labels[i] = "(-inf, inf)"
            elif c == 0:
                labels[i] = f"(-inf, {edge_labels[0]})"
            elif c >= n:
                labels[i] = f"[{edge_labels[-1]}, inf)"
            else:
                labels[i] = f"[{edge_labels[c - 1]}, {edge_labels[c]})"
        return labels

    @staticmethod
    def _category_dtype(edges):
        categories = AutoBinner._labels(np.arange(len(edges) + 2), edges).tolist()
        return pd.CategoricalDtype(categories, ordered=True)

    def get_feature_names_out(self, input_features=None):
        if input_features is not None:
            return np.asarray(input_features)
        if hasattr(self, "feature_names_in_"):
            return self.feature_names_in_
        n_features = getattr(self, "n_features_in_", None)
        if n_features is None:
            raise ValueError("AutoBinner must be fitted before getting feature names")
        return np.asarray([f"x{i}" for i in range(n_features)])

    def set_mapping(self, mapping):
        """Replace fitted bin mappings with finite, strictly increasing edge vectors.

        Keys must name currently binned columns. Omitted columns pass through.
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
        dtypes = {col: self._category_dtype(edges) for col, edges in replacement.items()}
        self.mapping_ = replacement
        self.category_dtypes_ = dtypes
        self.bin_cols_ = list(mapping.keys())


class AutoGrouper(TransformerMixin, BaseEstimator):
    """Group categorical levels into credibility-stable groups.

    Strategies
    ----------
    "rare"        Levels below ``min_exposure`` / ``min_claims`` -> ``other_label``.
                  ``min_exposure`` requires a real ``exposure_col`` column and
                  must be >= 1/366 (one day).
    "similarity"  Nominal levels are stably risk-sorted; ordered categoricals
                  retain their declared order. Under-credible groups merge
                  with their nearest-risk neighbour, then the closest adjacent
                  pairs merge until ``max_groups`` is met. Risks are aggregate
                  claims / exposure, recomputed after each merge; ties go left.

    ``mapping_`` is ``{col: {original_level: group_label}}``. Unknown levels at
    transform time map to ``other_label``.

    Configured exposure and claim-count columns must exist at fit and contain
    finite values; exposures must be at least one day (1/366, with day-count
    tolerance), and claim counts must be non-negative. Without ``exposure_col``,
    grouping uses unit row weights. ``target_col`` contains aggregate claims;
    when absent, ``y`` supplies rates, multiplied by exposure before pooling.

    Attributes
    ----------
    mapping_, category_dtypes_, group_cols_, n_features_in_, feature_names_in_.
    """

    def __init__(
        self,
        cols=None,
        strategy="similarity",
        max_groups=10,
        min_exposure=None,
        min_claims=None,
        exposure_col=None,
        claim_count_col=None,
        target_col=None,
        other_label="Other",
    ):
        self.cols = cols
        self.strategy = strategy
        self.max_groups = max_groups
        self.min_exposure = min_exposure
        self.min_claims = min_claims
        self.exposure_col = exposure_col
        self.claim_count_col = claim_count_col
        self.target_col = target_col
        self.other_label = other_label

    def __sklearn_tags__(self):
        tags = super().__sklearn_tags__()
        tags.input_tags.allow_nan = True
        tags.input_tags.string = True
        return tags

    def fit(self, X, y=None):
        if self.strategy not in ("rare", "similarity"):
            raise ValueError(f"strategy must be 'rare' or 'similarity'; got {self.strategy!r}")
        if self.max_groups is None or self.max_groups < 1:
            raise ValueError(f"max_groups must be at least 1; got {self.max_groups!r}")
        validate_data(self, X, y=y, dtype=None, ensure_all_finite=False)
        X_df, _ = _to_frame(X)
        cols = self._select_cols(X_df)
        exp = _column_array(X_df, self.exposure_col, required=True, minimum=EXPOSURE_FLOOR)
        cc = _column_array(X_df, self.claim_count_col, required=True)
        _check_min_exposure(self.min_exposure, exp)
        if self.min_claims is not None and cc is None:
            raise ValueError("min_claims requires claim_count_col in X")
        target = _column_array(X_df, self.target_col)
        if target is None and y is not None:
            target = np.asarray(y, dtype=float)
            if exp is not None:
                target = target * exp
        if self.strategy == "similarity" and target is None:
            raise ValueError(
                "similarity grouping requires a target (target_col in X or y); "
                "without one every level has risk zero and merges in incidental order"
            )
        self.mapping_ = {}
        self.category_dtypes_ = {}
        for col in cols:
            series = X_df[col]
            ordered_levels = (
                list(series.cat.categories)
                if isinstance(series.dtype, pd.CategoricalDtype) and series.cat.ordered
                else None
            )
            mapping = self._group_levels(series, exp, cc, target, ordered_levels)
            self.mapping_[col] = mapping
            self.category_dtypes_[col] = self._category_dtype(
                mapping, ordered=ordered_levels is not None
            )
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

    def _level_stats(self, values, exp, cc, target):
        df = pd.DataFrame({"lvl": values})
        df["exp"] = exp if exp is not None else 1.0
        g = df.groupby("lvl", observed=True, sort=False)
        stats = pd.DataFrame({"exp": g["exp"].sum()})
        if cc is not None:
            df["cc"] = cc
            stats["cc"] = df.groupby("lvl", observed=True, sort=False)["cc"].sum()
        if target is not None:
            df["tgt"] = target
            stats["tgt"] = df.groupby("lvl", observed=True, sort=False)["tgt"].sum()
            stats["pp"] = stats["tgt"] / stats["exp"].replace(0.0, np.nan)
        else:
            stats["pp"] = 0.0
        return stats

    def _group_levels(self, values, exp, cc, target, ordered_levels=None):
        stats = self._level_stats(values, exp, cc, target)
        if ordered_levels is not None:
            stats = stats.reindex([level for level in ordered_levels if level in stats.index])
        if self.strategy == "rare":
            return self._rare_mapping(stats)
        if ordered_levels is None:
            stats = stats.sort_values("pp", kind="stable")
        return self._adjacent_similarity_mapping(stats)

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

    def _adjacent_similarity_mapping(self, stats):
        groups = [[level] for level in stats.index]
        floor_exp = self.min_exposure or 0.0
        floor_cc = self.min_claims or 0.0

        def total(group, column):
            return float(stats.loc[group, column].sum())

        def risk(group):
            exposure = total(group, "exp")
            return total(group, "tgt") / exposure if "tgt" in stats and exposure > 0 else 0.0

        while len(groups) > 1:
            index = next(
                (
                    i
                    for i, group in enumerate(groups)
                    if total(group, "exp") < floor_exp
                    or ("cc" in stats and total(group, "cc") < floor_cc)
                ),
                None,
            )
            if index is None:
                break
            if index == 0:
                merge_left = False
            elif index == len(groups) - 1:
                merge_left = True
            else:
                merge_left = abs(risk(groups[index]) - risk(groups[index - 1])) <= abs(
                    risk(groups[index]) - risk(groups[index + 1])
                )
            if merge_left:
                groups[index - 1].extend(groups.pop(index))
            else:
                groups[index].extend(groups.pop(index + 1))

        while len(groups) > self.max_groups:
            differences = [
                abs(risk(groups[i]) - risk(groups[i + 1])) for i in range(len(groups) - 1)
            ]
            index = min(range(len(differences)), key=differences.__getitem__)
            groups[index].extend(groups.pop(index + 1))

        mp = {}
        taken = set(stats.index) | {self.other_label}
        for i, group in enumerate(groups):
            if len(group) == 1:
                label = group[0]
            else:
                label = f"group_{i}"
                suffix = 0
                while label in taken:
                    suffix += 1
                    label = f"group_{i}_{suffix}"
            taken.add(label)
            for level in group:
                mp[level] = label
        return mp

    def _category_dtype(self, mapping, *, ordered):
        categories = [
            level for level in dict.fromkeys(mapping.values()) if level != self.other_label
        ]
        return pd.CategoricalDtype([*categories, self.other_label], ordered=ordered)

    def transform(self, X):
        validate_data(self, X, reset=False, dtype=None, ensure_all_finite=False)
        X_df, was_df = _to_frame(X)
        feature_names = getattr(self, "feature_names_in_", None)
        if feature_names is not None and all(c in X_df.columns for c in feature_names):
            X_df = X_df[feature_names]
        out = X_df.copy()
        unseen = {}
        for col, mp in self.mapping_.items():
            if col not in out.columns:
                continue
            unknown = out[col].notna() & ~out[col].isin(mp)
            if unknown.any():
                unseen[col] = out.loc[unknown, col].drop_duplicates().tolist()
            out[col] = (
                out[col]
                .astype(object)
                .map(mp)
                .fillna(self.other_label)
                .astype(self.category_dtypes_[col])
            )
        if unseen:
            details = "; ".join(f"{column}={levels!r}" for column, levels in unseen.items())
            warnings.warn(
                f"AutoGrouper mapped unseen levels to {self.other_label!r}: {details}",
                UserWarning,
                stacklevel=2,
            )
        return out if was_df else out.to_numpy()

    def get_feature_names_out(self, input_features=None):
        if input_features is not None:
            return np.asarray(input_features)
        if hasattr(self, "feature_names_in_"):
            return self.feature_names_in_
        n_features = getattr(self, "n_features_in_", None)
        if n_features is None:
            raise ValueError("AutoGrouper must be fitted before getting feature names")
        return np.asarray([f"x{i}" for i in range(n_features)])

    def set_mapping(self, mapping):
        """Replace fitted groups: ``{col: {level: group_label}}``.

        Keys must name currently grouped columns. Omitted columns pass through.
        Invalid overrides leave the fitted mappings and vocabularies intact.
        """
        check_is_fitted(self, "mapping_")
        unknown = set(mapping) - set(self.group_cols_)
        if unknown:
            raise ValueError(f"mapping columns were not grouped: {sorted(unknown)}")
        replacement = {c: dict(m) for c, m in mapping.items()}
        dtypes = {
            col: self._category_dtype(values, ordered=self.category_dtypes_[col].ordered)
            for col, values in replacement.items()
        }
        self.mapping_ = replacement
        self.category_dtypes_ = dtypes
        self.group_cols_ = list(mapping.keys())
