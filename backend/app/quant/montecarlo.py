"""Monte Carlo simulation over a Beta-distributed belief.

The pooled probability plus an evidence-strength pseudo-count defines a Beta
posterior; sampling it yields a credible interval and tail risks without
assuming the point estimate is exact.
"""

import random
import statistics
from dataclasses import dataclass


@dataclass
class SimulationResult:
    mean: float
    ci_low: float
    ci_high: float
    p_above_market: float
    samples: int


def simulate(
    probability: float,
    evidence_strength: float,
    market_probability: float,
    n: int = 20_000,
    seed: int = 7,
) -> SimulationResult:
    """Sample a Beta(alpha, beta) posterior around `probability`.

    evidence_strength acts as a pseudo-sample size: more independent evidence
    means a tighter posterior. Deterministic for a fixed seed.
    """
    if not 0 < probability < 1:
        raise ValueError("probability must be strictly between 0 and 1")
    strength = max(2.0, evidence_strength)
    alpha = probability * strength
    beta = (1 - probability) * strength
    rng = random.Random(seed)
    draws = [rng.betavariate(alpha, beta) for _ in range(n)]
    draws.sort()
    return SimulationResult(
        mean=statistics.fmean(draws),
        ci_low=draws[int(0.05 * n)],
        ci_high=draws[int(0.95 * n)],
        p_above_market=sum(d > market_probability for d in draws) / n,
        samples=n,
    )
