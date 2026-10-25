"""Azoic: scikit-learn-compatible toolkit for non-life technical tariff modelling.

Public names are loaded on first access. ``import azoic`` and ``dir(azoic)``
do not import modelling, plotting, or optional tracking/tuning backends.
"""

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .data import EXPOSURE_FLOOR as EXPOSURE_FLOOR
    from .data import MIN_EXPOSURE as MIN_EXPOSURE
    from .data import DatasetSpec as DatasetSpec
    from .data import load_data as load_data
    from .data import split_portfolio as split_portfolio
    from .metrics import Lorenz as Lorenz
    from .metrics import calibration_table as calibration_table
    from .metrics import double_lift_table as double_lift_table
    from .metrics import gini as gini
    from .metrics import lorenz as lorenz
    from .metrics import mean_gamma_deviance as mean_gamma_deviance
    from .metrics import mean_poisson_deviance as mean_poisson_deviance
    from .metrics import mean_tweedie_deviance as mean_tweedie_deviance
    from .metrics import one_way_table as one_way_table
    from .metrics import op_ratio as op_ratio
    from .metrics import stability_table as stability_table
    from .mlops import log_run as log_run
    from .models import FrequencySeverityModel as FrequencySeverityModel
    from .models import RiskGBM as RiskGBM
    from .models import RiskGLM as RiskGLM
    from .plots import AZOIC_STYLE as AZOIC_STYLE
    from .plots import EXPOSURE as EXPOSURE
    from .plots import OBSERVED as OBSERVED
    from .plots import OKABE_ITO as OKABE_ITO
    from .plots import azoic_style as azoic_style
    from .plots import model_colors as model_colors
    from .plots import plot_actual_vs_predicted as plot_actual_vs_predicted
    from .plots import plot_calibration as plot_calibration
    from .plots import plot_double_lift as plot_double_lift
    from .plots import plot_lift as plot_lift
    from .plots import plot_lorenz as plot_lorenz
    from .plots import plot_one_way as plot_one_way
    from .preprocessing import AutoBinner as AutoBinner
    from .preprocessing import AutoGrouper as AutoGrouper
    from .profile import profile_features as profile_features
    from .profile import screen_features as screen_features
    from .reporting import comparison_dashboard as comparison_dashboard
    from .reporting import comparison_table as comparison_table
    from .reporting import model_card as model_card
    from .tariff import apply_tariff as apply_tariff
    from .tariff import distill_gbm as distill_gbm
    from .tariff import export_tariff as export_tariff
    from .tariff import extract_tariff as extract_tariff
    from .tariff import recalibrate_for_total as recalibrate_for_total
    from .tune import TuneResult as TuneResult
    from .tune import tune_experiment as tune_experiment
    from .validation import make_strata as make_strata
    from .validation import temporal_split as temporal_split
    from .workflow import CategoricalDistribution as CategoricalDistribution
    from .workflow import ExperimentConfig as ExperimentConfig
    from .workflow import FloatDistribution as FloatDistribution
    from .workflow import IntDistribution as IntDistribution
    from .workflow import ModelResult as ModelResult
    from .workflow import ModelSpec as ModelSpec
    from .workflow import ParameterDistribution as ParameterDistribution
    from .workflow import PreprocessingSpec as PreprocessingSpec
    from .workflow import Run as Run
    from .workflow import TuningSpec as TuningSpec
    from .workflow import check_experiment as check_experiment
    from .workflow import run_experiment as run_experiment

__version__ = "0.5.0"

_EXPORTS = {
    name: module
    for module, names in {
        "data": ("DatasetSpec", "load_data", "split_portfolio", "MIN_EXPOSURE", "EXPOSURE_FLOOR"),
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
            "check_experiment",
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


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f".{_EXPORTS[name]}", __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
