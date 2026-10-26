"""Azoic CLI for training configurations and consuming trusted saved candidates.

Wraps the M5 + M6 + M7 pieces end-to-end:
  * ``azoic check`` -- read-only development config/data checks; no fitting.
  * ``azoic profile`` -- runs ``profile_features`` + ``screen_features`` and
    prints (or writes) the resulting screening table.
  * ``azoic fit`` -- loads an ``ExperimentConfig`` YAML, ``run_experiment``s
    it, prints a model card to stdout (and/or writes it to disk).
  * ``azoic compare`` -- compares saved runs without fitting, or trains configs.
  * ``azoic report`` / ``azoic predict`` -- report or score saved candidates.
  * ``azoic export-tariff`` -- runs a config, exports a named GLM or, with
    ``--distill``, an exportable GLM student of a positive-objective GBM.
  * ``azoic tune`` -- optuna hyperparameter search per model
    (``tune`` extra, M7 / v0.2 part 1) then a model card of the best fit.

ponytail: the CLI is a thin shell over ``workflow`` + ``reporting`` +
``tariff`` + ``tune``; no business logic lives here.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import typer
import yaml

from azoic.data import DatasetSpec, load_data
from azoic.profile import profile_features, screen_features
from azoic.reporting import comparison_table, model_card, tariff_review
from azoic.tariff import RevisedTariff
from azoic.tariff import distill_gbm as _distill_gbm
from azoic.tariff import export_tariff as _export_tariff
from azoic.workflow import (
    ExperimentConfig,
    _data_fingerprint,
    check_experiment,
    load_run,
    run_experiment,
    save_run,
)

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Azoic: non-life technical tariff (pure premium) modelling.",
)


@app.command()
def check(
    config: Path = typer.Option(..., "--config", help="Development ExperimentConfig YAML."),
) -> None:
    """Check config/data without fitting, dropping, repairing or writing files."""
    try:
        result = check_experiment(ExperimentConfig.from_yaml(config))
    except ValueError as error:
        raise typer.BadParameter(str(error)) from None
    typer.echo(json.dumps(result, indent=2))


@app.command()
def profile(
    data: str = typer.Option(..., "--data", help="Parquet file (or s3:// path) to profile."),
    target: str = typer.Option(..., "--target", help="Target column name (e.g. claim_amount)."),
    exposure: str = typer.Option(..., "--exposure", help="Exposure column name."),
    claim_count: str | None = typer.Option(None, "--claim-count", help="Claim-count column."),
    time_col: str | None = typer.Option(None, "--time-col", help="Time column."),
    out: Path | None = typer.Option(
        None, "--out", help="Write the screening table to CSV (default: print to stdout)."
    ),
) -> None:
    """Profile features in a portfolio and screen them for keep / bin / group / drop."""
    spec = DatasetSpec(
        target=target,
        exposure=exposure,
        claim_count=claim_count,
        time_col=time_col,
    )
    df = load_data(data, spec=spec)
    prof = profile_features(df.drop(columns=spec.required_columns()))
    screened = screen_features(prof)

    if out is not None:
        screened.to_csv(out, index=False)
        typer.echo(f"Wrote {len(screened)} rows to {out}")
        return

    typer.echo(screened.to_string(index=False))


@app.command()
def fit(
    config: Path = typer.Option(..., "--config", help="ExperimentConfig YAML."),
    out: Path | None = typer.Option(None, "--out", help="Write the model card markdown here."),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Do not print the card to stdout."),
    save: Path | None = typer.Option(None, "--save-run", help="Save fitted candidates (pickle)."),
) -> None:
    """Run all models in an ``ExperimentConfig`` YAML; produce a model card."""
    cfg = ExperimentConfig.from_yaml(config)
    if save is None:
        run = run_experiment(cfg)
    else:
        run, estimators = run_experiment(cfg, return_estimators=True)
        save_run(run, estimators, save)
    md = model_card(run)

    if out is not None:
        out.write_text(md, encoding="utf-8")
        typer.echo(f"Wrote markdown card to {out}")
    if not quiet:
        typer.echo(md)


@app.command()
def compare(
    configs: list[Path] | None = typer.Argument(
        None, help="ExperimentConfig YAML files to FIT and compare."
    ),
    saved_runs: list[Path] | None = typer.Option(
        None, "--run", help="Trusted saved run to compare without fitting (repeatable)."
    ),
    out: Path | None = typer.Option(
        None, "--out", help="Write the comparison table to CSV (default: print to stdout)."
    ),
) -> None:
    """Compare saved runs without fitting, or explicitly train positional configs."""
    if not configs and not saved_runs:
        raise typer.BadParameter("supply config paths to train or --run saved candidates")
    if configs and saved_runs:
        raise typer.BadParameter("choose config paths (fits) or --run (never fits), not both")
    runs = [load_run(path)[0] for path in saved_runs or []]
    runs += [run_experiment(ExperimentConfig.from_yaml(path)) for path in configs or []]
    rows = comparison_table(runs)

    if out is not None:
        rows.to_csv(out, index=False)
        typer.echo(f"Wrote {len(rows)} rows to {out}")
        return

    typer.echo(f"Azoic compare\n{rows.to_string(index=False)}")


@app.command()
def report(
    saved_runs: list[Path] = typer.Option(..., "--run", help="Trusted saved runs (repeatable)."),
    out: Path | None = typer.Option(None, "--out", help="Card file, or new review directory."),
    review: bool = typer.Option(
        False, "--review", help="Write full tariff review with CSVs/plots."
    ),
    data: Path | None = typer.Option(
        None, "--data", help="Original development Parquet for review."
    ),
    incumbent: Path | None = typer.Option(None, "--incumbent", help="ID/rate Parquet for review."),
    incumbent_rate: str | None = typer.Option(
        None, "--incumbent-rate", help="Technical rate column."
    ),
    selected: str | None = typer.Option(
        None, "--selected", help="Selected file-stem/model or incumbent."
    ),
    rationale: str | None = typer.Option(None, "--rationale", help="Human selection rationale."),
    limitations: list[str] | None = typer.Option(
        None, "--limitation", help="Review limits; repeatable."
    ),
    segments: list[str] | None = typer.Option(
        None, "--segment", help="Raw segment columns; repeatable."
    ),
) -> None:
    """Report frozen development candidates without fitting or recalibrating."""
    if review:
        if any(
            value is None for value in (out, data, incumbent, incumbent_rate, selected, rationale)
        ):
            raise typer.BadParameter(
                "--review requires --out, --data, --incumbent, --incumbent-rate, "
                "--selected and --rationale"
            )
        if len({path.stem for path in saved_runs}) != len(saved_runs):
            raise typer.BadParameter("review run file stems must be unique")
        assert out is not None and data is not None and incumbent is not None
        assert incumbent_rate is not None and selected is not None and rationale is not None
        try:
            path = tariff_review(
                {path.stem: load_run(path) for path in saved_runs},
                df=pd.read_parquet(data),
                incumbent=pd.read_parquet(incumbent),
                incumbent_rate=incumbent_rate,
                out=out,
                selected=selected,
                rationale=rationale,
                limitations=limitations or (),
                segments=segments or (),
            )
        except (ValueError, OSError) as error:
            raise typer.BadParameter(str(error)) from None
        typer.echo(f"Wrote tariff review to {path}")
        return
    if len(saved_runs) != 1 or any(
        value is not None
        for value in (data, incumbent, incumbent_rate, selected, rationale, limitations, segments)
    ):
        raise typer.BadParameter("multiple runs and review options require --review")
    run, _ = load_run(saved_runs[0])
    md = model_card(run)
    if out is not None:
        out.write_text(md, encoding="utf-8")
    else:
        typer.echo(md)


@app.command()
def predict(
    saved_run: Path = typer.Option(..., "--run", help="Trusted saved run (pickle)."),
    model: str = typer.Option(..., "--model", help="Saved fitted model name."),
    data: Path = typer.Option(..., "--data", help="Parquet predictors in scoring order."),
    out: Path = typer.Option(..., "--out", help="CSV containing pure-premium rates."),
) -> None:
    """Score a frozen candidate; outcomes and exposure are optional for rate prediction."""
    run, estimators = load_run(saved_run)
    if model not in estimators:
        raise typer.BadParameter(f"model {model!r} not in saved models {list(estimators)}")
    frame = pd.read_parquet(data)
    missing = sorted(set(run.feature_names) - set(frame.columns))
    if missing:
        raise typer.BadParameter(f"missing predictors: {missing}")
    rates = np.asarray(estimators[model].predict(frame[run.feature_names]), dtype=float)
    if rates.shape != (len(frame),) or not np.isfinite(rates).all():
        raise ValueError("saved model must predict one finite rate per row")
    result = pd.DataFrame({"predicted_rate": rates})
    if run.config.spec.id_col is not None:
        from azoic.data import _validate_record_ids

        id_col = run.config.spec.id_col
        if id_col not in frame:
            raise typer.BadParameter(f"missing record ID column: {id_col}")
        _validate_record_ids(frame[id_col])
        result.insert(0, id_col, frame[id_col].to_numpy())
    result.to_csv(out, index=False)


@app.command("export-tariff")
def export_tariff(
    config: Path | None = typer.Option(None, "--config", help="ExperimentConfig YAML to FIT."),
    saved_run: Path | None = typer.Option(None, "--run", help="Trusted saved run; never fits."),
    data: Path | None = typer.Option(
        None, "--data", help="Original development Parquet for saved-run recalibration."
    ),
    model: str = typer.Option(..., "--model", help="Name of the model to export."),
    out: Path = typer.Option(..., "--out", help="Output xlsx path."),
    distill: bool = typer.Option(
        False,
        "--distill",
        help="Distill a positive-objective GBM to an exportable GLM on the existing split.",
    ),
    recalibrate: bool = typer.Option(
        True,
        "--recalibrate/--no-recalibrate",
        help="Shift the base so the tariff reproduces the observed training "
        "total claim amount (default: on).",
    ),
) -> None:
    """Export a saved GLM without fitting, or train a config (including distillation)."""
    from sklearn.pipeline import Pipeline

    from azoic.models import RiskGBM, RiskGLM

    if (config is None) == (saved_run is None):
        raise typer.BadParameter("supply exactly one of --config (fits) or --run (never fits)")
    if saved_run is not None:
        if distill:
            raise typer.BadParameter("--distill fits a new student; use --config explicitly")
        run, ests = load_run(saved_run)
        if model in ests and isinstance(ests[model], RevisedTariff) and recalibrate:
            raise typer.BadParameter(
                "revised tariff calibration is recorded; pass --no-recalibrate"
            )
        cfg = run.config
        df = None
        if recalibrate:
            if data is None:
                raise typer.BadParameter(
                    "saved-run recalibration requires --data; or --no-recalibrate"
                )
            df = load_data(data, spec=cfg.spec)
            if _data_fingerprint(df) != run.data_fingerprint:
                raise typer.BadParameter(
                    "--data does not match saved development fingerprint/order"
                )
        elif data is not None:
            raise typer.BadParameter("--data is only used for saved-run recalibration")
    else:
        if data is not None:
            raise typer.BadParameter("--data requires --run; config supplies its data_path")
        assert config is not None
        cfg = ExperimentConfig.from_yaml(config)
        if model not in cfg.models:
            raise typer.BadParameter(f"model {model!r} not in config models {list(cfg.models)}")
        cfg = cfg.model_copy(update={"models": {model: cfg.models[model]}})
        df = load_data(cfg.data_path, spec=cfg.spec)
        run, ests = run_experiment(cfg, return_estimators=True, df=df)
    if model not in ests:
        raise typer.BadParameter(f"model {model!r} not in saved models {list(ests)}")
    est = ests[model]
    if isinstance(est, RevisedTariff):
        _export_tariff(est, out, recalibrate=False)
        typer.echo(f"Wrote revised tariff for {model} to {out}")
        return
    final_est = est.steps[-1][1] if isinstance(est, Pipeline) else est
    if isinstance(final_est, RiskGBM) and not distill:
        raise typer.BadParameter(
            f"model {model!r} ends in RiskGBM; use --config with --distill to train a GLM student."
        )
    if isinstance(final_est, RiskGLM) and distill:
        raise typer.BadParameter("--distill is only valid for a RiskGBM model")
    if not isinstance(final_est, (RiskGLM, RiskGBM)):
        raise typer.BadParameter(
            f"model {model!r} ends in {type(final_est).__name__}; export-tariff requires a RiskGLM."
        )

    train_indices = list(run.train_indices)
    X = df[list(est.feature_names_in_)] if df is not None else None
    y = df[cfg.spec.target] if df is not None else None
    X_train = X.iloc[train_indices] if X is not None else None
    if isinstance(final_est, RiskGBM):
        assert X is not None and X_train is not None
        exportable = _distill_gbm(
            est if isinstance(est, Pipeline) else final_est,
            X_train,
            X.iloc[list(run.test_indices)],
        )
        metrics = vars(exportable)["distillation_metrics_"]
        typer.echo(
            "Distillation fidelity: "
            f"teacher_student_deviance={metrics['teacher_student_deviance']:.6g}, "
            f"student_teacher_total_ratio={metrics['student_teacher_total_ratio']:.6g}"
        )

    else:
        exportable = est if isinstance(est, Pipeline) else final_est

    _export_tariff(
        exportable,
        out,
        X=X_train,
        y=y.iloc[train_indices] if y is not None else None,
        exposure_col=cfg.spec.exposure,
        recalibrate=recalibrate,
    )
    typer.echo(f"Wrote tariff for {model} to {out}")


@app.command()
def tune(
    config: Path = typer.Option(..., "--config", help="ExperimentConfig YAML."),
    trials: int | None = typer.Option(
        None,
        "--trials",
        help="Optuna trials per model; overrides YAML (default: YAML or 20).",
    ),
    calibration_penalty: float | None = typer.Option(
        None,
        "--calibration-penalty",
        help="O/P penalty weight; overrides YAML (default: YAML or 1.0).",
    ),
    out: Path | None = typer.Option(None, "--out", help="Write the model card markdown here."),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Do not print the card to stdout."),
    save: Path | None = typer.Option(None, "--save-run", help="Save selected fitted candidates."),
    best_config: Path | None = typer.Option(
        None, "--best-config", help="Write selected config YAML (running it trains again)."
    ),
) -> None:
    """Tune model hyperparameters with optuna, then write a model card of the best fit."""
    from azoic.tune import tune_experiment

    cfg = ExperimentConfig.from_yaml(config)
    options = {"return_estimators": True} if save is not None else {}
    result = tune_experiment(
        cfg, n_trials=trials, calibration_penalty=calibration_penalty, **options
    )
    if save is not None:
        assert result.estimators is not None
        save_run(result.run, result.estimators, save)
    if best_config is not None:
        selected = result.run.config.model_dump(mode="json")
        raw = selected["data_path"]
        if "://" not in raw:
            selected["data_path"] = str(Path(raw).resolve())
        best_config.write_text(yaml.safe_dump(selected, sort_keys=False), encoding="utf-8")
    md = model_card(result.run)

    for name, params in result.best_params.items():
        typer.echo(f"tuned {name}: " + ", ".join(f"{k}={v}" for k, v in params.items()))
    if out is not None:
        out.write_text(md, encoding="utf-8")
        typer.echo(f"Wrote markdown card to {out}")
    if not quiet:
        typer.echo(md)


@app.command("evaluate-final")
def evaluate_final_command(
    saved_run: Path = typer.Option(..., "--run", help="Trusted selected development run."),
    model: str = typer.Option(..., "--model", help="Frozen selected candidate."),
    data: Path = typer.Option(..., "--data", help="Reserved final-test Parquet only."),
    membership: Path = typer.Option(
        ..., "--membership", help="Saved JSON with final_test ID list."
    ),
    rationale: str = typer.Option(..., "--rationale", help="Human selection rationale."),
    out: Path = typer.Option(..., "--out", help="New evaluated saved run; source stays unchanged."),
) -> None:
    """Evaluate a frozen fit on the final test without fitting or recalibrating."""
    from azoic.workflow import evaluate_final

    try:
        run, estimators = load_run(saved_run)
        if out.exists():
            raise FileExistsError(f"evaluated output already exists: {out}")
        manifest = json.loads(membership.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or not isinstance(manifest.get("final_test"), list):
            raise ValueError("membership JSON requires a final_test ID list")
        evaluated = evaluate_final(
            run,
            estimators,
            model=model,
            df=pd.read_parquet(data),
            final_test_ids=manifest["final_test"],
            rationale=rationale,
        )
        save_run(evaluated, estimators, out)
    except (OSError, ValueError, TypeError) as error:
        raise typer.BadParameter(str(error)) from None
    typer.echo(model_card(evaluated))


@app.command("refit-production")
def refit_production_command(
    saved_run: Path = typer.Option(..., "--run", help="Trusted evaluated predecessor run."),
    data: Path = typer.Option(
        ..., "--data", help="Full original development + final-test Parquet."
    ),
    rationale: str = typer.Option(..., "--rationale", help="Human production-refit rationale."),
    out: Path = typer.Option(..., "--out", help="New production saved run."),
) -> None:
    """Explicitly refit selected parameters, freezing mappings; no holdout claim."""
    from azoic.workflow import refit_production

    try:
        run, estimators = load_run(saved_run)
        if out.exists():
            raise FileExistsError(f"production output already exists: {out}")
        production, fitted = refit_production(
            run,
            estimators,
            df=pd.read_parquet(data),
            rationale=rationale,
        )
        save_run(production, fitted, out)
    except (OSError, ValueError, TypeError) as error:
        raise typer.BadParameter(str(error)) from None
    typer.echo(model_card(production))


@app.command("export-production")
def export_production_command(
    saved_run: Path = typer.Option(..., "--run", help="Trusted production GLM run."),
    cases: Path = typer.Option(..., "--cases", help="Synthetic predictor Parquet; no real rows."),
    units: Path = typer.Option(
        ..., "--units", help="JSON object mapping every predictor to its unit."
    ),
    out: Path = typer.Option(..., "--out", help="New handoff directory."),
) -> None:
    """Write specification, workbook, fitted artifact, recipe and agreement cases."""
    from azoic.tariff import export_production

    try:
        run, estimators = load_run(saved_run)
        feature_units = json.loads(units.read_text(encoding="utf-8"))
        if not isinstance(feature_units, dict):
            raise ValueError("units JSON must be an object mapping feature names to units")
        path = export_production(
            run,
            estimators,
            cases=pd.read_parquet(cases),
            feature_units=feature_units,
            out=out,
        )
    except (OSError, ValueError, TypeError) as error:
        raise typer.BadParameter(str(error)) from None
    typer.echo(str(path))


if __name__ == "__main__":
    app()
