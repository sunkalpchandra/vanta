.PHONY: dev-api dev-web test lint smoke snapshot static demo docker verify e2e

# The full pre-push gate: lint, tests, live build, static build
verify: lint test
	cd frontend && npx next build
	$(MAKE) static

# Curl every endpoint against a running backend (make dev-api first)
smoke:
	bash backend/scripts/smoke.sh

# Endpoint latency benchmark (fresh seeded DB, in-process)
bench:
	cd backend && .venv/bin/python scripts/bench.py --n 30

# Live backend on :8000 (seeds itself on first boot)
dev-api:
	cd backend && .venv/bin/uvicorn app.main:app --reload

# Live frontend on :3000
dev-web:
	cd frontend && npm run dev

test:
	cd backend && .venv/bin/python -m pytest tests/ -q

lint:
	cd backend && .venv/bin/ruff check app tests scripts

# Bake the static demo snapshot into frontend/public
snapshot:
	cd backend && .venv/bin/python scripts/export_snapshot.py --out ../frontend/public

# Full GitHub Pages build: snapshot + static export into frontend/out
static: snapshot
	cd frontend && NEXT_PUBLIC_STATIC_MODE=1 NEXT_PUBLIC_BASE_PATH=/vanta npx next build

docker:
	docker compose up --build

e2e: static
	cd frontend && npx playwright test

ingest:
	cd backend && .venv/bin/python scripts/ingest_polymarket.py --limit-events 75000 --no-prices && .venv/bin/python scripts/ingest_kalshi.py --limit-events 25000 --no-prices

ingest-prices:
	cd backend && .venv/bin/python scripts/ingest_polymarket.py --limit-events 0 --prices --price-budget 20000 && .venv/bin/python scripts/ingest_kalshi.py --limit-events 0 --prices --price-budget 5000

promote:
	cd backend && .venv/bin/python scripts/promote_events.py --count 25

sync:
	cd backend && .venv/bin/python scripts/sync_markets.py

sync-loop:
	cd backend && .venv/bin/python scripts/sync_markets.py --loop 30

agents:
	cd backend && .venv/bin/python scripts/run_agent_traders.py

backfill-ticks:
	cd backend && .venv/bin/python scripts/backfill_ticks.py

migrate:
	cd backend && .venv/bin/python scripts/migrate_v04.py && .venv/bin/python scripts/migrate_v05.py
