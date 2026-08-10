# Security

vanta is a demo/research codebase, not a hardened production service. Treat it
accordingly:

- **No authentication.** A `users` table exists in the schema, but auth is not
  wired up. Every API endpoint — including `POST /api/questions`, which runs
  the full pipeline — is unauthenticated. Do not expose the backend to the
  public internet as-is.
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
