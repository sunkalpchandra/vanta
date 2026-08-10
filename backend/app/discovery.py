"""Autonomous research mode (demo scope).

The production vision: agents watch ingest streams (markets moving, papers
landing, hiring shifts) and mint new questions autonomously. The demo keeps
the real half of that pipeline — deduplication against existing questions,
question creation, and a full agent-pipeline forecast — and sources candidates
from a curated watchlist instead of live streams.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Question
from .quant.analogs import tokenize
from .service import create_question, run_and_store_forecast


@dataclass(frozen=True)
class Candidate:
    question: str
    category: str
    horizon_days: int
    rationale: str


WATCHLIST: list[Candidate] = [
    Candidate(
        "Will a frontier lab announce a model trained on over 100k GPUs before mid-2027?",
        "technology",
        320,
        "Cluster construction and power-procurement filings imply the training runs are already scheduled.",
    ),
    Candidate(
        "Will US 10-year Treasury yields close below 3.5% within 6 months?",
        "finance",
        180,
        "Rate-cut pricing and term-premium compression are diverging — one of them is wrong.",
    ),
    Candidate(
        "Will a major streaming platform sign an exclusive AI-generated content deal this year?",
        "technology",
        140,
        "Production-cost pressure plus recent guild-agreement carve-outs open the contract space.",
    ),
    Candidate(
        "Will a G7 country announce a sovereign AI compute fund exceeding $10B?",
        "politics",
        200,
        "Three draft budget proposals reference national compute reserves this cycle.",
    ),
    Candidate(
        "Will an mRNA cancer vaccine report positive phase-3 results within 12 months?",
        "science",
        365,
        "Two phase-3 readouts fall inside the window; interim signals were strong.",
    ),
    Candidate(
        "Will gold set a new inflation-adjusted all-time high this year?",
        "finance",
        150,
        "Central-bank accumulation is at multi-decade highs while real yields soften.",
    ),
    Candidate(
        "Will a top-10 crypto exchange face major enforcement action within 9 months?",
        "crypto",
        270,
        "Open investigations and recent subpoena activity cluster around two venues.",
    ),
    Candidate(
        "Will any national football league adopt in-game AI officiating this season?",
        "sports",
        220,
        "Two leagues ran closed trials last season; one rulebook amendment is pending.",
    ),
]

# A candidate is "already covered" when it shares this much token overlap with
# an existing question.
DUPLICATE_THRESHOLD = 0.45


def _is_duplicate(candidate: Candidate, existing_questions: list[str]) -> bool:
    c_tokens = tokenize(candidate.question)
    if not c_tokens:
        return True
    for text in existing_questions:
        e_tokens = tokenize(text)
        if not e_tokens:
            continue
        overlap = len(c_tokens & e_tokens) / len(c_tokens | e_tokens)
        if overlap >= DUPLICATE_THRESHOLD:
            return True
    return False


def pending_candidates(db: Session) -> list[Candidate]:
    existing = list(db.scalars(select(Question.question)).all())
    return [c for c in WATCHLIST if not _is_duplicate(c, existing)]


def discover(db: Session, count: int) -> list[tuple[Question, Candidate]]:
    """Materialize up to `count` new questions from the watchlist and run the
    full agent pipeline on each. Idempotent: created questions are recognized
    as duplicates on later calls."""
    created: list[tuple[Question, Candidate]] = []
    for candidate in pending_candidates(db)[:count]:
        question = create_question(
            db,
            text=candidate.question,
            category=candidate.category,
            horizon_days=candidate.horizon_days,
        )
        run_and_store_forecast(db, question)
        created.append((question, candidate))
    return created
