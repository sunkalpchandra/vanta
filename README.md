# vanta — Autonomous Intelligence Engine for Probabilistic Forecasting

[![ci](https://github.com/sunkalpchandra/vanta/actions/workflows/ci.yml/badge.svg)](https://github.com/sunkalpchandra/vanta/actions/workflows/ci.yml)
[![deploy-pages](https://github.com/sunkalpchandra/vanta/actions/workflows/pages.yml/badge.svg)](https://github.com/sunkalpchandra/vanta/actions/workflows/pages.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Live demo:** [sunkalpchandra.github.io/vanta](https://sunkalpchandra.github.io/vanta/) — a static snapshot of the full system (feed, agent debates, calibration, morning brief, markets). Trading and asking new questions need a live backend.

**Run it live — real backend, real play-money trading** (register, trade real markets at synced prices, share a leaderboard):

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/sunkalpchandra/vanta)

One click provisions Postgres + the FastAPI server + a market-sync cron; put the frontend on Vercel pointed at it. Step-by-step: [docs/DEPLOY-LIVE.md](docs/DEPLOY-LIVE.md). Play money only — ⓥ credits are virtual.

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

- **Intelligence Feed** — discovery cards ranked by |edge|, with 30-day sparklines, category filters, search, and a biggest-moves strip
- **AI Debate Mode** — every forecast shows all seven agents' arguments, the skeptic's attack, and the quant agent's historical analogs
- **Morning Brief** — "5 things the world is wrong about" with category diversity, copy-as-text, and RSS
- **Accuracy Leaderboard** — directional accuracy, Brier and log scores, Murphy decomposition, and a reliability diagram, vanta vs market
- **Agent Leaderboard** — the internal forecaster competition: each agent's frozen calls scored at resolution
- **Resolution lifecycle** — settle questions against reality; the track record, archive, and learned category base rates grow from real outcomes
- **Autonomous research** — a deduplicated watchlist (built-in + user-added) the pipeline mints new questions from
- **Self-measurement** — a leave-one-out backtest of the analog engine, published with its no-skill benchmark
- **Ask vanta** — pose any yes/no future event; the full pipeline deliberates on demand
- **Shareable cards** — self-contained SVG prediction cards, stamped once resolved
- **Market history** — the market is a moving series, charted against vanta with evidence-arrival markers
- **Explanations** — leave-one-out evidence sensitivity, what-changed diffs, related questions, historical analogs, difficulty scores
- **Operations** — alerts, digest, unified search, starred questions, operator notes, operator CLI, `/metrics`, opt-in API-key gating, rate limiting
- **Performance, measured** — constant-query hot paths, batched sparklines, gzip + caching; see [docs/PERFORMANCE.md](docs/PERFORMANCE.md)
- **Real markets** — checkpointed ingest of 100k+ resolved Polymarket/Kalshi binary markets; active top-volume markets promoted into the live feed
- **Play-money market** — trade real Polymarket/Kalshi events with virtual ⓥ credits at real synced venue prices: positions, cost basis, realized P&L, settlement at venue outcomes (**play money · paper trading · real market prices** — never real money); see [docs/TRADING.md](docs/TRADING.md)
- **Live market sync** — a stateless sync engine keeps the tradable surface fresh (add / update prices / deactivate / settle), and the Pages demo re-bakes on a 6-hour cron so the deployed snapshot tracks current events
- **Portfolio** — ⓥ balance, open positions marked to the current price, an append-only trade log, and a trader leaderboard by lifetime P&L
- **Real backtest** — leakage-free scoring against pre-resolution venue prices with leave-one-out base rates and a no-skill benchmark; see [docs/BACKTEST.md](docs/BACKTEST.md)
- **Reasoning chat** — `/chat` streams the live agent debate over SSE: per-agent stances and arguments as they compute, then the final scorecard
- **Tested end to end** — 200+ backend tests (95% coverage), 32 frontend unit tests, and a Playwright suite that drives the exact static artifact GitHub Pages serves
- **Keyboard-first** — `/` focuses search, `[` and `]` page through questions; brief and question pages print cleanly

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

## GitHub Pages demo

GitHub Pages can't run the FastAPI backend, so the demo is a **baked snapshot**:
`backend/scripts/export_snapshot.py` boots the seeded app and walks the read API into
`frontend/public/data/*.json` + `frontend/public/cards/*.svg`, and the frontend builds with
`NEXT_PUBLIC_STATIC_MODE=1` — same pages, same charts, data read from the snapshot instead of
the network. `.github/workflows/pages.yml` re-bakes and redeploys on every push to `main` **and
on a 6-hour cron**: the scheduled bake seeds a workspace database, syncs current active markets
into it (best-effort — a venue hiccup falls back to the deterministic seed), and exports from
that, so the deployed demo carries fresh real events without a push.

```bash
# reproduce the Pages build locally
python backend/scripts/export_snapshot.py --out frontend/public
cd frontend && NEXT_PUBLIC_STATIC_MODE=1 NEXT_PUBLIC_BASE_PATH=/vanta npx next build
# artifact in frontend/out/
```

## Configuration

All variables are optional. Backend settings live in `backend/.env`; frontend settings live in `frontend/.env.local` (Next.js does not read `backend/.env`).

**`backend/.env`:**

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./vanta.db` | Any SQLAlchemy URL; compose uses Postgres 16 |
| `REDIS_URL` | *(unset)* | Morning-brief cache; falls back to in-process |
| `ANTHROPIC_API_KEY` | *(unset)* | Enables Claude-written agent narratives |
| `VANTA_MODEL` | `claude-opus-5` | Model for narratives |
| `FRONTEND_ORIGIN` | `http://localhost:3000` | CORS |

**`frontend/.env.local`:**

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | API base URL for the browser (client fetches, share links) |
| `API_URL_INTERNAL` | *(falls back to public URL)* | API base URL for SSR — set when the server reaches the API by a different route than the browser (compose sets `http://api:8000`) |

## API surface

| Endpoint | Description |
|---|---|
| `GET /api/feed` | Discovery cards ranked by absolute edge |
| `GET /api/questions` · `POST /api/questions` | List questions · ask a new one (runs the pipeline) |
| `GET /api/questions/{id}` | Question + latest forecast + evidence + agent debate |
| `GET /api/questions/{id}/history` | Probability time series |
| `POST /api/questions/{id}/refresh` | Re-run the agent pipeline |
| `POST /api/questions/{id}/evidence` | Ingest a signal, re-forecast immediately |
| `POST /api/questions/{id}/resolve` | Settle against reality; writes the track record |
| `GET /api/leaderboard` · `/calibration` · `/predictions` | Accuracy + Brier by category · reliability bins · resolved track record |
| `GET /api/stats` · `GET /api/categories` | System-level track record · coverage + base rates |
| `GET /api/brief` | Morning brief (top mispricings) |
| `GET /api/discover/candidates` · `POST /api/discover` | Autonomous research mode |
| `GET /api/cards/{id}.svg` | Shareable prediction card |
| `GET /api/markets` · `POST /api/markets/{id}/trade` | Play-money market over real synced events — [docs/TRADING.md](docs/TRADING.md) |

Full reference: [docs/API.md](docs/API.md).

## Tests

```bash
make verify   # lint + the full backend suite + live build + static export
# or just the suite:
cd backend && .venv/bin/python -m pytest tests/ -q
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
- The synthetic demo corpus deliberately claims **no edge** (vanta's simulated estimates derive from the market signal, never the outcome). The only accuracy numbers that mean anything come from the real-market backtest over ingested Polymarket/Kalshi events.
- The prediction market is **paper trading only**: ⓥ credits are virtual, worthless, and non-redeemable. No deposits, no withdrawals, no fees, no payouts — the events and prices are real, the money never is. vanta is an educational forecasting terminal, not a gambling product.
- Auth is deliberately light: `vk_` API keys are the trading identity and an opt-in gate (`REQUIRE_API_KEY=1`) for operator mutations — sessions, roles, and OAuth are out of scope for the demo.

## Roadmap

Autonomous question discovery · real market/news ingest · resolution pipeline writing the leaderboard · personal prediction profiles · AI forecaster tournament.
