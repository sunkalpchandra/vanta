from app.agents.base import QuestionContext
from app.agents.orchestrator import run_pipeline

CTX = QuestionContext(
    question="Will NVIDIA beat consensus earnings estimates next quarter?",
    category="finance",
    horizon_days=60,
    market_probability=0.72,
    market_volume_usd=2_000_000,
    market_liquidity="high",
    evidence=[
        {"source": "supply", "summary": "GPU demand outruns supply.", "sentiment": "positive", "impact": 0.9},
        {"source": "capex", "summary": "Hyperscalers raised capex guidance.", "sentiment": "positive", "impact": 0.8},
        {"source": "export", "summary": "Export controls cloud revenue share.", "sentiment": "negative", "impact": 0.6},
    ],
)


def test_pipeline_produces_complete_forecast():
    result = run_pipeline(CTX)
    assert 0 < result.probability < 1
    assert 1.0 <= result.confidence <= 10.0
    assert result.reasoning
    assert isinstance(result.risk_factors, list) and result.risk_factors
    agents = [o.agent for o in result.outputs]
    assert agents == ["research", "quant", "market", "sentiment", "historian", "skeptic", "synthesis"]


def test_pipeline_is_deterministic_without_llm():
    a = run_pipeline(CTX)
    b = run_pipeline(CTX)
    assert a.probability == b.probability
    assert a.confidence == b.confidence


def test_positive_evidence_lifts_probability_above_bearish_market():
    bearish = QuestionContext(
        question=CTX.question,
        category=CTX.category,
        horizon_days=CTX.horizon_days,
        market_probability=0.5,
        market_volume_usd=CTX.market_volume_usd,
        market_liquidity=CTX.market_liquidity,
        evidence=CTX.evidence,
    )
    result = run_pipeline(bearish)
    assert result.probability > 0.5  # strong positive evidence should create a bullish edge


def test_skeptic_always_opposes_consensus():
    result = run_pipeline(CTX)
    skeptic = next(o for o in result.outputs if o.agent == "skeptic")
    synthesis = next(o for o in result.outputs if o.agent == "synthesis")
    interim = skeptic.details["interim_consensus"]
    expected = "bear" if interim >= CTX.market_probability else "bull"
    assert skeptic.stance == expected
    assert skeptic.probability is None  # skeptic never joins the pool
    assert synthesis.details["risk_factors"] == skeptic.details["risk_factors"]
