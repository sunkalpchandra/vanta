# The play-money market

> **play money · paper trading · real market prices.** vanta's market is an
> educational paper-trading terminal: the events are real (synced from
> Polymarket and Kalshi), the prices are real venue prices, the money is not.
> ⓥ credits are virtual, worthless, and non-redeemable. No deposits, no
> withdrawals, no fees, no real money — ever.

## How it works

1. **Register** — `POST /api/users` with an email (open, no auth needed). The
   response contains your `vk_...` API key **once** — store it. Every trading
   call identifies you by this key (`X-API-Key` header); trading endpoints
   always require it, even when the rest of the API runs ungated.
2. **Start with ⓥ10,000** — every account opens with a play-money balance of
   10,000 vanta credits.
3. **Trade real events** — active markets synced from Polymarket and Kalshi
   carry a live YES price in (0, 1), interpreted as the probability of YES.
   You buy or sell **YES** or **NO** shares at the current synced venue price
   (NO shares price at `1 − yes_price`). Each share settles at ⓥ1 if your
   side wins, ⓥ0 if it loses.
4. **Settlement** — when the venue resolves an event, the sync engine records
   the outcome and settles open positions at ⓥ1/ⓥ0 per share. Settlement
   credits your balance and books the result into your realized P&L.
5. **Leaderboard** — `GET /api/markets/traders` ranks by **lifetime P&L**:
   current equity (balance + open positions marked to current prices) minus
   the ⓥ10,000 everyone starts with. Accounts that never traded are excluded,
   and only a display handle is shown — never your full email.

## The rules (money math)

These are invariants, enforced server-side and regression-tested:

- Quantities must be positive; execution prices must lie strictly in (0, 1).
- Amounts that hit a balance (costs, proceeds, payouts, realized P&L) round to
  2 decimals; execution prices keep 6 decimals so NO-side complements
  (`1 − yes_price`) don't accumulate float noise. Intermediate math stays
  full-precision.
- Balances can never go negative: a buy is rejected if its cost exceeds your
  balance. Buys whose cost would round below ⓥ0.01 are rejected too — no
  free shares.
- Sells are capped at the shares you actually hold (no shorting, no leverage).
- No fees, no spread, no slippage model: you trade at the synced venue price.
- Prices come from deterministic sync code only — the LLM narrative layer
  never touches a number, and never touches money.

## Under the hood (data model)

- **`positions`** — one row per (user, event, side), holding `shares`, the
  per-share cost basis `avg_price`, accumulated `realized_pnl`, and a
  `settled` flag. Buys move the average price; sells realize P&L against it.
- **`trades`** — an append-only execution log. `cost` is the signed balance
  delta (negative = spent), so an account's history is auditable by summing
  its trades against its balance.
- **`market_events`** — the real-venue corpus. The live-trading columns are
  `active` (tradable now), `yes_price` (current venue YES price), and
  `last_synced`.

## The sync engine

`backend/scripts/sync_markets.py` reconciles the local corpus against the
venues' current listings. Each run is stateless — no cursor files, no local
state; it converges to the venue truth and is safe to re-run or interrupt:

- **add** — active venue markets not yet in the corpus are ingested and
  flagged `active`.
- **update** — already-known active markets get a fresh `yes_price` and
  `last_synced` stamp.
- **deactivate** — markets the venue has closed or delisted flip
  `active = False`, so they leave the tradable surface (open positions remain
  until settlement).
- **settle** — venue-resolved markets record their outcome and settle open
  positions at ⓥ1/ⓥ0 per share. Settlement is idempotent: a re-run never
  pays a position twice.

The GitHub Pages demo re-bakes on a 6-hour cron
(`.github/workflows/pages.yml`): seed a workspace DB, sync fresh active
markets into it, export the snapshot — so the deployed static demo tracks
current real events without a push.

## Reproduce locally

```bash
cd backend

# one-time: databases created before v0.4 need the trading columns
.venv/bin/python scripts/migrate_v04.py            # add --db PATH for a non-default DB

# pull current active markets + prices (re-runnable; venue APIs, no keys)
.venv/bin/python scripts/sync_markets.py --polymarket-pages 20 --kalshi-pages 2

# register and trade (backend running: make dev-api)
curl -s -X POST localhost:8000/api/users -H 'content-type: application/json' \
  -d '{"email": "you@example.com"}'                # note the vk_ key — shown once
```

Then trade with your key in the `X-API-Key` header — see the play-money
market section of [docs/API.md](API.md) for the endpoint table.

There are no `make sync` / `make trade-demo` targets yet; the commands above
are the reproduce path.

## What this is for

Paper trading against real venue prices is a calibration exercise: it forces
point beliefs into positions, marks them against the world's aggregated
belief, and settles them against reality. It is not, and will never become,
a way to stake real money on anything.
