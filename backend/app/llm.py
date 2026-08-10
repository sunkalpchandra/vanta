"""Optional Claude-powered narrative layer.

All probabilities come from the deterministic quant engine. When an Anthropic
API key is available, agents route their *narrative* work (evidence summaries,
skeptic critiques, synthesis reasoning) through Claude; otherwise they fall
back to template-based text so the system runs fully offline.
"""

import logging

from .config import get_settings

logger = logging.getLogger(__name__)

_client = None
_client_checked = False


def _get_client():
    global _client, _client_checked
    if _client_checked:
        return _client
    _client_checked = True
    settings = get_settings()
    if not settings.anthropic_api_key:
        return None
    try:
        import anthropic

        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    except Exception:  # pragma: no cover - import/config failure is non-fatal
        logger.exception("Anthropic client unavailable; using deterministic narratives")
        _client = None
    return _client


def llm_available() -> bool:
    return _get_client() is not None


def narrate(system: str, prompt: str, fallback: str, max_tokens: int = 2048) -> str:
    """Ask Claude for a short narrative; return `fallback` on any failure.

    max_tokens leaves headroom because claude-opus-5 thinks by default and
    thinking tokens count against the cap.
    """
    client = _get_client()
    if client is None:
        return fallback
    settings = get_settings()
    try:
        response = client.messages.create(
            model=settings.vanta_model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        if response.stop_reason == "refusal":
            logger.warning("Claude declined a narrative request; using fallback text")
            return fallback
        text = next((b.text for b in response.content if b.type == "text"), "")
        return text.strip() or fallback
    except Exception:
        logger.exception("Claude narrative call failed; using fallback text")
        return fallback
