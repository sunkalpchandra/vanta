from app.data import REFERENCE_EVENTS
from app.quant.backtest import run_backtest


def test_backtest_runs_over_the_corpus():
    result = run_backtest(REFERENCE_EVENTS)
    assert result.n_events == len(REFERENCE_EVENTS)
    assert 0 < result.n_covered <= result.n_events
    assert 0 < result.coverage <= 1
    assert result.brier is not None and 0 <= result.brier <= 1
    assert result.log_score is not None and result.log_score > 0


def test_backtest_is_deterministic():
    a = run_backtest(REFERENCE_EVENTS)
    b = run_backtest(REFERENCE_EVENTS)
    assert a == b


def test_backtest_honest_about_baseline():
    """The report must always carry the no-skill benchmark so the analog
    engine's number can't be quoted without its context."""
    result = run_backtest(REFERENCE_EVENTS)
    assert 0 < result.baseline_brier <= 0.25 + 1e-9
