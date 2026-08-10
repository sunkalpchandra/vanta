# vanta — guide for coding agents

## Ground rules

- **Probabilities come from the quant engine only** (`backend/app/quant/`). The LLM layer
  (`backend/app/llm.py`) writes narrative prose and must never influence a number. Keep that
  boundary when extending anything.
- **Commit style:** small granular commits, imperative subjects, `feat|fix|test|docs|chore|ci|style(scope):` prefixes.
- The demo corpus in `backend/app/data.py` is deterministic fixture data and is labeled as such
  in the UI and README — never present it as live data.

## Traps already paid for (do not reintroduce)

- SQLite drops tzinfo despite `DateTime(timezone=True)` — serialize datetimes through
  `UTCDateTime` in `backend/app/schemas.py`; the frontend's `format.ts` also appends `Z` defensively.
- Analog matching: the category bonus must require token overlap > 0 (`quant/analogs.py`),
  or the quant agent fabricates analogs and can never abstain.
- Agent pooling filters: use `probability is not None`, never truthiness — `p=0.0` is a vote.
- SSR inside docker compose uses `API_URL_INTERNAL` (http://api:8000); `NEXT_PUBLIC_API_URL`
  is browser-only. Static mode (`NEXT_PUBLIC_STATIC_MODE=1`) reads `public/data` instead.
- Only server components may import `frontend/lib/data.ts` (it reads the filesystem in static
  mode). Client components import from `frontend/lib/api.ts`.

## Newer surface worth knowing

- Resolution writes three things atomically: the `predictions` row, per-agent
  `agent_track_records`, and the question freeze (guarded UPDATE + unique
  index). It also busts the brief cache. Extend `resolve_question`, don't
  bypass it.
- `service.learned_base_rate` is the only place the category prior touches the
  DB; agents read it from `QuestionContext.base_rate`.
- The static snapshot must stay in lockstep with `frontend/lib/data.ts`
  snapshot names — anything added there needs a matching entry in
  `backend/scripts/export_snapshot.py`.

- The feed's newest-forecast subquery must stay timestamp-first (id only
  breaks ties): seeding writes the live forecast before its backfill, so
  backfill rows have higher ids with older timestamps.
- Counterfactual pipeline runs (sensitivity) must set
  `QuestionContext.narratives = False` — never burn LLM calls on numbers-only
  reruns.
- Playwright specs run against the static export served under `/vanta`
  (`frontend/e2e/serve.sh`); interactions must tolerate the hydration race —
  wrap click/fill in `expect(...).toPass()` blocks, not bare waits.
- The brief cache key includes the category scope
  (`vanta:brief:{count}:{category|all}`); invalidation deletes by prefix.

## Trading invariants (v0.4 play-money market)

- **Play money, always**: ⓥ credits are virtual and non-redeemable. Every
  trading surface (UI and docs) carries "play money · paper trading · real
  market prices". Never add anything that moves, references, or implies real
  money; no gambling aesthetics — it's a terminal, not a slot machine.
- **Money math at the boundaries** (`app/trading.py`): validate `shares > 0`
  and execution price strictly in (0, 1); round money to 2 decimals only at
  the boundaries, and **house-favorable** — a buy's cost rounds up, a sell's
  proceeds and every settlement payout round down (`_debit` / `_credit`), so
  no run of dust trades can mint credits. Keep execution prices at 6 decimals
  so NO complements (`1 − yes_price`) don't drift — intermediate math stays
  full-precision. Balances never go negative; sells are capped at held shares;
  both sides enforce the ⓥ0.01 minimum notional on true notional (shares ×
  price), except a sell that fully closes a position (so a holder can always
  exit a sub-cent lot). Trading halts once an event passes its `close_time`
  (the synced price is stale) until the sync flips it inactive/resolved.
  Prices are deterministic code only — the LLM layer never touches money,
  same rule as probabilities.
- **Settlement is position-driven + idempotent**: `settle_resolved` pays out
  every resolved event that still has unsettled positions — driven by unpaid
  positions, never a time window or a just-flipped-outcome signal — so no
  payout is orphaned no matter which writer recorded the outcome.
  `settle_event` pays each position exactly once (`Position.settled` is the
  guard, same guarded-transition discipline as `resolve_question`); any settle
  path must be safe to re-run or crash mid-way without double-paying.
- **Sync statelessness**: `sync_markets.py` keeps no cursors or local state;
  each run reconciles against the venue's *current* listings
  (add / update / deactivate / settle) and must converge when re-run.
  Deactivation removes markets from the tradable surface but never touches
  open positions.
- **Static markets sample lockstep**: the same rule as every snapshot surface
  — any markets/portfolio data the static demo shows needs matching entries in
  `backend/scripts/export_snapshot.py` and `frontend/lib/data.ts`, and the
  Pages workflow's scheduled bake (seed → sync → export against the workspace
  bake DB) assumes the exporter's existing-DB passthrough mode.

## Verification loop

```
make lint      # ruff over backend
make test      # pytest (backend/.venv must exist)
cd frontend && npx next build          # live-mode build
make static    # snapshot + Pages export (out/)
make e2e       # Playwright over the static export (builds it first)
```

Backend tests share one process-level SQLite bound in `tests/conftest.py` (the engine binds at
first app import, and conftest imports before any test module under every ordering). Test
modules must tolerate earlier modules' writes (resolved questions, discovery-minted questions)
— e.g. pick seeded questions from the *end* of the newest-first list.
