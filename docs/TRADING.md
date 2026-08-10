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
- **House-favorable cent rounding.** Amounts that hit a balance round to 2
  decimals, but never in your favor: a buy's cost rounds **up** to the cent,
  while a sell's proceeds and every settlement payout round **down**. So no
  sequence of dust trades can skim fractions of a cent into free credits.
  Execution prices keep 6 decimals so NO-side complements (`1 − yes_price`)
  don't accumulate float noise, and intermediate math stays full-precision.
- **Minimum notional on both sides.** A trade's true notional (shares ×
  price) must be at least ⓥ0.01: below that a buy's cost would round to zero
  (free shares) and a repeated sell would be a rounding skim. The one
  exception is a sell that fully closes a position — always allowed, so a
  holder is never trapped in a sub-cent lot.
- Balances can never go negative: a buy is rejected if its (rounded-up) cost
  exceeds your balance.
- Sells are capped at the shares you actually hold (no shorting, no leverage).
- No fees and no spread — the fill is the synced venue price for your side.
- **Trading halts at close.** Once an event passes its `close_time` the synced
  price is stale (it may already have resolved off-feed), so trades are refused
  — "trading is halted pending settlement" — until the next sync flips the
  event inactive or resolved.
- **Slippage guard.** A trade may include `expected_price`, the YES/NO price
  the ticket showed. If the live synced price has drifted more than 2 cents by
  execution time the fill is rejected ("price moved: ...") instead of filling
  at the new price; omit it to accept whatever the current price is.
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
  positions at ⓥ1/ⓥ0 per share. Settlement is **position-driven**: a backstop
  sweep (`settle_resolved`) pays out *every* resolved event that still holds
  unsettled positions — whichever writer recorded the outcome — so no payout is
  orphaned by a budget cap or a missed time window. It is idempotent too: a
  re-run never pays a position twice.

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

Two Makefile targets wrap the sync loop: `make sync` runs one stateless pass
(`scripts/sync_markets.py`) and `make sync-loop` runs it as a daemon that
re-syncs every 30 minutes (`--loop 30`). There is no `trade-demo` target — the
`curl` calls above are the reproduce path for placing trades.

## What this is for

Paper trading against real venue prices is a calibration exercise: it forces
point beliefs into positions, marks them against the world's aggregated
belief, and settles them against reality. It is not, and will never become,
a way to stake real money on anything.
