import pytest

from app.quant.scoring import brier_score, calibration_bins, directional_accuracy


def test_brier_perfect_and_worst():
    assert brier_score([(1.0, 1), (0.0, 0)]) == 0.0
    assert brier_score([(1.0, 0), (0.0, 1)]) == 1.0
    assert brier_score([(0.5, 1), (0.5, 0)]) == pytest.approx(0.25)


def test_brier_rejects_empty():
    with pytest.raises(ValueError):
        brier_score([])


def test_directional_accuracy():
    pairs = [(0.9, 1), (0.7, 1), (0.4, 0), (0.6, 0)]  # 3 right, 1 wrong
    assert directional_accuracy(pairs) == pytest.approx(0.75)


def test_calibration_bins_diagonal_for_perfect_forecaster():
    # 100 forecasts at 0.25 with 25% observed, 100 at 0.75 with 75% observed.
    pairs = [(0.25, 1)] * 25 + [(0.25, 0)] * 75 + [(0.75, 1)] * 75 + [(0.75, 0)] * 25
    bins = calibration_bins(pairs, n_bins=4)
    quarter = next(b for b in bins if b.lo == 0.25)
    assert quarter.count == 100
    assert quarter.observed_rate == pytest.approx(0.25)
    assert quarter.mean_predicted == pytest.approx(0.25)


def test_calibration_bins_edge_membership():
    bins = calibration_bins([(0.0, 0), (1.0, 1)], n_bins=10)
    assert bins[0].count == 1  # p=0.0 in first bin
    assert bins[-1].count == 1  # p=1.0 captured by closed final bin
    assert sum(b.count for b in bins) == 2


def test_calibration_empty_bins_are_none():
    bins = calibration_bins([(0.95, 1)], n_bins=10)
    assert bins[0].mean_predicted is None
    assert bins[-1].observed_rate == 1.0


def test_calibration_round_quotes_land_in_their_nominal_bin():
    """Regression: 3*0.1 == 0.30000000000000004, so edge-comparison binning
    dropped exact round quotes (0.3, 0.6, 0.7) one bin below."""
    bins = calibration_bins([(0.3, 1), (0.6, 0), (0.7, 1)], n_bins=10)
    by_count = {i: b for i, b in enumerate(bins) if b.count}
    assert set(by_count) == {3, 6, 7}
    for b in by_count.values():
        assert b.lo <= b.mean_predicted <= b.hi
