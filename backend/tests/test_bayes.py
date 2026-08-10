import math

import pytest

from app.quant.bayes import agreement_confidence, inv_logit, logit, pool, shrink_to_base_rate


def test_logit_inverse_roundtrip():
    for p in (0.01, 0.25, 0.5, 0.9, 0.99):
        assert inv_logit(logit(p)) == pytest.approx(p, abs=1e-9)


def test_pool_single_estimate_is_identity():
    assert pool([(0.7, 1.0)]) == pytest.approx(0.7, abs=1e-9)


def test_pool_equal_weights_is_symmetric_around_half():
    assert pool([(0.3, 1.0), (0.7, 1.0)]) == pytest.approx(0.5, abs=1e-9)


def test_pool_respects_weights():
    pooled = pool([(0.9, 3.0), (0.1, 1.0)])
    assert pooled > 0.5  # heavier weight pulls the pool its way
    assert pooled == pytest.approx(inv_logit((logit(0.9) * 3 + logit(0.1)) / 4))


def test_pool_rejects_empty_and_zero_weight():
    with pytest.raises(ValueError):
        pool([])
    with pytest.raises(ValueError):
        pool([(0.5, 0.0)])


def test_shrinkage_moves_toward_base_rate():
    shrunk = shrink_to_base_rate(0.9, base_rate=0.4, strength=0.5)
    assert 0.4 < shrunk < 0.9
    assert shrink_to_base_rate(0.9, 0.4, strength=0.0) == pytest.approx(0.9)
    assert shrink_to_base_rate(0.9, 0.4, strength=1.0) == pytest.approx(0.4)


def test_confidence_rewards_agreement_and_decisiveness():
    agree = [(0.8, 1.0), (0.82, 1.0), (0.78, 1.0)]
    disagree = [(0.95, 1.0), (0.3, 1.0), (0.6, 1.0)]
    c_agree = agreement_confidence(agree, pool(agree))
    c_disagree = agreement_confidence(disagree, pool(disagree))
    assert c_agree > c_disagree
    assert 1.0 <= c_disagree <= c_agree <= 10.0


def test_confidence_spans_the_scale():
    """Regression: unanimous, decisive agents must be able to score near the
    top of the 10-point scale (the old caps silently limited it to 8.5)."""
    unanimous = [(0.97, 1.0), (0.96, 1.0), (0.97, 1.0)]
    assert agreement_confidence(unanimous, pool(unanimous)) >= 9.0
    coin_flip_fight = [(0.95, 1.0), (0.05, 1.0)]
    assert agreement_confidence(coin_flip_fight, pool(coin_flip_fight)) == 1.0


def test_pool_extreme_inputs_stay_finite():
    pooled = pool([(0.999999, 1.0), (0.000001, 1.0)])
    assert math.isfinite(pooled)
    assert 0 < pooled < 1
