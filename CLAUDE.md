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

## Verification loop

```
make lint      # ruff over backend
make test      # pytest (backend/.venv must exist)
cd frontend && npx next build          # live-mode build
make static    # snapshot + Pages export (out/)
```

Backend tests share one process-level SQLite bound in `tests/conftest.py` (the engine binds at
first app import, and conftest imports before any test module under every ordering). Test
modules must tolerate earlier modules' writes (resolved questions, discovery-minted questions)
— e.g. pick seeded questions from the *end* of the newest-first list.
