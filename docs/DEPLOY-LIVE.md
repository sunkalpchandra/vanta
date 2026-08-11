# Deploy a live vanta (real backend, real trading)

GitHub Pages is static hosting — it can serve the read-only demo, but it can't
run a server, so the play-money **trading** there is either read-only or the
in-browser local engine. To let anyone register, trade, and appear on the
leaderboard against a shared, live backend, deploy the real thing.

The turnkey split: **backend + Postgres on [Render](https://render.com)** (the
server), **frontend on [Vercel](https://vercel.com)** (Next.js's native home),
pointed at the Render API. Both have free tiers; total cost is $0 to try.

Play money only throughout — ⓥ credits are virtual and worthless. This is not a
real-money product; do not represent it as one.

## 1 · Backend + database on Render

1. Push this repo to your GitHub account.
2. In Render → **New +** → **Blueprint**, select the repo. Render reads
   [`render.yaml`](../render.yaml) and provisions three things:
   - **vanta-db** — a managed Postgres database.
   - **vanta-api** — the FastAPI server (Docker). On first boot it creates the
     tables and seeds demo markets, so trading works immediately.
   - **vanta-sync** — a cron that every 30 min adds real Polymarket/Kalshi/
     Manifold markets, refreshes prices, records history, and settles resolved
     markets.
3. When it's up, note the API URL, e.g. `https://vanta-api.onrender.com`.
   Check `https://vanta-api.onrender.com/api/health` returns `{"status":"ok"}`.
4. Leave `FRONTEND_ORIGIN` blank for now (you'll set it after step 2). Any
   `*.vercel.app` origin is already allowed by the API's CORS regex, so preview
   deploys work out of the box.

> Render's free web service sleeps after inactivity and cold-starts in ~30s;
> the free Postgres expires after 90 days. Fine for a demo — upgrade the plans
> in `render.yaml` for anything real.

## 2 · Frontend on Vercel

1. In Vercel → **Add New… → Project**, import the same repo. Set the **Root
   Directory** to `frontend/`. Vercel detects Next.js and uses
   [`frontend/vercel.json`](../frontend/vercel.json).
2. Add an **Environment Variable**:
   - `NEXT_PUBLIC_API_URL` = your Render API URL (e.g.
     `https://vanta-api.onrender.com`).
   - Do **not** set `NEXT_PUBLIC_STATIC_MODE` — that's the offline Pages build.
3. Deploy. You'll get a URL like `https://vanta.vercel.app`.
4. Back in Render, set the **vanta-api** service's `FRONTEND_ORIGIN` env to that
   URL (comma-separate multiple origins if you have a custom domain too) and
   let it redeploy. CORS will now accept your frontend.

That's it — visitors can register (they get ⓥ10,000), trade real markets at
real synced prices, and show up on the shared leaderboard.

## Everything on Render (single platform, optional)

Prefer one dashboard? Add the frontend as a fourth Render service (Docker,
`frontend/Dockerfile`) with build arg `NEXT_PUBLIC_API_URL` set to the API URL,
and set the API's `FRONTEND_ORIGIN` to the web service URL. The Vercel split is
recommended only because Vercel handles Next.js build-time env the most simply.

## Local live stack (docker compose)

To run the whole live stack on your machine (Postgres + Redis + API + web):

```bash
docker compose up --build
# API at http://localhost:8000, frontend at http://localhost:3000
```

## What "works" on a fresh deploy

- **Immediately**: demo markets are seeded, so register → trade → portfolio →
  leaderboard all work end to end.
- **Within 30 min**: the sync cron populates real venue markets; they appear on
  the markets page and become tradeable at live prices.
- **Ongoing**: prices refresh, price-history charts fill in, and markets settle
  and pay out winners as the venues resolve them.
