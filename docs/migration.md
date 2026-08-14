# Migration to Azoic 0.4

Replace `riskforge` imports and commands with `azoic`. Existing pickle or joblib estimators must be refitted because old module paths no longer resolve; no compatibility package or CLI alias is provided.
