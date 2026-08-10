# Changelog

All notable changes to vanta are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Planned

- Live prediction-market and news ingest replacing the seeded corpus.

## [0.2.0] - 2026-08-10

### Added

- Performance: constant-query feed/movers (was N+1), composite forecast index,
  batched `/api/feed/sparklines`, gzip, Cache-Control on tolerant reads,
  `X-Response-Time-Ms`, and a benchmark harness — measured in
  docs/PERFORMANCE.md.
- Market history: `market_snapshots` with a seeded 30-day walk, operator price
  ingest, per-question market series, and the dual-line vanta-vs-market chart
  with evidence-arrival markers.
- Explanation surfaces: leave-one-out evidence sensitivity (LLM-free
  counterfactual runs), what-changed diffs, related questions, derived alerts,
  difficulty scores, and per-agent calibration curves + receipts pages.
- Operator surface: auth-lite users + `X-API-Key` gating (opt-in), sliding
  rate limit, market/evidence/resolve controls, watchlist lifecycle, an
  operator CLI, and `/metrics` counters.
- Product surface: digest page, unified search, feed RSS, starred questions,
  CSV track record, PWA manifest, JSON-LD, "/" search shortcut.
- Quality: frontend vitest suite, hypothesis property tests, 85% coverage
  gate, snapshot-diff tool, request ids, hardened non-root images.

- Resolution lifecycle: `POST /api/questions/{id}/resolve` freezes a question
  against its actual outcome and writes the prediction into the leaderboard's
  track record; resolved questions leave the feed and brief, and refresh /
  evidence are rejected with 409.
- Scoring module (`quant/scoring.py`): Brier score, directional accuracy, and
  reliability-diagram calibration bins.
- Stats APIs: `GET /api/stats` (system-level track record and average edge),
  `GET /api/categories` (coverage + base rates), and
  `GET /api/leaderboard/calibration` (vanta vs market reliability bins).
- Evidence ingestion: `POST /api/questions/{id}/evidence` adds a signal and
  immediately re-runs the agent pipeline.
- Autonomous research mode (demo scope): `/api/discover` mints new questions
  from a curated watchlist, deduplicated by token overlap against existing
  questions, each forecast by the full pipeline.
- Static snapshot exporter (`backend/scripts/export_snapshot.py`) and a
  static demo mode for GitHub Pages, deployed at
  https://sunkalpchandra.github.io/vanta/ on every push to `main`.
- Archive page and `GET /api/leaderboard/predictions`: the full resolved track
  record with closer-call markers.
- Discovery panel on the ask page (live mode), confidence on brief items,
  RESOLVED stamps on settled share cards, `resolved=` question filter.
- Methodology page, calibration chart, stats bar, category filter chips,
  mobile-safe navigation, 404/error/loading states, OpenGraph metadata.

### Fixed

- Concurrent `POST /resolve` could double-settle a question (guarded UPDATE +
  unique index); a resolve landing mid-pipeline no longer corrupts the frozen
  record; the morning-brief cache is invalidated on resolution.
- Movers no longer emit zero-delta rows for questions with no forecast inside
  the window; brief ranks stay monotonic in |edge| after the diversity
  backfill; watchlist adds reject built-in duplicates and covered questions,
  and discovery can't mint duplicates within one call; seeding now finishes
  questions stranded forecast-less by a crash mid-boot; the sitemap lists
  category pages; the watch-a-signal form stays reachable at zero candidates.
- Calibration bins assigned by index — float bin edges dropped exact round
  quotes (0.30, 0.70) into the bin below.
- Backend test suite is order-independent (suite DB bound in conftest.py).

- Movement analytics: `GET /api/feed/movers` and a biggest-moves strip on the
  feed; 30-day sparklines on every feed card.
- Internal forecaster competition: resolution freezes each agent's final call
  into `agent_track_records`; `GET /api/agents/leaderboard` and the `/agents`
  page score research vs quant vs market vs historian vs synthesis.
- Scoring depth: log scores and the Murphy decomposition
  (reliability/resolution/uncertainty) on `GET /api/stats`.
- Question search (`?q=`), pagination (`limit`/`offset`), an analogs endpoint,
  and a DB probe on `/api/health`.
- Brief upgrades: category diversity (max 2 per category), copy-as-text
  sharing; two seed-time demo resolutions populate archive + agent pages.
- Operator controls on question pages (live mode): evidence ingest with
  immediate re-forecast, resolve YES/NO.
- Accessibility: skip-to-content link, search labels, mobile-safe nav labels.
- CI: live-server smoke job.
- Analog-engine backtest (`GET /api/quant/backtest`) published with its
  base-rate benchmark, surfaced on the methodology page.
- Learned category base rates: the historian and synthesis shrinkage blend
  the static prior with the observed resolved record.
- Watchlist lifecycle (list/add/delete) with a watch-a-signal form; feed sort
  options; per-category pages, calibration filter, and leaderboard links.
- Brief RSS feed (`/api/brief/rss`, baked as `brief.xml` in the demo);
  robots.txt + sitemap; per-question og:image share cards;
  prefers-reduced-motion support.

## [0.1.0] - 2026-08-10

### Added

- Seven-agent forecasting pipeline (research, quant, market, sentiment,
  historian, skeptic, synthesis) orchestrated in dependency order, with one
  structured report per agent per run.
- Deterministic quant engine: weighted Bayesian log-odds pooling,
  Beta-posterior Monte Carlo simulation, similarity-weighted historical
  analog matching, base-rate shrinkage, and agreement-based confidence.
- Optional Claude narrative layer (`ANTHROPIC_API_KEY`); template fallbacks
  keep the system fully offline-capable. Numbers never depend on the LLM.
- FastAPI backend: questions (ask/list/detail/history/refresh), intelligence
  feed ranked by edge, morning brief with Redis or in-process caching,
  accuracy leaderboard (directional accuracy + Brier by category), and
  shareable SVG prediction cards.
- Next.js 15 frontend: feed, question detail with Debate Mode, morning brief,
  leaderboard, and Ask vanta pages.
- Docker Compose stack (web, api, Postgres 16, Redis).
- Idempotent, resumable seeding: 12 demo questions with evidence and full
  agent runs, 30-day forecast history backfill, and a resolved demo track
  record for the leaderboard.

### Changed

- Databases created before the resolution feature must be deleted
  (`rm backend/vanta.db`) so the schema regenerates on next boot.
