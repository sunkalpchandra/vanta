.PHONY: dev-api dev-web test lint smoke snapshot static demo docker

# Curl every endpoint against a running backend (make dev-api first)
smoke:
	bash backend/scripts/smoke.sh

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
