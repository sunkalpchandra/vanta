# Changelog

All notable changes to vanta are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

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
  static demo mode for GitHub Pages.

### Planned

- Live prediction-market and news ingest replacing the seeded corpus.

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
