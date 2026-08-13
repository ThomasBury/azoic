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

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.isotonic import isotonic_regression
from sklearn.tree import DecisionTreeRegressor
from sklearn.utils.validation import validate_data

__all__ = ["AutoBinner", "AutoGrouper"]



def _to_frame(X):
    """Return (DataFrame, was_dataframe). Names: real or f'x{i}' for ndarray.

    ``np.asarray`` unwraps sklearn's ``_NotAnArray`` and ``list`` payloads.
    """
    if isinstance(X, pd.DataFrame):
        return X, True
    arr = np.asarray(X)
    n = arr.shape[1]
    return pd.DataFrame(arr, columns=[f"x{i}" for i in range(n)]), False


def _merge_small_bins(values, weights, edges, min_weight):
    """Iteratively merge bins below the weight floor into an adjacent bin.

    ponytail: O(n * n_bins) repetitive re-binning; fine until >1e6 rows.
    """
    if min_weight is None or len(edges) == 0:
        return edges
    total = float(weights.sum())
    if total < min_weight:
        return np.array([])  # impossible to satisfy any floor; single bin
    v, w = values, weights
    edges = list(edges)
    while edges:
        codes = np.searchsorted(np.array(edges), v, side="right")
        exp_per = np.bincount(codes, weights=w, minlength=len(edges) + 1)
        small = np.where(exp_per < min_weight)[0]
        if len(small) == 0:
            break
        i = int(small[0])
        if i == 0:
            edges.pop(0)
        elif i >= len(edges):
            edges.pop(-1)
        else:
            edges.pop(i)
    return np.array(edges, dtype=float)


class AutoBinner(TransformerMixin, BaseEstimator):
    """Bin numeric columns into actuarially-credible tariff bins.

    Binned columns become readable interval labels (DataFrame input) or integer
    bin codes (ndarray input). Non-target columns pass through unchanged. NaN
    is assigned to the last bin (ponytail: dedicated missing bin when needed).

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
        Minimum total claim_count per bin (tree strategy min_samples_leaf).
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

    def _array(self, X, name):
        if name and name in X.columns:
            return X[name].to_numpy(dtype=float)
        return None

    def fit(self, X, y=None):
        validate_data(self, X, y=y, dtype=None, ensure_all_finite=False)
        X_df, _ = _to_frame(X)
        cols = self._select_cols(X_df)
        exp = self._array(X_df, self.exposure_col)
        cc = self._array(X_df, self.claim_count_col)
        target = self._resolve_target(X_df, y)
        self.mapping_ = {}
        for col in cols:
            edges = self._edges(X_df[col].to_numpy(dtype=float), target, exp, cc)
            self.mapping_[col] = edges
        self.bin_cols_ = cols
        return self

    def _resolve_target(self, X, y):
        t = self._array(X, self.target_col)
        e = self._array(X, self.exposure_col)
        if t is not None and e is not None:
            with np.errstate(divide="ignore", invalid="ignore"):
                pp = np.where(e > 0, t / e, 0.0)
            return pp
        if t is not None:
            return t
        return None if y is None else np.asarray(y, dtype=float)

    def _select_cols(self, X):
        if self.cols is not None:
            return [c for c in self.cols if c in X.columns]
        return [c for c in X.columns if pd.api.types.is_numeric_dtype(X[c])]

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
                edges = self._tree_edges(v, ym, w, cc)
            else:
                edges = self._quantile_edges(v, w)
        else:
            edges = self._quantile_edges(v, w)
        if target is not None and self._mono_direction() is not None:
            t = target[mask]
            edges = self._enforce_monotonic(edges, v, w, t)
        weights = w if w is not None else np.ones_like(v)
        return _merge_small_bins(v, weights, edges, self.min_exposure)

    def _mono_direction(self):
        """True=increasing, False=decreasing, None=off; raise on garbage."""
        m = self.monotonic
        if m is False or m is None:
            return None
        if m is True or (isinstance(m, str) and m == "increasing"):
            return True
        if isinstance(m, str) and m == "decreasing":
            return False
        raise ValueError(
            f"monotonic must be False, True, 'increasing', or 'decreasing'; got {m!r}"
        )

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
            edges = np.quantile(v, np.linspace(0, 1, self.max_bins + 1)[1:-1])
        else:
            order = np.argsort(v, kind="stable")
            vs, ws = v[order], w[order]
            cum = np.cumsum(ws)
            if cum[-1] <= 0:
                return np.array([])
            qs = np.linspace(0, cum[-1], self.max_bins + 1)[1:-1]
            idx = np.searchsorted(cum, qs, side="right")
            idx = np.clip(idx, 0, len(vs) - 1)
            edges = vs[idx]
        return np.unique(edges)

    def _tree_edges(self, v, y, w, cc):
        msl = max(1, int(self.min_claims)) if self.min_claims else 1
        tree = DecisionTreeRegressor(
            max_leaf_nodes=self.max_bins, min_samples_leaf=msl, random_state=self.random_state
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
            out[col] = self._labels(codes, edges) if was_df else codes.astype(float)
        return out if was_df else out.to_numpy()

    @staticmethod
    def _codes(values, edges):
        codes = np.searchsorted(edges, values, side="right")
        codes = np.where(np.isnan(values), len(edges) + 1, codes)
        return codes.astype(int)

    @staticmethod
    def _labels(codes, edges):
        n = len(edges)
        labels = np.empty(len(codes), dtype=object)
        for i, c in enumerate(codes):
            if c > n:
                labels[i] = "Missing"
            elif n == 0:
                labels[i] = "(-inf, inf)"
            elif c == 0:
                labels[i] = f"(-inf, {edges[0]:.4g}]"
            elif c >= n:
                labels[i] = f"({edges[-1]:.4g}, inf)"
            else:
                labels[i] = f"({edges[c - 1]:.4g}, {edges[c]:.4g}]"
        return labels

    def get_feature_names_out(self, input_features=None):
        if input_features is not None:
            return np.asarray(input_features)
        if hasattr(self, "feature_names_in_"):
            return self.feature_names_in_
        return np.asarray([f"x{i}" for i in range(self.n_features_in_)])

    def set_mapping(self, mapping):
        """Override fitted bin edges: ``{col: array_of_edges}``."""
        self.mapping_ = {c: np.asarray(e, dtype=float) for c, e in mapping.items()}
        self.bin_cols_ = list(mapping.keys())


class AutoGrouper(TransformerMixin, BaseEstimator):
    """Group categorical levels into credibility-stable groups.

    Strategies
    ----------
    "rare"        Levels below ``min_exposure`` / ``min_claims`` -> ``other_label``.
    "similarity"  Greedily merge adjacent levels (sorted by pure premium) into
                  groups that each meet the credibility floor.

    ``mapping_`` is ``{col: {original_level: group_label}}``. Unknown levels at
    transform time map to ``other_label``.

    Attributes
    ----------
    mapping_, group_cols_, n_features_in_, feature_names_in_.
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

    def _array(self, X, name):
        if name and name in X.columns:
            return X[name].to_numpy(dtype=float)
        return None

    def fit(self, X, y=None):
        validate_data(self, X, y=y, dtype=None, ensure_all_finite=False)
        X_df, _ = _to_frame(X)
        cols = self._select_cols(X_df)
        exp = self._array(X_df, self.exposure_col)
        cc = self._array(X_df, self.claim_count_col)
        target = self._resolve_target(X_df, y)
        self.mapping_ = {c: self._group_levels(X_df[c].to_numpy(), exp, cc, target) for c in cols}
        self.group_cols_ = cols
        return self

    def _resolve_target(self, X, y):
        t = self._array(X, self.target_col)
        e = self._array(X, self.exposure_col)
        if t is not None and e is not None:
            with np.errstate(divide="ignore", invalid="ignore"):
                return np.where(e > 0, t / e, 0.0)
        if t is not None:
            return t
        return None if y is None else np.asarray(y, dtype=float)

    def _select_cols(self, X):
        if self.cols is not None:
            return [c for c in self.cols if c in X.columns]
        return [c for c in X.columns if not pd.api.types.is_numeric_dtype(X[c])]

    def _level_stats(self, values, exp, cc, target):
        df = pd.DataFrame({"lvl": values})
        df["exp"] = exp if exp is not None else 1.0
        g = df.groupby("lvl", observed=True)
        stats = pd.DataFrame({"exp": g["exp"].sum()})
        if cc is not None:
            df["cc"] = cc
            stats["cc"] = df.groupby("lvl", observed=True)["cc"].sum()
        if target is not None:
            df["tgt"] = target
            stats["tgt"] = df.groupby("lvl", observed=True)["tgt"].sum()
            stats["pp"] = stats["tgt"] / stats["exp"].replace(0.0, np.nan)
        else:
            stats["pp"] = 0.0
        return stats

    def _group_levels(self, values, exp, cc, target):
        stats = self._level_stats(values, exp, cc, target)
        if self.strategy == "rare":
            return self._rare_mapping(stats)
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
        order = stats.sort_values("pp").index.tolist()
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

    def transform(self, X):
        validate_data(self, X, reset=False, dtype=None, ensure_all_finite=False)
        X_df, was_df = _to_frame(X)
        feature_names = getattr(self, "feature_names_in_", None)
        if feature_names is not None and all(c in X_df.columns for c in feature_names):
            X_df = X_df[feature_names]
        out = X_df.copy()
        for col, mp in self.mapping_.items():
            if col not in out.columns:
                continue
            out[col] = out[col].map(mp).fillna(self.other_label)
        return out if was_df else out.to_numpy()

    def get_feature_names_out(self, input_features=None):
        if input_features is not None:
            return np.asarray(input_features)
        if hasattr(self, "feature_names_in_"):
            return self.feature_names_in_
        return np.asarray([f"x{i}" for i in range(self.n_features_in_)])

    def set_mapping(self, mapping):
        """Override fitted level groups: ``{col: {level: group_label}}``."""
        self.mapping_ = {c: dict(m) for c, m in mapping.items()}
        self.group_cols_ = list(mapping.keys())
