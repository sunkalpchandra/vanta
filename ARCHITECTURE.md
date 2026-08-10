# vanta architecture

This document explains how a forecast is actually produced: the request flow,
the seven agents and their contracts, the quant math underneath them, the
boundary between deterministic numbers and optional LLM prose, the data model,
and the seeding design. Every path and symbol below exists in the code.

## Request flow for a forecast

`POST /api/questions` lands in `ask_question` in
`backend/app/routers/questions.py`. From there:

1. **Create** — `create_question` (`backend/app/service.py`) inserts a
   `Question` row plus any `Evidence` rows. If the caller supplies no
   `market_probability`, the category base rate from `base_rate_for`
   (`backend/app/agents/historian.py`) stands in as the market prior, flagged
   by zero volume and `low` liquidity so downstream agents trust it less.
2. **Run** — `run_and_store_forecast` (`backend/app/service.py`) converts the
   ORM rows into a plain `QuestionContext` via `build_context`, then calls
   `run_pipeline` (`backend/app/agents/orchestrator.py`). The pipeline is pure
   computation over dataclasses; it never touches the database.
3. **Persist** — the service deletes the question's previous `AgentReport`
   rows and writes one fresh report per agent, then appends a new `Forecast`
   row. Agent reports are replace-on-run; forecast history is append-only.
4. **Respond** — `_detail` assembles the `QuestionDetail` response: question,
   latest forecast, evidence, and the full agent debate.

`POST /api/questions/{id}/refresh` reuses steps 2-4 on an existing question.

## Pipeline

```
                       QuestionContext
     (question, category, horizon, market state, evidence)
                              │
        ┌──────────┬──────────┼──────────┬──────────┐
        ▼          ▼          ▼          ▼          ▼
    research     quant      market   sentiment  historian     five independent
    evidence    analogs +  consensus   mood /    base rate     estimators
      tilt     Monte Carlo  + trust   momentum  + horizon      (ESTIMATORS)
        │          │          │          │          │
        └──────────┴──────────┼──────────┴──────────┘
                              ▼
                           skeptic        attacks the interim consensus;
                     (probability=None,   emits risk_factors and a
                        weight=0)         confidence_haircut
                              │
                              ▼
                          synthesis       pool() in log-odds space
                     weighted log-odds    → shrink_to_base_rate()
                      pooling + shrink    → agreement_confidence() − haircut
                              │
                              ▼
              PipelineResult(probability, confidence,
                    reasoning, risk_factors, edge)
```

`run_pipeline` iterates `ESTIMATORS` (a module-level list of the five
estimator instances), feeding each agent the outputs of the agents before it,
then runs `SkepticAgent` over the estimator outputs and `SynthesisAgent` over
everything. The result is a `PipelineResult` with the probability rounded to
four decimals, plus `edge = final probability − market probability`.

## The agent contract

Every agent subclasses `Agent` in `backend/app/agents/base.py`:

```python
def run(self, ctx: QuestionContext, prior_outputs: list[AgentOutput]) -> AgentOutput
```

`AgentOutput` carries `agent`, `stance` (bull/bear/neutral), `probability`
(`None` for agents that don't estimate), `weight` (its influence in the
Bayesian pool; `0` means not pooled), `argument` (prose), and `details`
(structured dict, surfaced in Debate Mode). An agent abstains by returning
`probability=None, weight=0.0` — the pool filters on
`o.probability is not None and o.weight > 0`, deliberately not truthiness, so
a `0.0` estimate counts as a maximally bearish vote rather than vanishing
(regression-tested in `backend/tests/test_agents_zero_probability.py`).

### The seven agents

| Agent | File | Inputs | Estimate | Weight |
|---|---|---|---|---|
| research | `agents/research.py` | evidence sentiment × impact | market logit + `tilt × 1.2`, where `tilt = (pos−neg)/(pos+neg+1)` | 1.0-1.5, grows with evidence mass |
| quant | `agents/quant_agent.py` | `REFERENCE_EVENTS` analogs | similarity-weighted hit rate, clamped to [0.05, 0.95] | `0.6 + min(0.9, n×0.09)`; **0 (abstains)** when no analogs clear the similarity gate |
| market | `agents/market.py` | market price, volume, liquidity | the market probability itself | 0.6 / 1.0 / 1.3 by liquidity, +0.2 above $1M volume |
| sentiment | `agents/sentiment.py` | evidence impact shares | `inv_logit((positive_share − 0.5) × 2.2)` | 0.45 flat (noisy signal); 0 when no evidence |
| historian | `agents/historian.py` | `CATEGORY_BASE_RATES`, horizon | market pulled toward base rate by `min(0.5, horizon_days/720)` in log-odds | 0.7 |
| skeptic | `agents/skeptic.py` | all prior outputs, evidence | **none** (`probability=None`) | 0 — contributes `risk_factors` and a `confidence_haircut` instead |
| synthesis | `agents/synthesis.py` | all prior outputs | the final pooled forecast | 0 — it is the output, not a pool input |

The skeptic recomputes the interim consensus with `pool()`, takes the opposite
stance, collects the strongest opposing evidence plus category-specific
structural risks (`CATEGORY_RISKS`), and computes
`haircut = min(2.5, divergence×6 + max(0, 1.2 − evidence_depth×0.3))` — larger
when vanta diverges further from the market on thinner evidence. The haircut
hits **confidence only**, never the probability.

## The quant core (`backend/app/quant/`)

All numbers come from three small, dependency-free modules.

### Log-odds pooling — `bayes.pool`

Estimates are combined as a logarithmic opinion pool:

```
z = Σ wᵢ · logit(pᵢ) / Σ wᵢ        final = inv_logit(z)
```

Pooling in log-odds space keeps extreme-but-confident estimates from being
washed out by averaging in probability space, and makes the pool associative
with the other logit-space operations. Probabilities are clamped to
`[1e-6, 1−1e-6]` (`bayes.clamp`) before `logit`.

### Base-rate shrinkage — `bayes.shrink_to_base_rate`

`z = (1−s)·logit(p) + s·logit(base_rate)`. The synthesis agent applies
`strength=0.12` against `base_rate_for(ctx.category)` — a mild pull toward the
long-run category frequency to correct pooled overconfidence.

### Agreement confidence — `bayes.agreement_confidence`

Confidence (0-10) is computed from the weighted variance of agent logits
around the pooled logit:

```
score = 5.5 + min(4.0, |z_pooled|×1.6) − min(4.5, variance×1.6)
```

Decisive pooled estimates (far from 50%) raise it; inter-agent disagreement
lowers it. The caps make the raw score span [1.0, 9.5]; the skeptic's haircut
is then subtracted with a floor of 1.0.

### Beta-posterior Monte Carlo — `montecarlo.simulate`

The quant agent treats its analog hit rate as the mean of a
`Beta(p·s, (1−p)·s)` posterior, where the pseudo-sample size
`s = max(2, evidence_strength)` (it passes `4 + n_analogs`). 20,000 draws with
a fixed seed (`random.Random(7)`) yield a 90% credible interval (5th/95th
percentiles) and `p_above_market`, the share of draws exceeding the market
price. Fixed seed means the whole pipeline is bit-for-bit deterministic
(asserted in `backend/tests/test_pipeline.py`).

### Analog matching — `analogs.find_analogs`

Questions are tokenized (`analogs.tokenize`, stopword-filtered) and scored
against `REFERENCE_EVENTS` in `backend/app/data.py` by Jaccard overlap plus a
0.35 same-category bonus — the bonus applies only when token overlap is
non-zero, so category membership alone can never clear the `min_similarity=0.2`
gate and the quant agent retains the ability to abstain. The top 20 matches
produce a similarity-weighted hit rate: closer analogs count for more.

### Scoring and self-measurement

`quant/scoring.py` scores resolved forecasts: Brier, log score, directional
accuracy, index-assigned calibration bins, and the Murphy decomposition
(reliability − resolution + uncertainty). `quant/backtest.py` runs a
leave-one-out replay of the analog engine over the reference corpus and always
reports the always-predict-the-base-rate benchmark beside its own numbers
(`GET /api/quant/backtest`, surfaced on the methodology page).

### The learned base rate

Agents never touch the database, so `service.learned_base_rate` computes a
blended category prior — the static rate in `historian.CATEGORY_BASE_RATES`
acting as ~20 phantom resolutions, with the observed resolved record taking
over as real outcomes accumulate — and passes it into `QuestionContext.
base_rate`. The historian and synthesis shrinkage both prefer it; the static
table remains the cold-start fallback.

### The internal forecaster competition

`resolve_question` freezes every estimating agent's final probability into
`agent_track_records` at settlement. `GET /api/agents/leaderboard` scores each
agent (Brier, log score, accuracy) against outcomes — the check on whether the
synthesis pool actually beats its own inputs. The skeptic never estimates and
is deliberately absent.

## Deterministic math vs. optional LLM — `backend/app/llm.py`

The boundary is one function: `narrate(system, prompt, fallback)`. Exactly
three agents call it — research, skeptic, synthesis — and only for their
`argument`/`reasoning` strings. Every probability, weight, confidence, and
risk list is computed before `narrate` is called and passed *into* the prompt;
nothing numeric is ever parsed *out* of the response. Without
`ANTHROPIC_API_KEY` (or on any API error or refusal), `narrate` returns the
deterministic template `fallback`, so the system runs fully offline and the
tests never depend on the network. `llm_available()` is reported by
`GET /api/health`.

## Data model (`backend/app/models.py`)

| Table | Purpose |
|---|---|
| `questions` | The question, category, horizon, and market snapshot (price, volume, liquidity). |
| `forecasts` | Append-only forecast history per question — powers the probability time-series chart and `GET /api/questions/{id}/history`. |
| `evidence` | Per-question signals: source, summary, sentiment, impact (0-1). Input to research/sentiment/skeptic. |
| `agent_reports` | One structured row per agent per run: stance, probability, argument, details JSON. |
| `predictions` | Resolved historical predictions (market vs vanta vs outcome) — feeds the leaderboard's accuracy and Brier scores. |
| `users` | Identity: the `vk_` API-key credential (operator gating + trading identity) and the play-money ⓥ balance (default 10,000). |
| `market_events` | The real-venue corpus (Polymarket/Kalshi), including the live-trading columns `active` / `yes_price` / `last_synced`. |
| `positions` | One row per (user, event, side): shares, per-share cost basis, realized P&L, settled flag. |
| `trades` | Append-only execution log; `cost` is the signed balance delta. |

`agent_reports` exists so Debate Mode can render the full seven-agent argument
— including each agent's structured `details` (analog lists, credible
intervals, haircuts) — without re-running the pipeline on every page view.
Reports are replaced on each run because the debate reflects the *current*
forecast; the numeric trail lives in the append-only `forecasts` table.

## Seeding and resumability (`backend/app/seed.py`)

The FastAPI lifespan in `backend/app/main.py` runs
`Base.metadata.create_all` and then `seed_if_empty` on every boot.
`seed_if_empty` is resumable by construction: `_seed_questions` diffs
`SEED_QUESTIONS` against existing question text and only creates the missing
ones (running the real pipeline on each), and the resolved-prediction corpus
is checked independently. A startup interrupted mid-seed completes on the
next boot instead of being blocked by a partial database.

Two backfills make the demo feel lived-in, both deterministic by seed:

- `_backfill_history` writes a 30-day *reverse* random walk in log-odds space
  (`random.Random(question.id × 7919)`, steps `gauss(0, 0.12)`) that ends
  exactly at the live forecast.
- `_seed_resolved_predictions` derives a track record from
  `REFERENCE_EVENTS` (`random.Random(1337)`): both market and vanta estimates
  are noised around the true outcome, with vanta's noise tighter (σ 0.13 vs
  0.22). The leaderboard edge is therefore a modeled property of the demo
  seed, as the README states — not a validated live record.

## Read-side routers

`feed.py` ranks discovery cards by |edge|; `brief.py` caches the top
mispricings for 10 minutes (Redis via `REDIS_URL`, else in-process);
`leaderboard.py` computes directional accuracy and Brier scores per category
from `predictions`; `cards.py` renders self-contained SVG share cards.

## Test pyramid

Three layers, each pinned to what it alone can catch:

- **Backend pytest** (`backend/tests/`): quant invariants (property-based via
  hypothesis), API contracts, the resolution race, middleware ordering (CORS
  outermost, cache headers 2xx-only), seed-resume repair, and snapshot-export
  lockstep with the frontend's expected filenames.
- **Frontend vitest** (`frontend/lib/*.test.ts`): pure logic — feed filtering,
  sparkline math, day-merge chart bucketing, starred persistence, formatting.
- **Playwright e2e** (`frontend/e2e/`): the built static export served under
  the real `/vanta` base path — the exact artifact GitHub Pages deploys.
  Covers feed rendering and filtering, question-page chart/debate, keyboard
  paging, the brief, leaderboards, and the honest demo-corpus labeling.

The e2e server (`e2e/serve.sh`) symlinks `out/` under a `/vanta` prefix so
basePath-relative links resolve exactly as they do in production.

## Real-market subsystem (v0.3)

`app/ingest/` pulls resolved binary markets from Polymarket (Gamma, keyset
paging past the offset cap) and Kalshi (public cursor API, aggressive junk
filtering) into `market_events` — deliberately separate from `questions` so a
100k-row corpus can't affect product hot paths. A budgeted, checkpointed
price pass fills `price_7d`/`price_30d` from venue price history via
`price_at`, which never reads points after the cutoff (leakage-tested).

`app/backtest.py` scores each priced resolved event by rebuilding the exact
live `QuestionContext` at T−h: venue price as market_probability, empty
evidence, `narratives=False`, leave-one-out category base rates. vanta and
the market are scored on identical snapshots against Brier/log/accuracy plus
an always-predict-the-base-rate benchmark. Results are idempotent per
(event, horizon) by unique index.

`scripts/promote_events.py` lifts top-volume ACTIVE Polymarket markets into
`questions`, so the live feed carries real bets with real venue prices.

## Play-money trading + market sync (v0.4)

The market layer turns the `market_events` corpus into a paper-trading
surface: **play money · paper trading · real market prices**. ⓥ credits are
virtual and non-redeemable; the events and prices are real.

**Identity.** Trading rides on the existing auth-lite users: `POST /api/users`
mints the `vk_` key (returned once), and — unlike operator gating, which is
opt-in — trading endpoints always resolve `X-API-Key → User`, because a trade
must belong to an account. Accounts open at ⓥ10,000 (`User.balance`).

**Trades.** `app/trading.py` is the engine; `routers/markets.py` the API. A
trade executes at the event's current synced `yes_price` (NO prices at
`1 − yes_price`, kept at 6 decimals). Validation is strict and server-side:
shares > 0, price strictly in (0, 1), sells capped at held shares, balance
never negative, buys below the ⓥ0.01 minimum notional rejected. Money rounds
to 2 decimals at the boundaries (trade cost, balance delta);
intermediate math keeps full precision. Each execution appends a `trades` row
whose `cost` is the signed balance delta — the account is auditable by
replaying its log — and upserts the unique (user, event, side) `positions`
row: buys blend `avg_price`, sells realize P&L against it.

**Settlement.** When a venue resolves an event, open positions settle at ⓥ1
per winning share, ⓥ0 per losing share, crediting balances and booking
`realized_pnl` (`trading.settle_event`). The `settled` flag makes settlement
idempotent — settled positions are skipped, so the sync engine can call it on
every pass and a re-run or crash mid-settle never double-pays. The trader
leaderboard ranks lifetime P&L = equity (balance + open positions marked to
current prices) − the ⓥ10,000 start; accounts that never traded are excluded.

**Sync.** `scripts/sync_markets.py` reconciles the corpus against the venues'
current listings, deliberately stateless — no cursors or checkpoint files;
every run converges to venue truth, so crashes and re-runs are harmless. Four
transitions: **add** (new active venue markets), **update** (`yes_price` +
`last_synced` refresh), **deactivate** (closed/delisted markets leave the
tradable surface; positions persist until settlement), **settle** (venue
outcomes recorded, positions paid). Prices flow only through this
deterministic path — the LLM layer never touches a number, and never touches
money.

**Deployment.** The Pages workflow re-bakes on a 6-hour cron: it seeds a
workspace database, runs the sync into it (best-effort — venue hiccups fall
back to the deterministic seed), and exports the snapshot from that DB, so
the static demo tracks current real events between pushes. Existing databases
predating v0.4 take the new columns via `scripts/migrate_v04.py`
(`create_all` adds tables, never columns).

## Reasoning chat (v0.3)

`app/agents/streaming.py` re-drives the pipeline's exact agent sequence as a
generator; `routers/chat.py` streams it as SSE (status → agent events →
evidence → related → forecast → done). Matched questions replay read-only;
question creation honors operator gating. The stream owns its session — the
request-scoped one closes before FastAPI consumes the generator. ChatConsole
parses the stream with `lib/sse.ts` (chunk-boundary tested) and renders the
debate progressively; static mode shows a clearly-labeled example transcript.
