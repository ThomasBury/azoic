"""Thin mlflow run logger for a ``riskforge.workflow.Run`` (lazy mlflow import).

mlflow is a heavy optional dep and lives in the ``mlops`` extra
(``uv sync --extra mlops``). ``log_run`` imports it lazily and raises with a
clear pointer when the extra is missing.

The whole M6 mlops surface is one function: a ``Run`` already carries
everything worth logging -- the config fingerprint (top-level), per-model
params, per-model metrics, and the calibration tables (CLI can persist those
as artifacts before calling ``log_run``).

ponytail: ceiling -- no fluent API, no custom logger classes; if cross-run
comparison / autolog / model registry wiring lands at v0.3, add then.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from riskforge.workflow import Run

__all__ = ["log_run", "MissingMLOpsExtra"]


class MissingMLOpsExtra(ImportError):
    """Raised by ``log_run`` when the ``mlops`` extra (mlflow) is not installed."""


def _import_mlflow():
    try:
        import mlflow
    except ImportError as e:
        raise MissingMLOpsExtra(
            "riskforge.mlops.log_run requires the `mlops` extra "
            "(`uv sync --extra mlops`); mlflow could not be imported."
        ) from e
    return mlflow


def _flatten_params(prefix: str, params: dict) -> dict:
    """mlflow flattens Frozenset keys internally but rejects None values and
    truncates long values (max 6000 chars). Cast to str, keep None as the
    empty string so the param still records the key."""
    out: dict = {}
    for k, v in params.items():
        if v is None:
            out[f"{prefix}.{k}"] = ""
        else:
            out[f"{prefix}.{k}"] = str(v)
    return out


def log_run(
    run: Run,
    *,
    tracking_uri: str | None = None,
    experiment_name: str | None = None,
    run_name: str | None = None,
    artifacts: Iterable[str | Path] | None = None,
    artifact_path: str = "artifacts",
) -> str:
    """Log ``run`` to mlflow and return the mlflow ``run_id`` (string).

    Records:
      * Top-level params: config name, split, test_size, random_state,
        n_rows / n_train / n_test (prefixed ``experiment.*``).
      * Per-model: ``<model>.kind`` + one ``<model>.params.<k>`` per param,
        plus one ``<model>.<metric>`` metric per metric (NaN metrics are
        skipped -- mlflow rejects NaN since 3.x).
      * Artifacts: every path in ``artifacts`` (file or directory).
    """
    mlflow = _import_mlflow()

    if tracking_uri is not None:
        mlflow.set_tracking_uri(tracking_uri)
    if experiment_name is not None:
        mlflow.set_experiment(experiment_name)

    with mlflow.start_run(run_name=run_name or run.config.name) as handle:
        # Top-level experiment fingerprint.
        mlflow.log_params(
            {
                "experiment.name": run.config.name,
                "experiment.split": run.config.split,
                "experiment.test_size": float(run.config.test_size),
                "experiment.random_state": int(run.config.random_state),
                "experiment.n_rows": int(run.n_rows),
                "experiment.n_train": int(run.n_train),
                "experiment.n_test": int(run.n_test),
                "experiment.feature_names": ", ".join(run.feature_names),
            }
        )

        # Per-model params + metrics.
        for name, res in run.models.items():
            mlflow.log_params({f"{name}.kind": res.kind})
            mlflow.log_params(_flatten_params(f"{name}.params", res.params))
            metrics_out: dict = {}
            for k, v in res.metrics.items():
                fv = float(v)
                if fv == fv and fv not in (float("inf"), float("-inf")):
                    metrics_out[f"{name}.{k}"] = fv
            if metrics_out:
                mlflow.log_metrics(metrics_out)

        # Artifacts.
        if artifacts is not None:
            for art in artifacts:
                p = Path(art)
                if not p.exists():
                    raise FileNotFoundError(f"log_run: artifact not found: {p}")
                if p.is_file():
                    mlflow.log_artifact(str(p), artifact_path=artifact_path)
                else:
                    # Upload the directory's contents under "<artifact_path>/<dir_name>"
                    # so the directory name is preserved in the artifact tree
                    # (mlflow.log_artifacts uploads contents flat under artifact_path).
                    mlflow.log_artifacts(
                        str(p), artifact_path=f"{artifact_path}/{p.name}"
                    )

        return str(handle.info.run_id)
