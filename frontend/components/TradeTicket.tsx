"use client";

import { useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { IS_STATIC } from "@/lib/config";
import { pct } from "@/lib/format";
import {
  authHeaders,
  ensureTrader,
  fmtCredits,
  getTraderKey,
  readableError,
  sidePrice,
  tradeCost,
  type MarketItem,
  type TradeResponse,
} from "@/lib/trader";

const PLAY_MONEY_LINE = "Play money — paper trading at real market prices.";

/** Inline buy/sell ticket for one active market. Virtual ⓥ credits only. */
export function TradeTicket({ market }: { market: MarketItem }) {
  const [side, setSide] = useState<"yes" | "no">("yes");
  const [action, setAction] = useState<"buy" | "sell">("buy");
  const [shares, setShares] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TradeResponse | null>(null);
  // Hydration-safe: read localStorage only after mount.
  const [hasKey, setHasKey] = useState(false);
  const [email, setEmail] = useState("");

  useEffect(() => {
    if (!IS_STATIC) setHasKey(getTraderKey() !== null);
  }, []);

  if (IS_STATIC) {
    return (
      <div className="text-sm text-muted">
        Trading is disabled in the static demo — run the backend to trade this market with
        ⓥ10,000 play credits.
        <div className="micro-label mt-2">play money · paper trading · real market prices</div>
      </div>
    );
  }

  const yesPrice = sidePrice(market.yes_price, "yes");
  if (yesPrice === null) {
    return (
      <div className="text-sm text-muted">
        No live price for this market yet — the venue sync hasn&apos;t priced it.
        <div className="micro-label mt-2">play money · paper trading · real market prices</div>
      </div>
    );
  }

  const price = sidePrice(market.yes_price, side);
  const qty = Number(shares);
  const preview = tradeCost(qty, price);

  async function register(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await ensureTrader(email);
      setHasKey(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed — is the backend running?");
    } finally {
      setBusy(false);
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!(qty > 0)) {
      setError("Enter a share quantity above zero.");
      return;
    }
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`${API_URL}/api/markets/${market.id}/trade`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ side, action, shares: qty }),
      });
      if (res.status === 401) {
        setHasKey(false);
        throw new Error("Trading key rejected — register again to keep trading.");
      }
      if (!res.ok) throw new Error(await readableError(res, `Trade failed (${res.status}).`));
      setResult((await res.json()) as TradeResponse);
      setShares("");
    } catch (err) {
      setError(
        err instanceof Error && !(err instanceof TypeError)
          ? err.message
          : "Trade failed — is the backend running?",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      {!hasKey ? (
        <form onSubmit={register} className="flex flex-wrap items-center gap-2">
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            aria-label="Email for your play-money account"
            className="w-56 rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm text-ink outline-none placeholder:text-muted focus:border-accent"
          />
          <button
            type="submit"
            disabled={busy}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "Creating…" : "Start trading with ⓥ10,000"}
          </button>
          <p className="w-full text-xs text-muted">
            Free play-money account — your trading key is stored in this browser only.
          </p>
        </form>
      ) : (
        <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
          <div>
            <div className="micro-label mb-1.5">side</div>
            <div role="group" aria-label="Side" className="inline-flex overflow-hidden rounded-lg border border-line">
              {(["yes", "no"] as const).map((s) => {
                const p = sidePrice(market.yes_price, s);
                return (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setSide(s)}
                    aria-pressed={side === s}
                    className={`num px-3 py-1.5 text-xs font-bold uppercase transition-colors ${
                      side === s ? "bg-surface-2 text-accent" : "text-ink-2 hover:text-ink"
                    }`}
                  >
                    {s} {p !== null ? pct(p) : "—"}
                  </button>
                );
              })}
            </div>
          </div>
          <div>
            <div className="micro-label mb-1.5">action</div>
            <div role="group" aria-label="Action" className="inline-flex overflow-hidden rounded-lg border border-line">
              {(["buy", "sell"] as const).map((a) => (
                <button
                  key={a}
                  type="button"
                  onClick={() => setAction(a)}
                  aria-pressed={action === a}
                  className={`px-3 py-1.5 text-xs font-bold uppercase transition-colors ${
                    action === a ? "bg-surface-2 text-accent" : "text-ink-2 hover:text-ink"
                  }`}
                >
                  {a}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label htmlFor={`shares-${market.id}`} className="micro-label mb-1.5 block">
              shares
            </label>
            <input
              id={`shares-${market.id}`}
              type="number"
              min="0"
              step="any"
              required
              value={shares}
              onChange={(e) => setShares(e.target.value)}
              placeholder="0"
              className="num w-24 rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-sm text-ink outline-none placeholder:text-muted focus:border-accent"
            />
          </div>
          <div className="min-w-24">
            <div className="micro-label mb-1.5">{action === "buy" ? "cost" : "proceeds"}</div>
            <div className="num py-1.5 text-sm font-bold text-ink">
              {preview !== null ? fmtCredits(preview) : "—"}
            </div>
          </div>
          <button
            type="submit"
            disabled={busy || preview === null}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-40"
          >
            {busy ? "Working…" : `${action === "buy" ? "Buy" : "Sell"} ${side.toUpperCase()}`}
          </button>
        </form>
      )}
      {error && <p className="mt-3 text-xs text-neg">{error}</p>}
      {result && (
        <p className="num mt-3 rounded-lg border border-line bg-surface-2 px-3 py-2 text-xs text-ink-2">
          Filled: {result.trade.action} {result.trade.shares} {result.trade.side.toUpperCase()} @{" "}
          {result.trade.price.toFixed(2)} · balance {fmtCredits(result.balance)} · position{" "}
          {result.position.shares} {result.position.side.toUpperCase()} @ avg{" "}
          {result.position.avg_price.toFixed(2)}
        </p>
      )}
      <p className="micro-label mt-3">{PLAY_MONEY_LINE}</p>
    </div>
  );
}
