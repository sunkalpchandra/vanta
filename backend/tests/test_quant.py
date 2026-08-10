from app.quant.analogs import find_analogs, tokenize
from app.quant.montecarlo import simulate

REFS = [
    ("Will NVIDIA beat quarterly earnings estimates?", "finance", 1),
    ("Will Apple beat quarterly revenue estimates?", "finance", 1),
    ("Will Tesla beat quarterly delivery estimates?", "finance", 0),
    ("Will a room-temperature superconductor be replicated this year?", "science", 0),
]


def test_tokenize_strips_stopwords():
    tokens = tokenize("Will the Fed cut rates before December?")
    assert "will" not in tokens and "the" not in tokens
    assert "fed" in tokens and "rates" in tokens


def test_analogs_prefer_same_topic():
    report = find_analogs("Will NVIDIA beat consensus earnings estimates next quarter?", "finance", REFS)
    assert report.n >= 2
    assert report.matches[0].text.startswith("Will NVIDIA")
    assert report.hit_rate is not None and report.hit_rate > 0.5


def test_analogs_empty_when_nothing_similar():
    report = find_analogs("Will the favorite win the chess world championship?", "sports", REFS, min_similarity=0.3)
    assert report.n == 0 and report.hit_rate is None


def test_category_alone_is_not_an_analog():
    """Regression: the category bonus must not clear the similarity gate by
    itself, or zero-overlap same-category events become fake analogs."""
    report = find_analogs("Will the favorite win the chess world championship?", "finance", REFS)
    assert report.n == 0 and report.hit_rate is None


def test_monte_carlo_is_deterministic_and_sane():
    a = simulate(0.7, evidence_strength=20, market_probability=0.6)
    b = simulate(0.7, evidence_strength=20, market_probability=0.6)
    assert a == b  # fixed seed => reproducible
    assert 0.6 < a.mean < 0.8
    assert a.ci_low < a.mean < a.ci_high
    assert 0.5 < a.p_above_market <= 1.0


def test_monte_carlo_tighter_with_more_evidence():
    weak = simulate(0.7, evidence_strength=4, market_probability=0.6)
    strong = simulate(0.7, evidence_strength=60, market_probability=0.6)
    assert (strong.ci_high - strong.ci_low) < (weak.ci_high - weak.ci_low)
