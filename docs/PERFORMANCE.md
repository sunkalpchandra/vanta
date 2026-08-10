# Performance notes

Measured with `backend/scripts/bench.py` (median/p90 of 30 in-process requests
against a fresh seeded DB, Apple Silicon dev machine, SQLite). Numbers are
small in absolute terms at demo scale — the point of the fixes is the
*scaling shape*, verified by query-count regression tests in
`backend/tests/test_performance.py`.

## Query-shape fixes (2026-08-10)

The feed and movers endpoints ran **one query per live question** (N+1). Both
now run a constant number of queries regardless of question count, using a
newest-forecast-id-per-question subquery join, backed by the composite index
`ix_forecasts_question_ts`.

| Endpoint | Before (median / p90) | After (median / p90) | Queries before → after |
|---|---|---|---|
| `GET /api/feed` | 3.24ms / 6.33ms | 2.22ms / 2.41ms | 1 + N → ≤2 |
| `GET /api/feed/movers` | 5.53ms / 8.13ms | 2.81ms / 3.04ms | 1 + 2N → ≤3 |

At the demo's 12 questions this is ~1.3-2x; the N+1 elimination is what keeps
these endpoints flat at 100+ questions.

## Payload-shape fix

The feed page fetched each card's 30-point history separately (12+ requests
server-side per page render; 12+ file reads in the static demo).
`GET /api/feed/sparklines` returns every live series in one payload (one
query), and the static snapshot bakes it as `sparklines.json`.

## Transport

- `GZipMiddleware` (min 1KB) — the feed/brief/leaderboard JSON payloads
  compress ~5-10x.
- `Cache-Control` on tolerant read endpoints (feed 30s, brief/leaderboard/
  stats 60s, cards/categories 300s, backtest 1h). Mutations and operator
  reads stay uncached; resolution already invalidates the brief server-side
  within its TTL semantics.
- `X-Response-Time-Ms` on every response for quick field diagnosis.

## Re-measuring

```bash
cd backend && .venv/bin/python scripts/bench.py --n 30
```

Query-count regressions fail CI via `tests/test_performance.py` — if a change
reintroduces per-question queries on the feed, movers, or sparklines paths,
the suite catches it without needing a timing harness.
