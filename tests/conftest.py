"""Synthetic actuarially-plausible portfolio fixtures for tests and demos.

The generator is deterministic (`seed=42`) and exposes enough signal that GLM,
GBM, and frequency-severity models can learn a non-trivial ranking on it later.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def make_synthetic_portfolio(n: int = 20000, seed: int = 42) -> pd.DataFrame:
    """Return a seeded DataFrame with exposure, features, claim_count, claim_amount.

    Columns:
        exposure       -- policy exposure weight, ~Uniform(0.5, 1.0)
        driver_age     -- int in [18, 90)
        vehicle_age    -- int in [0, 25)
        region         -- categorical {urban, suburban, rural}
        vehicle_brand  -- categorical {A, B, C, D}
        claim_count    -- Poisson(lambda * exposure * frequency_relativities)
        claim_amount   -- gamma-distributed severity * claim_count (>0 only)
    """
    rng = np.random.default_rng(seed)

    exposure = rng.uniform(0.5, 1.0, size=n)
    driver_age = rng.integers(18, 90, size=n)
    vehicle_age = rng.integers(0, 25, size=n)
    region = rng.choice(np.array(["urban", "suburban", "rural"]), size=n, p=[0.4, 0.4, 0.2])
    vehicle_brand = rng.choice(np.array(["A", "B", "C", "D"]), size=n, p=[0.3, 0.3, 0.2, 0.2])

    # Ground-truth frequency relativities.
    age_freq = np.where(driver_age < 25, 1.6, np.where(driver_age > 65, 1.3, 1.0))
    region_freq = np.where(region == "urban", 1.4, np.where(region == "rural", 0.6, 1.0))
    vehage_freq = 1.0 + 0.03 * vehicle_age
    lam = 0.10 * exposure * age_freq * region_freq * vehage_freq
    claim_count = rng.poisson(lam)

    # Severity: Gamma per claim, brand D heavier. claim_amount = severity * count.
    pos = claim_count > 0
    claim_amount = np.zeros(n, dtype=float)
    sev_mean = np.where(vehicle_brand == "D", 4500.0, 3000.0)
    shape = 3.0
    per_claim_sev = rng.gamma(shape, sev_mean / shape, size=n)
    claim_amount[pos] = per_claim_sev[pos] * claim_count[pos]

    return pd.DataFrame(
        {
            "exposure": exposure,
            "driver_age": driver_age,
            "vehicle_age": vehicle_age,
            "region": region,
            "vehicle_brand": vehicle_brand,
            "claim_count": claim_count,
            "claim_amount": claim_amount,
        }
    )


@pytest.fixture(scope="session")
def synthetic_portfolio() -> pd.DataFrame:
    return make_synthetic_portfolio()
