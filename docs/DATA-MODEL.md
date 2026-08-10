# Data model

Ten tables, all declared in `backend/app/models.py` against the single `DeclarativeBase` in
`backend/app/db.py`. The schema is created at startup (`Base.metadata.create_all` in the app
lifespan) and seeded idempotently by `seed.py` — there are no migrations yet. Everything runs
identically on SQLite (the default) and Postgres (compose).

## Tables

**users** — operator accounts. `email` and `api_key` are both unique and indexed. The
`api_key` is a `vk_...` credential shown once at creation; it gates mutations only when
`require_api_key` is on (off by default — demo mode). No other table references users yet:
the schema exists, auth is not wired up.

**questions** — the core entity: a yes/no question about the future. Carries the question
text, `category` (indexed), `horizon_days`, and the current market view (`market_probability`,
`market_volume_usd`, `market_liquidity`). Resolution state lives here too: `resolved`
(indexed), `outcome` (1 YES / 0 NO, nullable until settled), `resolved_at`. Parent of
forecasts, evidence, and agent_reports via `cascade="all, delete-orphan"` — deleting a
question takes its debate history with it.

**forecasts** — one row per pipeline run: `probability`, `confidence` (0–10), `reasoning`
text, and a JSON `risk_factors` list. **Append-only**: every refresh adds a row, and the
accumulated rows *are* the vanta side of the probability-history chart.

**market_snapshots** — point-in-time market prices, the market side of the market-vs-vanta
chart. Also append-only; `Question.market_probability` mirrors the newest row so list views
never need the history.

**evidence** — ingested signals per question: `source`, `summary`, `sentiment`
(positive/negative/neutral), and an `impact` weight (0–1). Appended as signals arrive; each
ingest triggers an immediate re-forecast.

**agent_reports** — one structured report per agent per run: `agent` name, `stance`
(bull/bear/neutral), the agent's own `probability` (nullable — some agents abstain), the
`argument` prose, and a JSON `details` blob. This is what Debate Mode renders.

**agent_track_records** — each agent's probability frozen at resolution time, with the
`outcome`. Written by `resolve_question` from the final agent_reports snapshot; `agent` is
indexed because the agent leaderboard aggregates by agent across all resolutions.

**predictions** — resolved historical predictions: question text, category (indexed), the
market and vanta probabilities at settlement, and the outcome. Powers the accuracy
leaderboard. Rows with `question_id = NULL` are the seeded reference corpus; rows with a
value came from a live question resolving.

**watchlist_items** — user-added discovery candidates (`question` text is unique, so the
watchlist deduplicates itself), merged with the built-in watchlist that autonomous research
mints questions from.

## Append-only vs replace-on-run

The two per-run tables have opposite retention policies, on purpose:

- **forecasts append.** History is the product — sparklines, the 30-day chart, and
  "what did vanta think before T" all read old rows.
- **agent_reports replace.** `service.py` deletes a question's reports and rewrites them on
  every run, so Debate Mode always shows exactly one coherent debate — the latest. The
  per-agent *history* that matters is captured elsewhere: `resolve_question` freezes the
  final reports into agent_track_records before they can be overwritten again.

## Why predictions.question_id is unique

A question must settle exactly once. `resolve_question` guards with an UPDATE, but the
unique index on `predictions.question_id` is the database-level backstop against concurrent
resolves: the second writer violates the constraint instead of silently double-counting a
result into the leaderboard. The column is nullable, and NULLs don't collide under a unique
constraint — which is exactly what lets the seeded reference corpus hold many rows with no
question at all.

## Composite indexes

Both time-series tables carry a composite index `(question_id, timestamp)`:

- `ix_forecasts_question_ts` — every hot read is "newest forecast for question X" or
  "newest forecast before T for question X". The composite serves both as an index-order
  scan on the question's slice; neither a lone `question_id` index (sort step) nor a lone
  `timestamp` index (full-range filter) does.
- `ix_market_snapshots_question_ts` — the same shape for the market series: one question's
  snapshots, ordered by time, for charts and 30-day sparklines.

## The SQLite tzinfo trap

Every datetime column is declared `DateTime(timezone=True)` and every default is
`utcnow()` (timezone-aware UTC). SQLite stores the value but **returns it naive** — the
tzinfo is gone on read. Serialized as-is, a bare ISO string like `2026-08-10T14:00:00` gets
parsed by JavaScript `Date()` as *local* time, shifting every chart date by the viewer's
UTC offset.

The answer is `UTCDateTime` in `backend/app/schemas.py`: a Pydantic `PlainSerializer` that
assumes UTC on naive values, converts aware values to UTC, and always emits a `Z`-suffixed
ISO string. All outbound datetimes go through it; `frontend/lib/format.ts` appends `Z`
defensively as a second layer. Postgres round-trips tzinfo correctly, so the serializer is
a no-op there — the wire format is identical either way.

## Entity-relationship sketch

```
  users                          watchlist_items
  (standalone — auth not wired)  (standalone — question text UNIQUE)

                          questions
                              │ 1
     ┌───────────┬────────────┼─────────────┬────────────────┐
     │ *         │ *          │ *           │ *              │ *
 forecasts  market_snapshots  evidence  agent_reports  agent_track_records
 (append,   (append,          (append   (REPLACED      (frozen per agent
  composite  composite         per       each run —     at resolution)
  ts index)  ts index)         signal)   latest only)
                              │ 0..1
                          predictions
                          (question_id UNIQUE + nullable;
                           NULL rows = seeded reference corpus)
```
