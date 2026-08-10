"""Forecast scoring: Brier score, directional accuracy, calibration bins.

Operates on (probability, outcome) pairs where outcome is 0 or 1. These are
the metrics behind the leaderboard, the stats endpoint, and the reliability
diagram.
"""

from dataclasses import dataclass


def brier_score(pairs: list[tuple[float, int]]) -> float:
    """Mean squared error of probabilities vs outcomes. Lower is better;
    0.25 is the score of always answering 50%."""
    if not pairs:
        raise ValueError("brier_score requires at least one pair")
    return sum((p - o) ** 2 for p, o in pairs) / len(pairs)


def directional_accuracy(pairs: list[tuple[float, int]]) -> float:
    """Share of forecasts on the right side of 50%."""
    if not pairs:
        raise ValueError("directional_accuracy requires at least one pair")
    return sum(1 for p, o in pairs if (p >= 0.5) == bool(o)) / len(pairs)


@dataclass
class CalibrationBin:
    """One bucket of a reliability diagram."""

    lo: float
    hi: float
    mid: float
    count: int
    mean_predicted: float | None
    observed_rate: float | None


def calibration_bins(pairs: list[tuple[float, int]], n_bins: int = 10) -> list[CalibrationBin]:
    """Bucket forecasts by predicted probability and compare against the
    observed YES rate per bucket. A perfectly calibrated forecaster's points
    sit on the diagonal (mean_predicted == observed_rate)."""
    if n_bins < 2:
        raise ValueError("n_bins must be at least 2")
    width = 1.0 / n_bins
    # Assign by index, not by comparing against accumulated float edges:
    # 3 * 0.1 == 0.30000000000000004, which would drop p=0.3 into the bin
    # below its nominal boundary. int(p * n_bins) keeps round quotes (0.3,
    # 0.7) in the bin they open; p=1.0 folds into the final bin.
    grouped: dict[int, list[tuple[float, int]]] = {}
    for p, o in pairs:
        idx = min(int(p * n_bins), n_bins - 1)
        grouped.setdefault(idx, []).append((p, o))

    bins: list[CalibrationBin] = []
    for i in range(n_bins):
        lo, hi = i * width, (i + 1) * width
        members = grouped.get(i, [])
        if members:
            mean_pred = sum(p for p, _ in members) / len(members)
            observed = sum(o for _, o in members) / len(members)
        else:
            mean_pred = observed = None
        bins.append(
            CalibrationBin(
                lo=round(lo, 4),
                hi=round(hi, 4),
                mid=round(lo + width / 2, 4),
                count=len(members),
                mean_predicted=None if mean_pred is None else round(mean_pred, 4),
                observed_rate=None if observed is None else round(observed, 4),
            )
        )
    return bins
