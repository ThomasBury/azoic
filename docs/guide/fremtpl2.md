# freMTPL2 tutorial

The freMTPL2 tutorial is the complete Azoic workflow on the public French motor
third-party-liability portfolio. It is an executable Quarto document rendered
as one standalone HTML page.

[Open the tutorial](https://thomasbury.github.io/azoic/tutorial/fremtpl2.html){ .md-button .md-button--primary }
[View the QMD source](https://github.com/ThomasBury/azoic/blob/main/examples/fremtpl2.qmd){ .md-button }

## Prerequisites for a local render

From a checkout, install the tutorial environment and ensure Quarto is on
`PATH`:

```bash
uv sync --group demo --extra mlops --extra plot
quarto --version
just demo
```

The render fetches pinned OpenML datasets 41214 and 41215, so this page is the
only onboarding path that needs network access. Generated data, caches,
workbooks, reports, MLflow state, and `examples/fremtpl2.html` stay ignored.

## What it covers

- deterministic cleaning, sampling, and portfolio validation;
- profiling, screening, binning, and grouping;
- direct Tweedie GLM and LightGBM candidates;
- Poisson-frequency times Gamma-severity modelling;
- held-out Gini, Lorenz, lift, calibration, one-way, double-lift, and
  actual-versus-predicted diagnostics;
- outcome-free scoring checks;
- model cards, comparison output, MLflow logging, and tariff export.

!!! note "Rendering boundary"

    The tutorial keeps its existing Quarto rendering and styling. Zensical links
    to the generated HTML but does not parse or restyle the QMD.

## Related guides

- [Actuarial workflow](actuarial-workflow.md) explains why the evaluation
  sequence is structured this way.
- [Data profiling and preprocessing](data-preprocessing.md) documents the
  mapping-first preprocessing controls.
- [Diagnostics and visualization](diagnostics-visualization.md) provides
  focused plotting recipes.
- [Reporting and operations](operations.md) covers model cards, tuning, MLflow,
  and tariff export.
