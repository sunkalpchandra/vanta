# vanta API reference

Base URL: `http://localhost:8000` (interactive docs at `/docs`). All responses are JSON unless noted. Timestamps are zone-qualified UTC (`...Z`).

## Questions

| Endpoint | Description |
|---|---|
| `GET /api/questions` | All questions, newest first. Filters: `?category=`, `?resolved=`, `?q=` (text search), `?limit=&offset=` (pagination). |
| `GET /api/questions/{id}/analogs` | The quant agent's historical analog matches from the latest run. |
| `POST /api/questions` | Ask a question — runs the full seven-agent pipeline. Body: `{question, category, horizon_days, market_probability?}`. `category` is one of `technology · finance · politics · science · sports · crypto`. Without `market_probability`, the category base rate stands in (flagged by zero volume / low liquidity). |
| `GET /api/questions/{id}` | Question + latest forecast + evidence + the full agent debate. |
| `GET /api/questions/{id}/history` | Probability time series (append-only forecast history). |
| `POST /api/questions/{id}/refresh` | Re-run the pipeline. `409` once resolved. |
| `POST /api/questions/{id}/evidence` | Ingest a signal (`{source, summary, sentiment, impact}`) and immediately re-forecast. `409` once resolved. |
| `POST /api/questions/{id}/resolve` | Settle against reality: `{outcome: bool}`. Freezes the question, writes the leaderboard prediction. `409` on double-resolve. |

## Intelligence surfaces

| Endpoint | Description |
|---|---|
| `GET /api/feed` | Discovery cards for live questions, ranked by absolute edge. `?limit=` caps. |
| `GET /api/feed/movers?days=3&limit=6` | Questions whose vanta probability moved most over the window. |
| `GET /api/brief?count=5` | Morning brief — top mispricings, max 2 per category (`count` 1–20). Cached 10 minutes; invalidated on resolution. |
| `GET /api/cards/{id}.svg` | Self-contained shareable prediction card (SVG). RESOLVED stamp once settled. |

## Track record

| Endpoint | Description |
|---|---|
| `GET /api/leaderboard` | Directional accuracy + Brier by category, vanta vs market. |
| `GET /api/leaderboard/calibration` | Reliability-diagram bins (10) for vanta and market. |
| `GET /api/stats` | System-level: live/resolved counts, accuracy, Brier, log scores, Murphy decomposition (reliability/resolution/uncertainty), average live edge. |
| `GET /api/categories` | Coverage and long-run base rate per category. |
| `GET /api/agents/leaderboard` | The internal forecaster competition — each agent's frozen calls scored against outcomes, sorted by Brier. |

## Autonomous research

| Endpoint | Description |
|---|---|
| `GET /api/discover/candidates` | Watchlist questions not yet covered by the question base. |
| `POST /api/discover?count=3` | Mint up to `count` (1–5) new questions and forecast each. Idempotent — covered questions are skipped. |

## Meta

| Endpoint | Description |
|---|---|
| `GET /api/health` | `{status, llm_narratives}`. |

## Error semantics

- `404` — unknown question id.
- `409` — state conflicts: resolving twice, refreshing/adding evidence to a resolved question.
- `422` — validation: malformed bodies, out-of-range `count`, unknown `category`.
- No auth yet (see SECURITY.md); everything is workspace-local.
