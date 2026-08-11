"""Shareable market cards — self-contained SVG, no external assets.

Mirrors app/routers/cards.py (the question share cards): same 800x418 dark
canvas, escaped text, RESOLVED stamp. This variant renders a MarketEvent from
the play-money markets surface — real synced venue prices, virtual ⓥ trading.

Distinct prefix (/api/market-cards) so the `.svg` path never collides with
markets.router's `/api/markets/{event_id}` int path.
"""

import html

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import MarketEvent

# Reuse the question card's word-wrap helper when importable; fall back to a
# local copy so this router never hard-depends on cards.py's internals.
try:  # pragma: no cover - trivial import guard
    from .cards import _wrap
except Exception:  # pragma: no cover

    def _wrap(text: str, width: int = 38, max_lines: int = 3) -> list[str]:
        words, lines, line = text.split(), [], ""
        for w in words:
            if len(line) + len(w) + 1 > width:
                lines.append(line)
                line = w
            else:
                line = f"{line} {w}".strip()
        if line:
            lines.append(line)
        if len(lines) > max_lines:
            lines = lines[: max_lines - 1] + [lines[max_lines - 1] + "…"]
        return lines


router = APIRouter(prefix="/api/market-cards", tags=["markets"])

_MONO = "ui-monospace,Menlo,monospace"
_SANS = "-apple-system,Segoe UI,sans-serif"
_DISCLAIMER = "play money · paper trading · real market prices"


def _compact_usd(value: float) -> str:
    """Compact venue volume: $1.2K / $3.4M / $2B (mirrors format's TS helper)."""
    v = value or 0.0
    for cutoff, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(v) >= cutoff:
            num = f"{v / cutoff:.1f}".rstrip("0").rstrip(".")
            return f"${num}{suffix}"
    return f"${v:.0f}"


def _text(x, y, content, *, size, fill, mono=True, weight=None, spacing=None, anchor=None) -> str:
    fam = _MONO if mono else _SANS
    attrs = [f'x="{x}"', f'y="{y}"', f'fill="{fill}"', f'font-family="{fam}"', f'font-size="{size}"']
    if weight:
        attrs.append(f'font-weight="{weight}"')
    if spacing:
        attrs.append(f'letter-spacing="{spacing}"')
    if anchor:
        attrs.append(f'text-anchor="{anchor}"')
    return f"<text {' '.join(attrs)}>{content}</text>"


def _pct(p: float | None) -> str:
    return f"{p:.0%}" if p is not None else "—"


def _build_svg(event: MarketEvent) -> str:
    # Current venue YES price; fall back to the frozen final price once settled.
    price = event.yes_price if event.yes_price is not None else event.final_price
    no_price = round(1.0 - price, 6) if price is not None else None

    source_label = html.escape((event.source or "market").upper())
    badge_w = len(source_label) * 9 + 26
    badge = (
        f'<rect x="60" y="80" width="{badge_w}" height="30" rx="8" fill="none" stroke="#374151"/>'
        + _text(74, 100, source_label, size=13, fill="#9ca3af", spacing=1)
    )

    resolved_stamp = ""
    if event.outcome is not None:
        is_yes = event.outcome == 1
        stamp_text = "RESOLVED YES" if is_yes else "RESOLVED NO"
        stamp_color = "#34d399" if is_yes else "#f87171"
        resolved_stamp = (
            f'<rect x="556" y="44" width="184" height="34" rx="8" fill="none" '
            f'stroke="{stamp_color}" stroke-width="1.5"/>'
            + _text(648, 66, stamp_text, size=14, fill=stamp_color, spacing=2, anchor="middle")
        )

    title_lines = "".join(
        f'<tspan x="60" dy="{34 if i else 0}">{html.escape(line)}</tspan>'
        for i, line in enumerate(_wrap(event.question))
    )
    title = (
        f'<text x="60" y="158" fill="#f9fafb" font-family="{_SANS}" '
        f'font-size="26" font-weight="600">{title_lines}</text>'
    )

    footer_text = f"{_DISCLAIMER} · {html.escape(event.category or 'other')}"

    parts = [
        '<rect width="800" height="418" rx="24" fill="url(#bg)" stroke="#1f2937"/>',
        _text(60, 56, "VANTA · MARKETS", size=15, fill="#6b7280", spacing=4),
        badge,
        resolved_stamp,
        title,
        _text(60, 290, "YES", size=13, fill="#6b7280", spacing=2),
        _text(60, 338, _pct(price), size=44, fill="#34d399", weight=700),
        _text(300, 290, "NO", size=13, fill="#6b7280", spacing=2),
        _text(300, 338, _pct(no_price), size=44, fill="#9ca3af", weight=700),
        _text(540, 290, "VOLUME", size=13, fill="#6b7280", spacing=2),
        _text(540, 338, _compact_usd(event.volume_usd), size=44, fill="#e5e7eb", weight=700),
        _text(60, 390, footer_text, size=13, fill="#4b5563"),
    ]
    body = "\n  ".join(p for p in parts if p)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="418" viewBox="0 0 800 418">\n'
        "  <defs>\n"
        '    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">\n'
        '      <stop offset="0" stop-color="#0a0f1c"/><stop offset="1" stop-color="#111827"/>\n'
        "    </linearGradient>\n"
        "  </defs>\n"
        f"  {body}\n"
        "</svg>"
    )


@router.get("/{event_id}.svg")
def market_card(event_id: int, db: Session = Depends(get_db)):
    """An 800x418 shareable SVG for one market event. 404 if unknown."""
    event = db.get(MarketEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="market not found")
    svg = _build_svg(event)
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=300"},
    )
