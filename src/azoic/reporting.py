"""Development model cards, comparisons and frozen tariff-review bundles.

``model_card(run)`` returns a markdown summary of the experiment: config name,
dataset shape + features, and a per-model block with metrics + a calibration-
table preview.

"""

from __future__ import annotations

import warnings
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import azoic

__all__ = ["model_card", "comparison_table", "comparison_dashboard", "tariff_review"]


def _fmt(x: Any, dp: int = 4) -> str:
    """Format a scalar (number / NaN) for the card with ``dp`` decimals."""
    if x is None:
        return ""
    if isinstance(x, float) and pd.isna(x):
        return "nan"
    return f"{x:.{dp}f}"


def _df_preview_md(df: pd.DataFrame, n: int = 12) -> str:
    """Render the first ``n`` rows of ``df`` as a markdown table.

    ponytail: preview only; full calibration tables are written next to the
    card via the CLI when needed. Markdown tables on wide frames would overflow
    the rendered card.
    """
    cols = list(df.columns)
    head = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    rows = [head, sep]
    for row in df.head(n).itertuples(index=False, name=None):
        cells = []
        for v in row:
            if isinstance(v, float):
                cells.append(_fmt(v, 4))
            else:
                cells.append(str(v))
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def _metrics_block_md(name: str, kind: str, params: dict, metrics: dict) -> str:
    if any(key.endswith("_full") for key in metrics):
        return "\n".join(
            [
                f"### Model: `{name}` ({kind})",
                "",
                "Full training evidence only:",
                "",
                *[f"- {key}: {_fmt(value, 6)}" for key, value in metrics.items()],
            ]
        )
    lines = [
        f"### Model: `{name}` ({kind})",
        "",
        f"- params: `{params}`",
        f"- gini (train): {_fmt(metrics.get('gini_train'))}",
        f"- gini (test):  {_fmt(metrics.get('gini_test'))}",
        f"- O/P ratio (test):  {_fmt(metrics.get('op_ratio_test'))}",
        f"- deviance (test):  {_fmt(metrics.get('deviance_test'), 6)}",
        f"- D² (test):        {_fmt(metrics.get('d2_test'))}",
    ]
    return "\n".join(lines)


def model_card(run: azoic.Run) -> str:
    """Return the model card for ``run`` as markdown.

    Calibration tables are truncated to their first 12 rows -- a preview, not
    the full table; write full tables separately when all segments are needed.
    """
    cfg = run.config
    lines = [
        f"# Azoic model card -- {cfg.name}",
        "",
        "## Experiment",
        "",
        (
            "Production refit: full training evidence only; "
            "final-test results belong to the predecessor."
            if run.production
            else "Development evidence only: `test` means development validation, "
            "not the final test."
        ),
        "",
        f"- name: `{cfg.name}`",
        f"- data: `{cfg.data_path}`",
        f"- split: `{cfg.split}` (test_size={cfg.test_size}, random_state={cfg.random_state})",
        f"- target: `{cfg.spec.target}`  exposure: `{cfg.spec.exposure}`",
        f"- data fingerprint: `{run.data_fingerprint}`",
        f"- rows: {run.n_rows}  (train {run.n_train} / test {run.n_test})",
        f"- features ({len(run.feature_names)}): " + ", ".join(f"`{c}`" for c in run.feature_names),
        "",
    ]
    if run.final_evaluation:
        evaluation = run.final_evaluation
        lines.extend(
            [
                "## Frozen final evaluation",
                "",
                f"- selected: `{evaluation['model']}`; {evaluation['rationale']}",
                f"- fitted identity: `{evaluation['fitted_fingerprint']}`",
                f"- final data fingerprint: `{evaluation['data_fingerprint']}`",
                *[
                    f"- final {key}: {_fmt(value, 6)}"
                    for key, value in evaluation["metrics"].items()
                ],
                "",
            ]
        )
    if run.production:
        lines.extend(
            [
                "## Production lineage",
                "",
                f"- rationale: {run.production['rationale']}",
                "- predecessor fitted identity: "
                f"`{run.production['predecessor_fitted_fingerprint']}`",
                f"- mapping policy: {run.production['mapping_policy']}",
                f"- calibration policy: {run.production['calibration_policy']}",
                "",
            ]
        )
    if cfg.spec.protected_cols:
        lines.insert(
            -1,
            "- protected columns: " + ", ".join(f"`{c}`" for c in cfg.spec.protected_cols),
        )

    lines.extend(["## Portfolio basis", ""])
    for field in ("exposure_unit", "currency", "observation_period", "claim_valuation_basis"):
        lines.append(f"- {field}: {getattr(cfg.spec, field) or 'unrecorded'}")
    lines.append("- upstream adjustments: " + ("; ".join(cfg.spec.adjustments) or "none recorded"))
    lines.append(f"- record ID column: {cfg.spec.id_col or 'unrecorded'}")
    lines.append("")

    lines.append("## Provenance")
    lines.append("")
    lines.append(
        "- runtime versions: "
        + (
            ", ".join(f"{key}={value}" for key, value in run.runtime_versions.items())
            or "unrecorded"
        )
    )
    if run.tuning_settings:
        settings = run.tuning_settings
        lines.append(
            f"- effective tuning: {settings['n_trials']} trials/model, "
            f"calibration_penalty={settings['calibration_penalty']}, "
            f"random_state={settings['random_state']}"
        )
        for name, study in settings["models"].items():
            lines.append(f"- `{name}` sampler: `{study['sampler']}` (seed={study['seed']})")
    else:
        lines.append("- effective tuning: unrecorded (ordinary runs do not tune)")
    lines.append("")

    for name, res in run.models.items():
        lines.append(_metrics_block_md(name, res.kind, res.params, res.metrics))
        lines.append("")
        if res.revision:
            lines.append("- candidate: revised tariff; metrics use revised predictions")
            calibration = res.revision["calibration"]
            lines.append(f"- recorded calibration multiplier: {calibration['multiplier']:.12g}")
            for change in res.revision["changes"]:
                lines.append(
                    f"- {change['feature']} / {change['level']!r}: "
                    f"{change['original_factor']:.12g} -> {change['factor']:.12g}; "
                    f"{change['reason']}"
                )
            lines.append("")
        if res.resolved_params:
            lines.append(
                f"- constructor: `{res.resolved_params['class']}` "
                f"({len(res.resolved_params) - 1} settings in `resolved_params`)"
            )
        else:
            lines.append("- constructors: unrecorded")
        lines.append("")
        lines.append(
            "#### Calibration table (full training, first 12 rows)"
            if run.production
            else "#### Calibration table (test, first 12 rows)"
        )
        lines.append("")
        lines.append(_df_preview_md(res.calibration_table))
        lines.append("")
        if res.protected_calibration:
            lines.append("#### Protected-group calibration (outer test)")
            lines.append("")
            lines.append(
                "This held-out subgroup evidence is descriptive only; it is not a fairness "
                "threshold or legal assessment."
            )
            for column, table in res.protected_calibration.items():
                lines.extend(["", f"##### `{column}`", "", _df_preview_md(table), ""])
    return "\n".join(lines)


def comparison_table(runs: Iterable[azoic.Run]) -> pd.DataFrame:
    """Return all model metrics, warning once for mixed evaluation contexts.

    Dataset fingerprints, target/exposure columns, portfolio basis and holdout membership must
    match for direct comparisons. Holdout order does not matter. Mixed contexts
    remain available for descriptive comparison; the warning names affected runs.
    """
    runs = list(runs)
    contexts = [
        (
            bool(run.production),
            run.data_fingerprint,
            run.config.spec.target,
            run.config.spec.exposure,
            run.config.spec.exposure_unit,
            run.config.spec.currency,
            run.config.spec.observation_period,
            run.config.spec.claim_valuation_basis,
            tuple(run.config.spec.adjustments),
            frozenset(run.test_indices),
        )
        for run in runs
    ]
    mismatched = [
        runs[i].config.name
        for i, context in enumerate(contexts[1:], start=1)
        if context != contexts[0]
    ]
    if mismatched:
        warnings.warn(
            f"Runs {[runs[0].config.name, *mismatched]!r} have different evaluation contexts "
            "(dataset fingerprints, target/exposure definitions, portfolio basis, "
            "or holdout membership); "
            "metrics are descriptive and cannot be compared directly.",
            UserWarning,
            stacklevel=2,
        )
    rows = [
        {
            "config": run.config.name,
            "model": name,
            "kind": result.kind,
            "evidence": "production_refit (full training)"
            if run.production
            else ("development (revised tariff)" if result.revision else "development"),
            **result.metrics,
        }
        for run in runs
        for name, result in run.models.items()
    ]
    columns = [
        "config",
        "model",
        "kind",
        "evidence",
        "gini_train",
        "gini_test",
        "op_ratio_test",
        "deviance_test",
        "d2_test",
    ]
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=pd.Index(columns))


def comparison_dashboard(runs: Iterable[azoic.Run]) -> str:
    """Return standalone Plotly HTML with the same context warning as the table."""
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError as error:
        raise ImportError(
            "comparison_dashboard requires the `plot` extra (`uv sync --extra plot`)"
        ) from error

    runs = list(runs)
    if any(run.production for run in runs):
        raise ValueError("production refits have full-training metrics; use comparison_table")
    table = comparison_table(runs)
    labels = table["config"].astype(str) + " / " + table["model"].astype(str)
    labels.loc[table["evidence"] == "development (revised tariff)"] += " (revised)"
    figure = make_subplots(
        rows=2,
        cols=3,
        specs=[[{"type": "table", "colspan": 3}, None, None], [{}, {}, {}]],
        subplot_titles=("Development metrics", "", "", "Gini (test)", "O/P ratio", "Deviance"),
        row_heights=[0.45, 0.55],
        vertical_spacing=0.12,
    )
    figure.add_trace(
        go.Table(
            header={"values": list(table.columns)},
            cells={"values": [table[column].tolist() for column in table.columns]},
        ),
        row=1,
        col=1,
    )
    for column, title, col in (
        ("gini_test", "Gini (test)", 1),
        ("op_ratio_test", "O/P ratio", 2),
        ("deviance_test", "Deviance", 3),
    ):
        figure.add_trace(
            go.Bar(x=labels, y=table[column], name=title, showlegend=False),
            row=2,
            col=col,
        )
    figure.update_layout(height=800, title="Azoic model comparison")
    return figure.to_html(full_html=True, include_plotlyjs=True)


def _review_metrics(amount, rate, exposure):
    from azoic.metrics import _tweedie_scores, gini, op_ratio

    deviance, d2 = (
        _tweedie_scores(amount, rate, exposure)
        if (rate > 0).all()
        else (float("inf"), float("nan"))
    )
    return {
        "gini": gini(amount, rate, exposure),
        "o_p_ratio": op_ratio(amount, rate, exposure),
        "deviance": deviance,
        "d2": d2,
    }


def _review_changes(snapshots, keys):
    rows = []
    baseline = next(iter(snapshots))
    original = snapshots[baseline]
    for candidate, current in snapshots.items():
        for key in dict.fromkeys([*original, *current]):
            before, after = original.get(key), current.get(key)
            if before != after:
                rows.append(
                    {
                        "baseline": baseline,
                        "candidate": candidate,
                        **dict(zip(keys, key, strict=True)),
                        "before": before,
                        "after": after,
                    }
                )
    return pd.DataFrame(rows, columns=["baseline", "candidate", *keys, "before", "after"])


def tariff_review(
    runs: Mapping[str, tuple[azoic.Run, Mapping[str, Any]]],
    *,
    df: pd.DataFrame,
    incumbent: pd.DataFrame,
    incumbent_rate: str,
    out: str | Path,
    selected: str,
    rationale: str,
    limitations: Iterable[str] = (),
    segments: Iterable[str] = (),
) -> Path:
    """Write a development tariff review to a new directory; return ``review.md``.

    ``runs`` maps unique aliases to the (Run, fitted-estimator dictionary) pairs
    returned by run_experiment/load_run/revise_run. Candidate labels are
    ``alias/model``; ``selected`` must be one of these or ``incumbent``. Supply
    already recalibrated/revised artifacts: reporting never fits or recalibrates.

    All runs must have the same fingerprint, portfolio basis, recorded unique IDs
    and training/validation membership. ``df`` is the original development frame
    in its saved order. ``incumbent`` has that same ID column and exactly the same
    IDs (any order), plus finite nonnegative annual technical pure-premium rates.
    ``segments`` names raw columns shared across candidates (default: first run
    predictors); protected columns are included automatically. CSVs contain every
    row; Markdown tables preview twelve rows. Existing output directories are
    rejected and failed writes leave no partial bundle. Bundles include record
    IDs/outcomes; handle them as data.
    """
    import tempfile

    import matplotlib.pyplot as plt
    from matplotlib.figure import Figure

    from azoic.data import _validate_record_ids
    from azoic.metrics import calibration_table
    from azoic.models import RiskGLM
    from azoic.plots import plot_lift, plot_one_way
    from azoic.tariff import RevisedTariff, _factors_frame, _pipeline_parts, extract_tariff
    from azoic.workflow import _data_fingerprint, _validate_candidates, _validate_portfolio

    if not runs or not rationale.strip():
        raise ValueError("review requires candidates and a nonempty selection rationale")
    out = Path(out)
    if out.exists():
        raise FileExistsError(f"review output already exists: {out}")
    if any(run.production or run.final_evaluation for run, _ in runs.values()):
        raise ValueError("tariff review requires development candidates before final evaluation")
    reference = next(iter(runs.values()))[0]
    spec = reference.config.spec
    id_col = spec.id_col
    if id_col is None or not reference.record_ids:
        raise ValueError("review requires a declared id_col and recorded development IDs")
    _validate_portfolio(reference.config, df)
    if _data_fingerprint(df) != reference.data_fingerprint:
        raise ValueError("review data must match saved development fingerprint/order")
    if tuple(df[id_col]) != reference.record_ids:
        raise ValueError("review record IDs must match the saved development IDs")
    train, valid = reference.train_indices, reference.test_indices
    if (
        not train
        or not valid
        or len(train) != reference.n_train
        or len(valid) != reference.n_test
        or reference.n_rows != len(df)
        or len(train) + len(valid) != len(df)
        or set(train) & set(valid)
        or set(train) | set(valid) != set(range(len(df)))
    ):
        raise ValueError("review requires complete, disjoint recorded split membership")
    if (
        not incumbent.columns.is_unique
        or id_col not in incumbent
        or incumbent_rate not in incumbent
    ):
        raise ValueError("incumbent requires unique columns including record IDs and rate")
    if incumbent_rate == id_col:
        raise ValueError("incumbent rate must be a separate column from record IDs")
    _validate_record_ids(incumbent[id_col])
    if set(incumbent[id_col]) != set(reference.record_ids):
        raise ValueError("incumbent record ID membership must match development exactly")
    incumbent_values = incumbent.set_index(id_col).loc[list(reference.record_ids), incumbent_rate]
    incumbent_values = incumbent_values.to_numpy(dtype=float)
    if not np.isfinite(incumbent_values).all() or (incumbent_values < 0).any():
        raise ValueError("incumbent rates must be finite and nonnegative")
    segments = list(segments) or list(reference.feature_names)
    segments = list(dict.fromkeys([*segments, *spec.protected_cols]))
    if any(column not in df for column in segments):
        raise ValueError("review segments must name columns in the development frame")
    if spec.time_col is not None:
        periods = df[spec.time_col]
        if periods.isna().any() or (
            pd.api.types.is_numeric_dtype(periods) and not np.isfinite(periods).all()
        ):
            raise ValueError("review time column must contain finite, nonmissing periods")
    basis = spec.model_dump(exclude={"excluded_cols"})
    candidates = {}
    metadata, mapping_frames, factor_frames, revisions = [], [], [], []
    mapping_snapshots, factor_snapshots = {}, {}
    for alias, (run, estimators) in runs.items():
        if (
            run.data_fingerprint != reference.data_fingerprint
            or run.config.spec.model_dump(exclude={"excluded_cols"}) != basis
            or run.record_ids != reference.record_ids
            or set(run.train_indices) != set(train)
            or set(run.test_indices) != set(valid)
            or len(run.train_indices) != len(train)
            or len(run.test_indices) != len(valid)
            or run.n_rows != reference.n_rows
            or run.n_train != reference.n_train
            or run.n_test != reference.n_test
        ):
            raise ValueError(
                "review runs must share development identity, basis and split membership"
            )
        if not run.models:
            raise ValueError("review requires at least one model per run")
        _validate_candidates(run, estimators)
        for name, estimator in estimators.items():
            label = f"{alias}/{name}"
            if label in candidates:
                raise ValueError("review candidate labels must be unique")
            rate = np.asarray(estimator.predict(df[list(estimator.feature_names_in_)]), dtype=float)
            if rate.shape != (len(df),) or not np.isfinite(rate).all() or (rate < 0).any():
                raise ValueError(
                    "review candidates must predict one finite nonnegative rate per row"
                )
            candidates[label] = rate
            revision = run.models[name].revision
            scale = "fitted"
            if revision:
                scale = "revised" if revision["changes"] else "recalibrated"
                if not revision["calibration"]["applied"]:
                    scale = "revised structural"
                revisions.extend({"candidate": label, **change} for change in revision["changes"])
            source = estimator.source if isinstance(estimator, RevisedTariff) else estimator
            backend, _, mapping = _pipeline_parts(source, None)
            mapping_frames.append(mapping.assign(candidate=label))
            mapping_snapshots[label] = {
                (row["feature"], row["role"]): repr(row)
                for row in mapping.fillna("").to_dict("records")
            }
            factors = pd.DataFrame(columns=["feature", "level", "multiplicative_factor"])
            factor_status = "not a log-link GLM tariff"
            if isinstance(backend, RiskGLM):
                try:
                    tariff = (
                        estimator.tariff
                        if isinstance(estimator, RevisedTariff)
                        else extract_tariff(backend)
                    )
                    factors = _factors_frame(tariff)
                    factors["level_type"] = factors["level"].map(lambda level: type(level).__name__)
                    factors["level"] = factors["level"].map(repr)
                    factors = pd.concat(
                        [
                            pd.DataFrame(
                                [
                                    {
                                        "feature": "(base)",
                                        "level": "",
                                        "level_type": "",
                                        "multiplicative_factor": tariff["base_rate"],
                                    }
                                ]
                            ),
                            factors,
                        ],
                        ignore_index=True,
                    )
                    factor_status = "available"
                except ValueError as error:
                    factor_status = str(error)
            factor_frames.append(factors.assign(candidate=label))
            factor_snapshots[label] = {
                (row["feature"], row["level"]): row["multiplicative_factor"]
                for row in factors.to_dict("records")
            }
            metadata.append(
                {
                    "candidate": label,
                    "scale": scale,
                    "calibration_multiplier": revision.get("calibration", {}).get(
                        "multiplier", 1.0
                    ),
                    "factor_status": factor_status,
                    "data_fingerprint": run.data_fingerprint,
                    "config": run.config.model_dump_json(),
                    "runtime_versions": repr(run.runtime_versions),
                    "tuning_settings": repr(run.tuning_settings),
                    "revision": repr(revision),
                }
            )
    if selected not in {"incumbent", *candidates}:
        raise ValueError(f"selected must be incumbent or one of {list(candidates)}")
    exposure = df[spec.exposure].to_numpy(dtype=float)
    amount = df[spec.target].to_numpy(dtype=float)
    count = df[spec.claim_count].to_numpy(dtype=float) if spec.claim_count else None
    if not np.isfinite(
        [exposure.sum(), amount.sum(), count.sum() if count is not None else 0]
    ).all():
        raise ValueError("review portfolio totals must be finite")
    partition = np.full(len(df), "training", dtype=object)
    partition[list(valid)] = "validation"
    records, totals, calibration, segment_tables, temporal, distribution = [], [], [], [], [], []
    plots = []
    for label, rate in {"incumbent": incumbent_values, **candidates}.items():
        delta = rate - incumbent_values
        percentage = np.full(len(df), np.nan)
        with np.errstate(over="ignore", invalid="ignore"):
            np.divide(delta, incumbent_values, out=percentage, where=incumbent_values > 0)
            percentage *= 100
            predicted_amount = rate * exposure
            predicted_total = predicted_amount.sum()
        if not np.isfinite(percentage[incumbent_values > 0]).all() or not np.isfinite(
            predicted_total
        ):
            raise ValueError("review rate changes and predicted totals must be finite")
        record = pd.DataFrame(
            {
                "candidate": label,
                "record_id": df[id_col].to_numpy(),
                "record_id_type": df[id_col].map(lambda value: type(value).__name__).to_numpy(),
                "partition": partition,
                "exposure": exposure,
                "claim_amount": amount,
                "claim_count": count if count is not None else np.nan,
                "rate": rate,
                "predicted_claim_amount": predicted_amount,
                "incumbent_rate": incumbent_values,
                "delta_rate": delta,
                "percentage_change": percentage,
            }
        )
        records.append(record)
        for split, positions in (
            ("development", np.arange(len(df))),
            ("training", np.asarray(train)),
            ("validation", np.asarray(valid)),
        ):
            a, r, e = amount[positions], rate[positions], exposure[positions]
            totals.append(
                {
                    "candidate": label,
                    "partition": split,
                    "n_records": len(positions),
                    "exposure": e.sum(),
                    "claim_amount": a.sum(),
                    "claim_count": count[positions].sum() if count is not None else np.nan,
                    "predicted_claim_amount": np.dot(r, e),
                    "incumbent_claim_amount": np.dot(incumbent_values[positions], e),
                    "changed_records": np.count_nonzero(delta[positions]),
                    "changed_exposure": e[delta[positions] != 0].sum(),
                    **_review_metrics(a, r, e),
                }
            )
            part = record.iloc[positions]
            buckets = pd.cut(part.percentage_change, [-np.inf, -50, -20, -5, 0, 5, 20, 50, np.inf])
            buckets = buckets.astype(object).where(part.percentage_change != 0, "unchanged")
            change = part.assign(
                change_band=buckets.astype(object).where(
                    part.percentage_change.notna(), "undefined (zero incumbent)"
                )
            )
            dist = (
                change.groupby("change_band", observed=True, sort=False)
                .agg(
                    n_records=("rate", "size"),
                    exposure=("exposure", "sum"),
                    claim_amount=("claim_amount", "sum"),
                    claim_count=("claim_count", lambda values: values.sum(min_count=1)),
                    predicted_claim_amount=("predicted_claim_amount", "sum"),
                )
                .reset_index()
            )
            distribution.append(dist.assign(candidate=label, partition=split))
            # ponytail: raw levels can be large; add shared bins when measured reviews need them.
            for column in segments:
                table = calibration_table(
                    a,
                    r,
                    e,
                    groups=df.iloc[positions][column],
                    claim_count=count[positions] if count is not None else None,
                )
                table = table.rename(columns={"group": "level"})
                base = calibration_table(
                    a, incumbent_values[positions], e, groups=df.iloc[positions][column]
                )
                table["incumbent_claim_amount"] = base.predicted_claim_amount.to_numpy()
                impacts = (
                    part.assign(level=df.iloc[positions][column].to_numpy())
                    .groupby("level", observed=True, dropna=False)["delta_rate"]
                    .agg(changed_records=lambda x: np.count_nonzero(x))
                )
                table = table.merge(impacts, on="level", validate="one_to_one")
                table["delta_claim_amount"] = (
                    table.predicted_claim_amount - table.incumbent_claim_amount
                )
                table["percentage_change"] = (
                    100
                    * table.delta_claim_amount
                    / table.incumbent_claim_amount.where(table.incumbent_claim_amount > 0)
                )
                segment_tables.append(
                    table.assign(candidate=label, partition=split, feature=column)
                )
            if spec.time_col is not None:
                table = calibration_table(
                    a,
                    r,
                    e,
                    groups=df.iloc[positions][spec.time_col],
                    claim_count=count[positions] if count is not None else None,
                )
                table = table.rename(columns={"group": "period"})
                period_values = df.iloc[positions][spec.time_col].to_numpy()
                scores = [
                    _review_metrics(
                        a[period_values == period],
                        r[period_values == period],
                        e[period_values == period],
                    )
                    for period in table.period
                ]
                temporal.append(
                    pd.concat(
                        [table, pd.DataFrame(scores).drop(columns="o_p_ratio")], axis=1
                    ).assign(candidate=label, partition=split)
                )
        v = np.asarray(valid)
        table = calibration_table(
            amount[v], rate[v], exposure[v], claim_count=count[v] if count is not None else None
        )
        calibration.append(table.assign(candidate=label, partition="validation"))
        plots.append((label, table))
    tables = {
        "candidates": pd.DataFrame(metadata),
        "records": pd.concat(records, ignore_index=True),
        "totals": pd.DataFrame(totals),
        "calibration": pd.concat(calibration, ignore_index=True),
        "segments": pd.concat(segment_tables, ignore_index=True)
        if segment_tables
        else pd.DataFrame(
            columns=["candidate", "partition", "feature", "level", "exposure", "claim_amount"]
        ),
        "temporal": pd.concat(temporal, ignore_index=True)
        if temporal
        else pd.DataFrame(columns=["candidate", "partition", "period", "exposure", "claim_amount"]),
        "rate_changes": pd.concat(distribution, ignore_index=True),
        "mappings": pd.concat(mapping_frames, ignore_index=True),
        "mapping_changes": _review_changes(mapping_snapshots, ["feature", "role"]),
        "factors": pd.concat(factor_frames, ignore_index=True),
        "factor_changes": _review_changes(factor_snapshots, ["feature", "level"]),
        "revision_history": pd.DataFrame(
            revisions,
            columns=["candidate", "feature", "level", "original_factor", "factor", "reason"],
        ),
    }
    tables["mappings"] = tables["mappings"].reindex(
        columns=[
            "candidate",
            "feature",
            "role",
            "dtype",
            "levels",
            "n_levels",
            "reference_level",
            "mapping",
            "interval_closure",
            "missing_destination",
            "unseen_destination",
        ]
    )
    tables["factors"] = tables["factors"].reindex(
        columns=[
            "candidate",
            "feature",
            "level",
            "level_type",
            "multiplicative_factor",
            "application",
        ]
    )
    lines = [
        "# Azoic tariff review",
        "",
        "## Decision",
        "",
        f"Selected: **{selected}**",
        "",
        rationale,
        "",
        "## Scope and interpretation",
        "",
        (
            "Development evidence only: validation is reused during selection; "
            "it is not final-test evidence."
        ),
        "Reporting only scores frozen candidates; it never fits or recalibrates.",
        (
            f"Rates are technical pure premium in {spec.currency or 'unrecorded currency'} "
            "per exposure-year; period costs equal rate × exposure (years)."
        ),
        (
            "Incumbent rates must use the same technical basis; commercial "
            "loadings and upstream claim adjustments are outside this report."
        ),
        f"Record ID column: `{id_col}`. Data fingerprint: `{reference.data_fingerprint}`.",
        f"Portfolio basis: `{basis}`.",
        (
            "O/P is aggregate observed amount / sum(rate × exposure). Gini "
            "measures ranking only; deviance uses exposure weights and power=1.5."
        ),
        (
            "Zero incumbent rates have undefined percentage changes (blank CSV "
            "cells), including zero-to-zero. Absolute rate changes remain defined."
        ),
        (
            "Change bands are descriptive, not approval thresholds. Changed "
            "records use exact unrounded rate inequality."
        ),
        (
            "Segment levels are shared raw values, not candidate-specific "
            "learned groups. Missing levels retain their totals."
        ),
        (
            "Mapping/factor changes compare each candidate with the first "
            "candidate; complete snapshots and revision reasons accompany them."
        ),
        (
            "Markdown tables preview twelve rows; linked CSV tables contain "
            "every row at full precision."
        ),
        "",
        "## Limitations",
        "",
        (
            "No universal approval rule or superiority claim is implied. Human "
            "actuarial review and final evaluation remain required."
        ),
        (
            "Bundles contain record IDs and outcomes. Store and share with the "
            "same controls as the development portfolio."
        ),
        "Temporal diagnostics unavailable: no time_col declared."
        if spec.time_col is None
        else (
            "Temporal tables describe the declared periods; random-split "
            "periods are descriptive, not forward validation."
        ),
        "Claim counts unavailable."
        if count is None
        else "Claim counts are included where supplied.",
        "",
        *[f"- {item}" for item in limitations],
        "",
        "## Candidate scales",
        "",
        "The incumbent is the supplied annual technical rate. "
        "Fitted rates are raw model predictions; "
        "recalibrated and revised rates include only their already recorded multiplier. "
        "A revised structural tariff has no calibration applied.",
        "",
        _df_preview_md(
            tables["candidates"][["candidate", "scale", "calibration_multiplier", "factor_status"]]
        ),
        "",
    ]
    with tempfile.TemporaryDirectory(dir=out.parent) as temporary:
        staging = Path(temporary) / "review"
        staging.mkdir()
        for name, table in tables.items():
            table.to_csv(staging / f"{name}.csv", index=False)
            lines.extend(
                [
                    f"## {name.replace('_', ' ').title()}",
                    "",
                    f"[Complete table ({len(table)} rows)]({name}.csv)",
                    "",
                ]
            )
            if name in {
                "totals",
                "rate_changes",
                "mapping_changes",
                "factor_changes",
                "revision_history",
            }:
                lines.extend([_df_preview_md(table), ""])
        lines.extend(["## Validation plots", ""])
        for i, (label, table) in enumerate(plots):
            ax = plot_lift(table, label=label, title=f"{label}: development validation")
            try:
                assert isinstance(ax.figure, Figure)
                ax.figure.savefig(staging / f"lift-{i}.png", bbox_inches="tight")
            finally:
                plt.close(ax.figure)
            lines.extend(
                [
                    (
                        f"![Observed and predicted annual pure premium by risk "
                        f"decile: {label}](lift-{i}.png)"
                    ),
                    "",
                ]
            )
        for i, column in enumerate(segments):
            table = tables["segments"]
            table = table[
                (table.candidate == selected)
                & (table.partition == "validation")
                & (table.feature == column)
            ].copy()
            table["level_label"] = table.level.map(str)
            ax = plot_one_way(table, label=selected, title=f"{selected}: {column}")
            try:
                assert isinstance(ax.figure, Figure)
                ax.figure.savefig(staging / f"segment-{i}.png", bbox_inches="tight")
            finally:
                plt.close(ax.figure)
            lines.extend(
                [
                    (
                        f"![Observed and predicted annual pure premium by "
                        f"{column}, selected candidate](segment-{i}.png)"
                    ),
                    "",
                ]
            )
        (staging / "review.md").write_text("\n".join(lines), encoding="utf-8")
        staging.rename(out)
    return out / "review.md"
