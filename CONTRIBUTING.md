# Contributing to vanta

## Dev setup

Backend (FastAPI, Python 3.11+):

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload   # http://localhost:8000, docs at /docs
```

The backend uses SQLite (`backend/vanta.db`) and seeds itself on first boot —
no keys or services required. Optional settings go in `backend/.env` (see
`.env.example`).

Frontend (Next.js 15):

```bash
cd frontend
npm install
npm run dev   # http://localhost:3000
```

Frontend env vars live in `frontend/.env.local`, not `backend/.env`.

## Tests

```bash
backend/.venv/bin/python -m pytest backend/tests/ -q
```

Or from `backend/`: `.venv/bin/python -m pytest tests/ -q`. The suite covers
the quant math (`test_bayes.py`, `test_quant.py`), the full pipeline
(`test_pipeline.py`), the API (`test_api.py`), and known regressions
(`test_agents_zero_probability.py`). Everything runs offline; nothing may
depend on `ANTHROPIC_API_KEY` being set.

## Commit style

Small, granular commits — one logical change each, per-file where that is the
natural unit. Subjects are imperative present tense with a type prefix, as in
the existing log:

```
feat: add horizon pull to historian agent
fix: pool zero-probability estimates instead of dropping them
test: cover skeptic haircut bounds
docs: note frontend env file location
chore: bump recharts
```

## The one hard rule

**Probabilities come from the quant engine, never from LLM output.** The LLM
layer (`backend/app/llm.py`, `narrate()`) writes prose only: numbers are
computed first and passed *into* the prompt, and nothing numeric is ever
parsed *out* of a response. `narrate` must always take a deterministic
`fallback` so the system behaves identically offline. If your change makes any
number depend on Claude's output, it will not be merged.

## Adding a new agent

1. Implement the contract: subclass `Agent` from `backend/app/agents/base.py`
   and return an `AgentOutput` from
   `run(self, ctx: QuestionContext, prior_outputs: list[AgentOutput])`.
2. Set `weight` deliberately — it is the agent's influence in the log-odds
   pool. To abstain, return `probability=None, weight=0.0`. Never signal
   abstention with `probability=0.0`: an exact zero is a maximally bearish
   vote and is pooled (see `tests/test_agents_zero_probability.py`).
3. Register it in `ESTIMATORS` in `backend/app/agents/orchestrator.py` if it
   is an independent estimator. Order matters: estimators run before the
   skeptic, which attacks their interim consensus, and the synthesis agent
   pools last.
4. If it needs narrative text, compute all numbers first and call
   `narrate(system, prompt, fallback)` with a template fallback.
5. Add tests: the agent's estimate and weight under representative contexts,
   its abstention path, and update the expected agent list in
   `tests/test_pipeline.py::test_pipeline_produces_complete_forecast`.
