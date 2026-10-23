"""Azoic: scikit-learn-compatible toolkit for non-life technical tariff modelling.

Public names are loaded on first access. ``import azoic`` and ``dir(azoic)``
do not import modelling, plotting, or optional tracking/tuning backends.
"""

from importlib import import_module

__version__ = "0.5.0"

_EXPORTS = {
    name: module
    for module, names in {
        "data": ("DatasetSpec", "load_data", "MIN_EXPOSURE", "EXPOSURE_FLOOR"),
        "profile": ("profile_features", "screen_features"),
        "preprocessing": ("AutoBinner", "AutoGrouper"),
        "models": ("RiskGLM", "RiskGBM", "FrequencySeverityModel"),
        "metrics": (
            "gini",
            "lorenz",
            "Lorenz",
            "calibration_table",
            "stability_table",
            "one_way_table",
            "double_lift_table",
            "op_ratio",
            "mean_tweedie_deviance",
            "mean_poisson_deviance",
            "mean_gamma_deviance",
        ),
        "validation": ("make_strata", "temporal_split"),
        "plots": (
            "AZOIC_STYLE",
            "OKABE_ITO",
            "OBSERVED",
            "EXPOSURE",
            "azoic_style",
            "model_colors",
            "plot_lorenz",
            "plot_lift",
            "plot_calibration",
            "plot_one_way",
            "plot_double_lift",
            "plot_actual_vs_predicted",
        ),
        "workflow": (
            "FloatDistribution",
            "IntDistribution",
            "CategoricalDistribution",
            "ParameterDistribution",
            "TuningSpec",
            "PreprocessingSpec",
            "ModelSpec",
            "ExperimentConfig",
            "ModelResult",
            "Run",
            "run_experiment",
        ),
        "tariff": (
            "distill_gbm",
            "export_tariff",
            "extract_tariff",
            "apply_tariff",
            "recalibrate_for_total",
        ),
        "reporting": ("model_card", "comparison_table", "comparison_dashboard"),
        "mlops": ("log_run",),
        "tune": ("tune_experiment", "TuneResult"),
    }.items()
    for name in names
}
__all__ = ["__version__", *_EXPORTS]


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f".{_EXPORTS[name]}", __name__), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
