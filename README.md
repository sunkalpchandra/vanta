# vanta — Autonomous Intelligence Engine for Probabilistic Forecasting

> *"What does the world currently believe will happen, and what does our intelligence system think is actually going to happen?"*

vanta is a multi-agent forecasting intelligence platform. It watches questions about the future — rate cuts, earnings beats, model releases, elections, breakthroughs — and for each one produces a calibrated probability, a confidence score, the full internal agent debate, and the **edge**: where vanta's estimate diverges from the prediction-market consensus.

vanta is **not** a gambling platform. It is a forecasting intelligence system.

```
 MARKET 72%   ·   VANTA 81%   ·   EDGE +9%   ·   CONFIDENCE 8.4/10
```

## Architecture

```
            DATA LAYER (seeded demo corpus; ingest adapters in production)
   prediction markets · news · filings · papers · social signals
                              │
                              ▼
                    ┌─────────────────────┐
                    │  VANTA AGENT SYSTEM  │
                    │                     │
                    │  Research Agent      │  qualitative evidence, ± signals
                    │  Quant Agent         │  historical analogs + Monte Carlo
                    │  Market Agent        │  market consensus, liquidity trust
                    │  Sentiment Agent     │  public mood & momentum
                    │  Historian Agent     │  category base rates, horizon pull
                    │  Skeptic Agent       │  attacks the consensus, haircuts confidence
                    │  Synthesis Agent     │  weighted Bayesian log-odds pool
                    └─────────┬───────────┘
                              │
                              ▼
              probability · confidence · reasoning · risks
                              │
                              ▼
        Intelligence Feed · Debate Mode · Morning Brief · Leaderboard
```

**Design principle: deterministic math, optional LLM narratives.** Every probability comes from a reproducible quant core — weighted Bayesian aggregation in log-odds space, Beta-posterior Monte Carlo simulation, similarity-weighted historical analog matching, base-rate shrinkage, agreement-based confidence calibration. When `ANTHROPIC_API_KEY` is set, the research, skeptic, and synthesis agents write their narratives with Claude (`claude-opus-5`); without it the system runs fully offline with template narratives. Numbers never depend on the LLM.

## Features

- **Intelligence Feed** — discovery cards ranked by |edge|, flagging what the market may be mispricing
- **AI Debate Mode** — every forecast shows all seven agents' arguments, including the skeptic's attack
- **Morning Brief** — "5 things the world is wrong about", cached (Redis or in-process)
- **Accuracy Leaderboard** — vanta vs market directional accuracy and Brier scores by category
- **Ask vanta** — pose any yes/no future event; the full pipeline deliberates on demand
- **Shareable cards** — self-contained SVG prediction cards at `/api/cards/{id}.svg`

## Quick start (no keys, no Docker)

```bash
# backend — http://localhost:8000 (docs at /docs)
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload

# frontend — http://localhost:3000
cd frontend
npm install
npm run dev
```

The backend uses SQLite by default and seeds itself on first boot: 12 live questions with evidence, full agent runs, 30-day forecast history, and a resolved track record for the leaderboard.

## Docker

```bash
docker compose up --build
# web: http://localhost:3000 · api: http://localhost:8000 · postgres + redis included
```

## Configuration

Copy `.env.example` to `backend/.env` (all optional):

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./vanta.db` | Any SQLAlchemy URL; compose uses Postgres 16 |
| `REDIS_URL` | *(unset)* | Morning-brief cache; falls back to in-process |
| `ANTHROPIC_API_KEY` | *(unset)* | Enables Claude-written agent narratives |
| `VANTA_MODEL` | `claude-opus-5` | Model for narratives |
| `FRONTEND_ORIGIN` | `http://localhost:3000` | CORS |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Frontend → API base URL |

## API surface

| Endpoint | Description |
|---|---|
| `GET /api/feed` | Discovery cards ranked by absolute edge |
| `GET /api/questions` · `POST /api/questions` | List questions · ask a new one (runs the pipeline) |
| `GET /api/questions/{id}` | Question + latest forecast + evidence + agent debate |
| `GET /api/questions/{id}/history` | Probability time series |
| `POST /api/questions/{id}/refresh` | Re-run the agent pipeline |
| `GET /api/leaderboard` | Accuracy + Brier by category |
| `GET /api/brief` | Morning brief (top mispricings) |
| `GET /api/cards/{id}.svg` | Shareable prediction card |

## Tests

```bash
cd backend && .venv/bin/python -m pytest tests/ -q   # quant math, pipeline, API
```

## Project layout

```
backend/
  app/
    agents/        # 7 reasoning modules + orchestrator
    quant/         # bayes.py · montecarlo.py · analogs.py
    routers/       # questions · feed · leaderboard · brief · cards
    data.py        # demo corpus (reference events, seed questions)
    llm.py         # optional Claude narrative layer
    seed.py        # idempotent seeding + history backfill
  tests/
frontend/
  app/             # feed · questions/[id] · leaderboard · brief · ask
  components/      # charts, debate panel, cards, meters
```

## Honest scope notes

- Market data, evidence, and the resolved track record are a **seeded demo corpus** — deterministic and clearly labeled in-app. Production ingest (Polymarket/Kalshi APIs, news, filings) plugs in at `data.py`'s seams.
- The leaderboard's "vanta beats market" edge is a property of the demo seed, not a validated live track record.
- Users table exists in the schema; auth is not wired up yet.

## Roadmap

Autonomous question discovery · real market/news ingest · resolution pipeline writing the leaderboard · personal prediction profiles · AI forecaster tournament.
