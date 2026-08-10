"""Weighted Bayesian aggregation in log-odds space.

Each agent contributes a probability estimate and a weight. Estimates are
pooled as a weighted average of log-odds (a logarithmic opinion pool), then
shrunk toward the category base rate to correct for overconfidence.
"""

import math

EPS = 1e-6


def clamp(p: float, lo: float = EPS, hi: float = 1 - EPS) -> float:
    return max(lo, min(hi, p))


def logit(p: float) -> float:
    p = clamp(p)
    return math.log(p / (1 - p))


def inv_logit(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def pool(estimates: list[tuple[float, float]]) -> float:
    """Pool (probability, weight) pairs via weighted log-odds averaging."""
    if not estimates:
        raise ValueError("pool() requires at least one estimate")
    total_w = sum(w for _, w in estimates)
    if total_w <= 0:
        raise ValueError("weights must sum to a positive value")
    z = sum(logit(p) * w for p, w in estimates) / total_w
    return inv_logit(z)


def shrink_to_base_rate(p: float, base_rate: float, strength: float = 0.15) -> float:
    """Shrink an estimate toward the base rate in log-odds space.

    strength=0 returns p unchanged; strength=1 returns the base rate.
    """
    if not 0 <= strength <= 1:
        raise ValueError("strength must be in [0, 1]")
    z = (1 - strength) * logit(p) + strength * logit(base_rate)
    return inv_logit(z)


def agreement_confidence(estimates: list[tuple[float, float]], pooled: float) -> float:
    """Confidence (0-10) from inter-agent agreement and distance from 50%.

    Low dispersion between agents and a pooled estimate far from coin-flip
    both increase confidence; disagreement between agents reduces it.
    """
    if not estimates:
        return 0.0
    total_w = sum(w for _, w in estimates)
    z_pooled = logit(pooled)
    variance = sum(w * (logit(p) - z_pooled) ** 2 for p, w in estimates) / total_w
    # Caps chosen so the score spans [1.0, 9.5]: unanimous + decisive agents
    # can reach the top of the scale, heavy disagreement bottoms out at 1.
    dispersion_penalty = min(4.5, variance * 1.6)
    decisiveness = min(4.0, abs(z_pooled) * 1.6)
    score = 5.5 + decisiveness - dispersion_penalty
    return round(max(1.0, min(10.0, score)), 1)
