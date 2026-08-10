"""Property-based checks over the quant core: invariants that must hold for
arbitrary inputs, not just the examples the unit tests picked."""

from hypothesis import given
from hypothesis import strategies as st

from app.quant.bayes import agreement_confidence, pool, shrink_to_base_rate
from app.quant.scoring import brier_score, calibration_bins, log_score, murphy_decomposition

probabilities = st.floats(min_value=0.001, max_value=0.999)
weights = st.floats(min_value=0.05, max_value=5.0)
estimates = st.lists(st.tuples(probabilities, weights), min_size=1, max_size=8)
outcome_pairs = st.lists(st.tuples(probabilities, st.integers(min_value=0, max_value=1)), min_size=1, max_size=60)


@given(estimates)
def test_pool_stays_in_bounds_and_within_hull(ests):
    pooled = pool(ests)
    assert 0 < pooled < 1
    lo = min(p for p, _ in ests)
    hi = max(p for p, _ in ests)
    assert lo - 1e-9 <= pooled <= hi + 1e-9  # log-odds pooling never extrapolates


@given(probabilities, probabilities, st.floats(min_value=0.0, max_value=1.0))
def test_shrinkage_is_a_bounded_interpolation(p, base, strength):
    shrunk = shrink_to_base_rate(p, base, strength)
    lo, hi = sorted((p, base))
    assert lo - 1e-9 <= shrunk <= hi + 1e-9


@given(estimates)
def test_confidence_always_in_scale(ests):
    confidence = agreement_confidence(ests, pool(ests))
    assert 1.0 <= confidence <= 10.0


@given(outcome_pairs)
def test_scores_bounded(pairs):
    assert 0.0 <= brier_score(pairs) <= 1.0
    assert log_score(pairs) >= 0.0


@given(outcome_pairs)
def test_calibration_bins_conserve_every_pair(pairs):
    bins = calibration_bins(pairs)
    assert sum(b.count for b in bins) == len(pairs)
    for b in bins:
        if b.count:
            assert 0.0 <= b.observed_rate <= 1.0
            assert 0.0 <= b.mean_predicted <= 1.0


@given(outcome_pairs)
def test_murphy_components_bounded(pairs):
    d = murphy_decomposition(pairs)
    assert d.reliability >= 0.0
    assert d.resolution >= 0.0
    assert 0.0 <= d.uncertainty <= 0.25
