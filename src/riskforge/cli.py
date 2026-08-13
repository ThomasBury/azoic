"""RiskForge CLI (Typer): ``profile`` / ``fit`` / ``compare`` / ``export-tariff`` /
``tune``.

Wraps the M5 + M6 + M7 pieces end-to-end:
  * ``riskforge profile`` -- runs ``profile_features`` + ``screen_features`` and
    prints (or writes) the resulting screening table.
  * ``riskforge fit`` -- loads an ``ExperimentConfig`` YAML, ``run_experiment``s
    it, prints a model card to stdout (and/or writes md + html).
  * ``riskforge compare`` -- runs one or more configs and prints a side-by-side
    per-model metrics table.
  * ``riskforge export-tariff`` -- runs a config, picks a named GLM, writes a
    multiplicative-tariff xlsx whose base reproduces the portfolio observed
    total pure premium (M6).
  * ``riskforge tune`` -- optuna hyperparameter search per model
    (``tune`` extra, M7 / v0.2 part 1) then a model card of the best fit.

ponytail: the CLI is a thin shell over ``workflow`` + ``reporting`` +
``tariff`` + ``tune``; no business logic lives here.
"""

from __future__ import annotations

from pathlib import Path

import typer

from riskforge.data import DatasetSpec, load_data
from riskforge.profile import profile_features, screen_features
from riskforge.reporting import comparison_dashboard, comparison_table, model_card
from riskforge.tariff import export_tariff as _export_tariff
from riskforge.workflow import ExperimentConfig, run_experiment

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="RiskForge: non-life technical tariff (pure premium) modelling.",
)


@app.command()
def profile(
    data: Path = typer.Option(..., "--data", help="Parquet file (or s3:// path) to profile."),
    target: str = typer.Option(..., "--target", help="Target column name (e.g. claim_amount)."),
    exposure: str = typer.Option(..., "--exposure", help="Exposure column name."),
    claim_count: str | None = typer.Option(None, "--claim-count", help="Claim-count column."),
    time_col: str | None = typer.Option(None, "--time-col", help="Time column."),
    id_col: str | None = typer.Option(None, "--id-col", help="Policy id column."),
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
        id_col=id_col,
    )
    df = load_data(data, spec=spec)
    prof = profile_features(df)
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
    out_html: Path | None = typer.Option(None, "--out-html", help="Write an HTML model card."),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Do not print the card to stdout."),
) -> None:
    """Run all models in an ``ExperimentConfig`` YAML; produce a model card."""
    cfg = ExperimentConfig.from_yaml(config)
    run = run_experiment(cfg)
    md = model_card(run, fmt="md")

    if out is not None:
        out.write_text(md, encoding="utf-8")
        typer.echo(f"Wrote markdown card to {out}")
    if out_html is not None:
        out_html.write_text(model_card(run, fmt="html"), encoding="utf-8")
        typer.echo(f"Wrote HTML card to {out_html}")
    if not quiet:
        typer.echo(md)


@app.command()
def compare(
    configs: list[Path] = typer.Argument(
        ..., help="One or more ExperimentConfig YAML files to run and compare."
    ),
    out: Path | None = typer.Option(
        None, "--out", help="Write the comparison table to CSV (default: print to stdout)."
    ),
    out_html: Path | None = typer.Option(
        None, "--out-html", help="Write a standalone comparison dashboard."
    ),
) -> None:
    """Run multiple configs and print a side-by-side per-model metric table."""
    runs = [run_experiment(ExperimentConfig.from_yaml(cfg_path)) for cfg_path in configs]
    rows = comparison_table(runs)

    if out is not None:
        rows.to_csv(out, index=False)
        typer.echo(f"Wrote {len(rows)} rows to {out}")
    if out_html is not None:
        out_html.write_text(comparison_dashboard(runs), encoding="utf-8")
        typer.echo(f"Wrote dashboard to {out_html}")
    if out is not None or out_html is not None:
        return

    typer.echo(f"RiskForge compare\n{rows.to_string(index=False)}")


@app.command("export-tariff")
def export_tariff(
    config: Path = typer.Option(..., "--config", help="ExperimentConfig YAML."),
    model: str = typer.Option(..., "--model", help="Name of the (GLM) model to export."),
    out: Path = typer.Option(..., "--out", help="Output xlsx path."),
    recalibrate: bool = typer.Option(
        True,
        "--recalibrate/--no-recalibrate",
        help="Shift the base so the tariff reproduces the observed portfolio "
        "total claim amount (default: on).",
    ),
) -> None:
    """Run an ``ExperimentConfig``, pick the named GLM, write a multiplicative-tariff xlsx."""
    from riskforge.models import RiskGLM

    cfg = ExperimentConfig.from_yaml(config)
    run, ests = run_experiment(cfg, return_estimators=True)
    if model not in ests:
        raise typer.BadParameter(
            f"model {model!r} not in config models {list(ests)}; check the YAML `models:` keys."
        )
    est = ests[model]
    final_est = est.steps[-1][1] if hasattr(est, "steps") else est
    if not isinstance(final_est, RiskGLM):
        raise typer.BadParameter(
            f"model {model!r} ends in {type(final_est).__name__}; export-tariff requires a RiskGLM."
        )

    df = load_data(cfg.data_path, spec=cfg.spec)
    X = df[list(est.feature_names_in_)]
    y = df[cfg.spec.target]

    _export_tariff(
        est,
        out,
        X=X,
        y=y,
        exposure_col=cfg.spec.exposure,
        recalibrate=recalibrate,
    )
    typer.echo(f"Wrote tariff for {model} to {out}")


@app.command()
def tune(
    config: Path = typer.Option(..., "--config", help="ExperimentConfig YAML."),
    trials: int = typer.Option(
        20, "--trials", help="Optuna trials per model (tune extra required)."
    ),
    calibration_penalty: float = typer.Option(
        1.0,
        "--calibration-penalty",
        help="Penalty weight on |1 - op_ratio_test|; scale to deviance magnitude.",
    ),
    out: Path | None = typer.Option(None, "--out", help="Write the model card markdown here."),
    out_html: Path | None = typer.Option(None, "--out-html", help="Write an HTML model card."),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Do not print the card to stdout."),
) -> None:
    """Tune model hyperparameters with optuna, then write a model card of the best fit."""
    from riskforge.tune import tune_experiment

    cfg = ExperimentConfig.from_yaml(config)
    result = tune_experiment(cfg, n_trials=trials, calibration_penalty=calibration_penalty)
    md = model_card(result.run, fmt="md")

    for name, params in result.best_params.items():
        typer.echo(f"tuned {name}: " + ", ".join(f"{k}={v:.4g}" for k, v in params.items()))
    if out is not None:
        out.write_text(md, encoding="utf-8")
        typer.echo(f"Wrote markdown card to {out}")
    if out_html is not None:
        out_html.write_text(model_card(result.run, fmt="html"), encoding="utf-8")
        typer.echo(f"Wrote HTML card to {out_html}")
    if not quiet:
        typer.echo(md)


if __name__ == "__main__":
    app()
