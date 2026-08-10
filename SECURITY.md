# Security

vanta is a demo/research codebase, not a hardened production service. Treat it
accordingly:

- **Auth is opt-in, off by default.** Operator mutations (resolve, market,
  evidence, refresh, discovery, watchlist writes) can be gated behind
  `X-API-Key` — including ask (it runs the full pipeline) and note writes — by setting `REQUIRE_API_KEY=1` (register keys via
  `POST /api/users`; keys are stored in plaintext — treat the DB as sensitive).
  Reads and `POST /api/questions` stay open, and a sliding-window rate limit
  (`RATE_LIMIT_PER_MINUTE`, per-process) guards all mutations. This is
  demo-grade: do not expose the backend to the public internet as-is.
- **Containers run unprivileged** (backend: dedicated user; frontend: `node`),
  with OS security upgrades applied at build. Base-image CVEs that upstream
  hasn't patched remain — rebuild images regularly.
- **Reporting.** Report vulnerabilities by opening a GitHub issue on this
  repository. There is no bug bounty; a clear reproduction is the most useful
  thing you can provide.
- **Never commit API keys.** `backend/.env` and `frontend/.env.local` are
  gitignored; keep secrets there and copy from `.env.example`. If a key does
  land in history, revoke it — removing the commit is not enough.
- **Scope of `ANTHROPIC_API_KEY`.** The key only enables Claude-written
  narrative text (`backend/app/llm.py`). All probabilities, confidences, and
  weights come from the deterministic quant engine, so a leaked or abused key
  cannot alter any forecast number — the blast radius is prose and API spend.
- CORS is restricted to `FRONTEND_ORIGIN` (default `http://localhost:3000`).
- The default SQLite database (`backend/vanta.db`) is a local file containing
  only seeded demo data.
