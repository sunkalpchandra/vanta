# Deployment

vanta ships in three shapes: bare local, docker compose, and a static GitHub Pages demo.
All three run the same code; they differ only in database, wiring, and whether a backend
exists at all.

## (a) Bare local — uvicorn + npm run dev

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload          # http://localhost:8000, docs at /docs

cd frontend
npm install && npm run dev                        # http://localhost:3000
```

No keys, no services. The backend defaults to `sqlite:///./vanta.db`, creates the schema at
startup, and seeds itself on first boot. Redis is optional — the morning-brief cache falls
back to an in-process TTL cache. Without `ANTHROPIC_API_KEY` the agents use template
narratives; the numbers are deterministic either way.

## (b) docker compose — Postgres 16 + Redis + api + web

```bash
docker compose up --build
```

Four services:

- **db** — `postgres:16-alpine`, data in the `pgdata` volume. Its healthcheck runs
  `pg_isready -h 127.0.0.1` — the `-h` forces TCP, because during first-boot initdb Postgres
  runs a socket-only temp server that a bare `pg_isready` would report healthy too early.
- **redis** — `redis:7-alpine`, wired to the api via `REDIS_URL`.
- **api** — built from `backend/Dockerfile` (python:3.12-slim, uvicorn on 8000). Talks to
  Postgres via `postgresql+psycopg://vanta:vanta@db:5432/vanta`. Starts only after db is
  healthy; its own healthcheck fetches `/api/health`, which round-trips a `SELECT 1`.
- **web** — built from `frontend/Dockerfile` (node:22-alpine, three stages: deps, build,
  `next start` on 3000). Starts only after api is healthy.

**The API_URL_INTERNAL split.** The frontend needs two different routes to the same API.
`NEXT_PUBLIC_API_URL=http://localhost:8000` is a *build arg* baked into the browser bundle —
what client-side fetches and share-card links use, via the host-published port.
`API_URL_INTERNAL=http://api:8000` is a runtime env var for SSR inside the web container —
there, `localhost:8000` would point at the web container itself and every server-rendered
page would come up empty.

## (c) GitHub Pages — baked static snapshot

Pages can't run FastAPI, so `.github/workflows/pages.yml` (push to `main`, or manual
dispatch; concurrent runs cancel superseded ones) bakes the API into files:

1. `python backend/scripts/export_snapshot.py --out frontend/public` boots the seeded app
   and walks the read API into `frontend/public/data/*.json` and `frontend/public/cards/*.svg`.
2. `npx next build` with `NEXT_PUBLIC_STATIC_MODE=1` and `NEXT_PUBLIC_BASE_PATH=/vanta`
   produces a static export in `frontend/out` — same pages, same charts, data read from the
   snapshot instead of the network.
3. `upload-pages-artifact` + `deploy-pages` publish `frontend/out`.

There is no backend at runtime, so anything that mutates — asking questions, ingesting
evidence, resolving — needs shape (a) or (b).

## Environment variables

Backend settings come from `backend/.env` (pydantic-settings, case-insensitive, extras
ignored); frontend settings from `frontend/.env.local` — Next.js does not read `backend/.env`.

**`backend/.env`:**

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./vanta.db` | Any SQLAlchemy URL; compose overrides with Postgres |
| `REDIS_URL` | *(unset)* | Brief cache backend; unset falls back to in-process |
| `ANTHROPIC_API_KEY` | *(unset)* | Enables Claude-written narratives |
| `VANTA_MODEL` | `claude-opus-5` | Model for narratives |
| `FRONTEND_ORIGIN` | `http://localhost:3000` | CORS allow-origin |
| `RATE_LIMIT_PER_MINUTE` | `240` | Mutating requests per client per minute; `0` disables |
| `REQUIRE_API_KEY` | `false` | Require `X-API-Key` on operator mutations |
| `GIT_SHA` | unset | Deployed commit, surfaced at `/api/meta` and in the baked snapshot's meta.json |

**`frontend/.env.local`:**

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Browser-side API base, baked at build time |
| `API_URL_INTERNAL` | *(falls back to public URL)* | SSR-side API base (compose: `http://api:8000`) |
| `NEXT_PUBLIC_STATIC_MODE` | *(unset)* | `1` reads the baked snapshot instead of the network |
| `NEXT_PUBLIC_BASE_PATH` | *(unset)* | Subpath prefix for Pages (`/vanta`) |

## The two guard flags

**Rate limiting** (`rate_limit_per_minute`, default 240) is a sliding-window limiter in
`main.py` middleware: POST/DELETE under `/api`, keyed by client IP, answering 429 with
`Retry-After: 60` when exceeded. **API-key gating** (`require_api_key`, default off) makes
mutations demand an `X-API-Key` minted by `POST /api/users` — the `vk_...` credential shown
once at creation. Both are off-by-default demo posture; flip them for anything shared.

## Honest scaling notes

- **SQLite is single-writer.** Fine for one uvicorn process; concurrent writers serialize
  and can hit lock errors. Any multi-process or multi-replica setup should point
  `DATABASE_URL` at Postgres, as compose does.
- **In-process caches are per worker.** Without `REDIS_URL`, the brief cache lives in each
  worker's memory: N workers means N independent caches, and cache invalidation on resolve
  only reaches the worker that handled the request. Set `REDIS_URL` before adding workers.
- **The rate limiter is per process and in memory.** The effective limit multiplies by
  worker and replica count, and state resets on restart. It is a demo-grade guard against
  runaway clients, not DDoS armor — enforce real limits at the edge.
- Read endpoints emit `Cache-Control` headers (feed 30s, brief/leaderboard/stats 60s, cards
  300s), so a fronting proxy or CDN can absorb read traffic without any app changes.
