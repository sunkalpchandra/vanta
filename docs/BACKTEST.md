# The real-market backtest

The synthetic demo corpus claims no edge by construction — simulated vanta
estimates derive from the market signal, never the outcome. (An earlier seed
noised vanta around the known outcome, which rigged the demo leaderboard to
~100% accuracy. That number was meaningless, and it's gone.)

The only accuracy claims vanta makes come from this backtest.

## Methodology

1. **Corpus** — resolved binary markets ingested from Polymarket (Gamma API)
   and Kalshi (public trade API): `make ingest` →
   `scripts/ingest_polymarket.py` / `scripts/ingest_kalshi.py`. Both are
   checkpointed and resumable; junk (multivariate combos, ambiguous
   settlements, empty titles) is rejected at normalization.
2. **Pre-resolution prices** — for each resolved event the price pass fetches
   the venue's own history (CLOB daily prices / Kalshi candlesticks) and
   records the price at T−7d and T−30d **at-or-before the cutoff, never
   after** (`price_at` is leakage-tested).
3. **Scoring** — `POST /api/backtest/run?horizon=7` runs the exact live agent
   pipeline per event with: `market_probability` = the T−h price, **no
   evidence** (none was captured back then; fabricating any would leak the
   present into the past), `narratives=False` (zero LLM), and a category base
   rate learned **leave-one-out** from other events only.
4. **Comparison** — the market is scored on the identical T−h snapshot, plus
   an always-predict-the-base-rate no-skill benchmark. Brier, log score,
   directional accuracy, and calibration bins for all three.

## Reading the scorecard

Expect **vanta ≈ market**. The pipeline's only real information *is* the
market price plus corpus base rates; beating deep prediction markets from
their own price alone would be extraordinary, and this scorecard will say
whatever the data says. Its value is honest calibration measurement and a
harness where future real evidence sources (news ingest, filings) can prove
or disprove an edge on held-out data.

## Coverage caveats

- AMM-era Polymarket markets (pre-2022) expose no CLOB price history; they
  stay in the corpus but can't be scored (no pre-close price).
- Markets that lived under a day have no T−7d price by definition.
- The scorecard reports `coverage` (scored ÷ resolved corpus) and per-source
  counts — read them before quoting any number.
