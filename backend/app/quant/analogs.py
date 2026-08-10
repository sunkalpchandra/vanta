"""Historical analog matching.

Scores a question against a reference set of resolved events using keyword
and category similarity, then reports the hit rate among the top matches —
the "17 of 20 similar situations resolved YES" style of evidence.
"""

import re
from dataclasses import dataclass

_WORD = re.compile(r"[a-z0-9$%.]+")

STOPWORDS = {
    "will", "the", "a", "an", "be", "by", "in", "on", "of", "to", "before",
    "after", "and", "or", "is", "it", "its", "this", "that", "than", "at",
}


def tokenize(text: str) -> set[str]:
    return {t for t in _WORD.findall(text.lower()) if t not in STOPWORDS}


@dataclass
class AnalogMatch:
    text: str
    category: str
    similarity: float
    outcome: int  # 1 resolved YES, 0 resolved NO


@dataclass
class AnalogReport:
    matches: list[AnalogMatch]
    hit_rate: float | None  # None when no matches found
    n: int


def similarity(q_tokens: set[str], q_category: str, ref_text: str, ref_category: str) -> float:
    ref_tokens = tokenize(ref_text)
    overlap = 0.0 if not q_tokens or not ref_tokens else len(q_tokens & ref_tokens) / len(q_tokens | ref_tokens)
    # Category membership only *amplifies* topical overlap — on its own it must
    # not clear the min_similarity gate, or every same-category event becomes a
    # fake "analog" and the quant agent can never abstain.
    category_bonus = 0.35 if overlap > 0 and q_category == ref_category else 0.0
    return min(1.0, overlap + category_bonus)


def find_analogs(
    question: str,
    category: str,
    reference_set: list[tuple[str, str, int]],
    top_k: int = 20,
    min_similarity: float = 0.2,
) -> AnalogReport:
    """reference_set entries are (text, category, outcome)."""
    q_tokens = tokenize(question)
    scored = [
        AnalogMatch(text=t, category=c, similarity=similarity(q_tokens, category, t, c), outcome=o)
        for t, c, o in reference_set
    ]
    matches = sorted(
        (m for m in scored if m.similarity >= min_similarity),
        key=lambda m: m.similarity,
        reverse=True,
    )[:top_k]
    if not matches:
        return AnalogReport(matches=[], hit_rate=None, n=0)
    # Similarity-weighted hit rate: closer analogs count for more.
    total_w = sum(m.similarity for m in matches)
    hit_rate = sum(m.similarity * m.outcome for m in matches) / total_w
    return AnalogReport(matches=matches, hit_rate=hit_rate, n=len(matches))
