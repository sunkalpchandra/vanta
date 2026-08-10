"""Leave-one-out backtest of the analog engine.

For every resolved event in the reference corpus, hide it, ask find_analogs to
forecast it from the remaining events, and score the prediction against the
known outcome. This measures the standalone skill of the quant agent's analog
matching — the one component whose claims are fully checkable offline.
"""

from dataclasses import dataclass

from .analogs import find_analogs
from .scoring import brier_score, directional_accuracy, log_score


@dataclass
class BacktestResult:
    n_events: int
    n_covered: int  # events where the engine found analogs (didn't abstain)
    coverage: float
    accuracy: float | None
    brier: float | None
    log_score: float | None
    baseline_brier: float  # always-predict-base-rate benchmark


def run_backtest(reference_events: list[tuple[str, str, int]]) -> BacktestResult:
    pairs: list[tuple[float, int]] = []
    outcomes = [outcome for _, _, outcome in reference_events]
    base_rate = sum(outcomes) / len(outcomes)
    for i, (text, category, outcome) in enumerate(reference_events):
        remaining = reference_events[:i] + reference_events[i + 1 :]
        report = find_analogs(text, category, remaining)
        if report.hit_rate is None:
            continue  # abstained — counted against coverage, not accuracy
        clamped = min(0.95, max(0.05, report.hit_rate))
        pairs.append((clamped, outcome))
    n = len(reference_events)
    return BacktestResult(
        n_events=n,
        n_covered=len(pairs),
        coverage=round(len(pairs) / n, 4),
        accuracy=round(directional_accuracy(pairs), 4) if pairs else None,
        brier=round(brier_score(pairs), 4) if pairs else None,
        log_score=round(log_score(pairs), 4) if pairs else None,
        baseline_brier=round(brier_score([(base_rate, o) for o in outcomes]), 4),
    )
