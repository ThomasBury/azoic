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

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.isotonic import isotonic_regression
from sklearn.tree import DecisionTreeRegressor
from sklearn.utils.validation import validate_data

from azoic.validation import _weighted_quantile_edges

__all__ = ["AutoBinner", "AutoGrouper"]


def _to_frame(X):
    """Return (DataFrame, was_dataframe). Names: real or f'x{i}' for ndarray.

    ``np.asarray`` unwraps sklearn's ``_NotAnArray`` and ``list`` payloads.
    """
    if isinstance(X, pd.DataFrame):
        return X, True
    arr = np.asarray(X)
    n = arr.shape[1]
    return pd.DataFrame(arr, columns=pd.Index([f"x{i}" for i in range(n)])), False


def _column_array(X, name):
    if name and name in X.columns:
        return X[name].to_numpy(dtype=float)
    return None


def _resolve_target(X, y, target_col, exposure_col):
    target = _column_array(X, target_col)
    exposure = _column_array(X, exposure_col)
    if target is not None and exposure is not None:
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(exposure > 0, target / exposure, 0.0)
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
            bin_weights[-2] += bin_weights.pop()
        else:
            edges.pop(small)
            bin_weights[small] += bin_weights.pop(small + 1)
    return np.array(edges, dtype=float)


class AutoBinner(TransformerMixin, BaseEstimator):
    """Bin numeric columns into actuarially-credible tariff bins.

    Binned columns become ordered interval categoricals (DataFrame input) or
    integer bin codes (ndarray input). Non-target columns pass through
    unchanged. NaN is assigned to a reserved ``"Missing"`` category.

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
        Requires ``exposure_col``; ignored if absent.
    min_claims : float | None
        Minimum aggregate claim count per bin; smaller bins merge into neighbours.
    exposure_col, claim_count_col, target_col : str | None
        Special columns inside X. For tree binning, the target is
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
        validate_data(self, X, y=y, dtype=None, ensure_all_finite=False)
        X_df, _ = _to_frame(X)
        cols = self._select_cols(X_df)
        exp = _column_array(X_df, self.exposure_col)
        cc = _column_array(X_df, self.claim_count_col)
        if self.min_claims is not None and cc is None:
            raise ValueError("min_claims requires claim_count_col in X")
        target = _resolve_target(X_df, y, self.target_col, self.exposure_col)
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
            return [c for c in self.cols if c in X.columns]
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
        weights = w if w is not None else np.ones_like(v)
        edges = _merge_small_bins(v, weights, edges, self.min_exposure)
        claim_counts = cc[mask] if cc is not None else np.ones_like(v)
        return _merge_small_bins(v, claim_counts, edges, self.min_claims)

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
                labels[i] = f"(-inf, {edge_labels[0]}]"
            elif c >= n:
                labels[i] = f"({edge_labels[-1]}, inf)"
            else:
                labels[i] = f"({edge_labels[c - 1]}, {edge_labels[c]}]"
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
        """Override fitted bin edges: ``{col: array_of_edges}``."""
        self.mapping_ = {c: np.asarray(e, dtype=float) for c, e in mapping.items()}
        self.category_dtypes_ = {
            col: self._category_dtype(edges) for col, edges in self.mapping_.items()
        }
        self.bin_cols_ = list(mapping.keys())


class AutoGrouper(TransformerMixin, BaseEstimator):
    """Group categorical levels into credibility-stable groups.

    Strategies
    ----------
    "rare"        Levels below ``min_exposure`` / ``min_claims`` -> ``other_label``.
    "similarity"  Nominal levels are risk-sorted before grouping. Ordered
                  categoricals merge only adjacent levels, choosing the
                  closest exposure-weighted pure premium and breaking ties
                  to the left.

    ``mapping_`` is ``{col: {original_level: group_label}}``. Unknown levels at
    transform time map to ``other_label``.

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
        validate_data(self, X, y=y, dtype=None, ensure_all_finite=False)
        X_df, _ = _to_frame(X)
        cols = self._select_cols(X_df)
        exp = _column_array(X_df, self.exposure_col)
        cc = _column_array(X_df, self.claim_count_col)
        if self.min_claims is not None and cc is None:
            raise ValueError("min_claims requires claim_count_col in X")
        target = _column_array(X_df, self.target_col)
        if target is None and y is not None:
            target = np.asarray(y, dtype=float)
            if exp is not None:
                target = target * exp
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
            return [c for c in self.cols if c in X.columns]
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
        if ordered_levels is not None:
            return self._ordered_similarity_mapping(stats)
        return self._similarity_mapping(stats)

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

    def _similarity_mapping(self, stats):
        order = stats.sort_values("pp", kind="stable").index.tolist()
        floor_exp = self.min_exposure or 0.0
        floor_cc = self.min_claims or 0.0
        has_cc = "cc" in stats.columns
        groups, cur, cur_exp, cur_cc = [], [], 0.0, 0.0
        for lvl in order:
            r = stats.loc[lvl]
            cur.append(lvl)
            cur_exp += float(r["exp"])
            if has_cc:
                cur_cc += float(r["cc"])
            if cur_exp >= floor_exp and cur_cc >= floor_cc:
                groups.append(cur)
                cur, cur_exp, cur_cc = [], 0.0, 0.0
        if cur:
            if groups:
                groups[-1].extend(cur)
            else:
                groups.append(cur)
        if self.max_groups and len(groups) > self.max_groups:
            while len(groups) > self.max_groups:
                groups[-2].extend(groups.pop())
        mp = {}
        for i, grp in enumerate(groups):
            label = grp[0] if len(grp) == 1 else f"group_{i}"
            for lvl in grp:
                mp[lvl] = label
        return mp

    def _ordered_similarity_mapping(self, stats):
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

        while self.max_groups and len(groups) > self.max_groups:
            differences = [
                abs(risk(groups[i]) - risk(groups[i + 1])) for i in range(len(groups) - 1)
            ]
            index = min(range(len(differences)), key=differences.__getitem__)
            groups[index].extend(groups.pop(index + 1))

        mp = {}
        for i, group in enumerate(groups):
            label = group[0] if len(group) == 1 else f"group_{i}"
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
        """Override fitted level groups: ``{col: {level: group_label}}``."""
        ordered = {
            col: self.category_dtypes_[col].ordered
            for col in mapping
            if hasattr(self, "category_dtypes_") and col in self.category_dtypes_
        }
        self.mapping_ = {c: dict(m) for c, m in mapping.items()}
        self.category_dtypes_ = {
            col: self._category_dtype(values, ordered=ordered.get(col, False))
            for col, values in self.mapping_.items()
        }
        self.group_cols_ = list(mapping.keys())
