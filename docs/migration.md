# Migration to Azoic 0.4

Azoic 0.4 is the package and CLI rename from `riskforge`. The migration is
deliberately direct: update source configuration, refit serialized estimators,
and verify the same held-out workflow.

## Required changes

- Replace `riskforge` imports with `azoic`.
- Replace `riskforge` commands with `azoic`.
- Refit pickle or joblib estimators because their old module paths no longer
  resolve.
- Update automation to the canonical documentation and tutorial URLs.

No compatibility package or CLI alias is provided.

[Install Azoic 0.4](getting-started/installation.md){ .md-button .md-button--primary }
[Run a first model](getting-started/first-model.md){ .md-button }
[Review configuration and CLI](reference/configuration-cli.md){ .md-button }
