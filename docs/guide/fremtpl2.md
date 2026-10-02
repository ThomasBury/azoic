# freMTPL2 tutorial

The tutorial series is the complete Azoic workflow as an executable Quarto
book: the freMTPL2 chapters walk the public French motor third-party-liability
portfolio from claims data to an exported multiplicative tariff, and later
chapters cover the remaining library features on freMTPL2 subsets or small
synthetic portfolios.

[Open the tutorial series](https://thomasbury.github.io/azoic/tutorial/index.html){ .md-button .md-button--primary }
[View the QMD sources](https://github.com/ThomasBury/azoic/tree/main/examples){ .md-button }

## Prerequisites for a local render

From a checkout, install the tutorial environment and ensure Quarto is on
`PATH`:

```bash
uv sync --group demo --extra mlops --extra plot --extra tune
quarto --version
just demo
```

The render fetches pinned OpenML datasets 41214 and 41215 for the freMTPL2
chapters, so those pages are the only onboarding path that needs network
access. Generated data, caches, workbooks, reports, MLflow state, and the
rendered book stay under ignored `examples/_artifacts/` and `examples/_book/`.
Chapters refit their own models and create every artifact they need. The loader
reuses its cleaned cache and regenerates the sampled portfolio parquet. Changing
the claim cap or cleaning rules requires rebuilding the cleaned cache; see the
book's portfolio chapter. Shared functions in `_shared.qmd` are tutorial helpers,
not public Azoic APIs.

Read index → portfolio → experiments → essential diagnostics → scoring and
tariff review first. Stop after scoring if policy rates are the deliverable;
stop after direct GLM tariff review if a workbook is enough. Distillation,
diagnostic derivations, and all subsequent chapters are optional recipes.

## Chapter map

1. **Index** — what the series builds, conventions, and setup.
2. **Portfolio ingestion and review** — pinned OpenML fetch, deterministic
   cleaning, portfolio summary, profiling, and screening.
3. **Two reproducible experiments** — direct Tweedie GLM baseline, raw
   LightGBM benchmark, representative fitted bins/groups, and optional full
   inspection with exact partitions.
4. **Held-out diagnostics** — frozen training recalibration, held-out
   Gini/Lorenz/lift/calibration and age one-ways, then evidence and open review
   questions. Derivations, grouped views, double-lift, and residuals are optional.
5. **Scoring and tariff export** — outcome-free scoring and a direct GLM
   workbook; optional structured GBM teacher and distillation, application using the fitted
   preprocessing pipeline, fidelity, and four-candidate claims evaluation.
6. **Reporting, MLflow, and the CLI** — model cards, comparison table and
   dashboard, local MLflow logging, and the `azoic` CLI walkthrough.
7. **Frequency–severity alternatives** — Poisson × Gamma GLM and GBM variants
   on the same partition.
8. **Configuration-driven tuning** — `tune_experiment` with a typed YAML
   `tuning:` block on a bounded subset; the outer holdout stays untouched.
9. **Temporal stability diagnostics** — synthetic period portfolio,
   `temporal_split` experiment, and reconciled `stability_table` rows.
10. **Protected-group audit** — `protected_cols` subgroup calibration evidence
    on a synthetic protected attribute.
11. **Manual tariff recipes** — `extract_tariff`, `apply_tariff`, and
    `recalibrate_for_total` factor revisions. Regularization guidance appears
    earlier with experiment configuration.

!!! note "Rendering boundary"

    The tutorial keeps its existing Quarto rendering and styling. Zensical links
    to the generated book pages but does not parse or restyle the QMD.

A full sequential render checks all 11 pages. It does not prove each chapter
can run alone; a separate synthetic fresh-process check covers reporting setup
through MLflow logging. The Pages workflow renders after pushes to main and
is not a pre-merge tutorial gate.

## Related guides

- [Actuarial workflow](actuarial-workflow.md) explains why the evaluation
  sequence is structured this way.
- [Data profiling and preprocessing](data-preprocessing.md) documents the
  mapping-first preprocessing controls.
- [Diagnostics and visualization](diagnostics-visualization.md) provides
  focused plotting recipes.
- [Reporting and operations](operations.md) covers model cards, tuning, MLflow,
  and tariff export.
