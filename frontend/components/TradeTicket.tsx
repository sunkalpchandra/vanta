"use client";

import { useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { IS_STATIC } from "@/lib/config";
import { pct } from "@/lib/format";
import {
  authHeaders,
  clearTraderKey,
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
export function TradeTicket({
  market,
  onPriceStale,
}: {
  market: MarketItem;
  /** Optional: called when the backend rejects a trade because the price moved,
   *  so the parent can refetch the live price. Absent → the drift is surfaced only. */
  onPriceStale?: () => void;
}) {
  const [side, setSide] = useState<"yes" | "no">("yes");
  const [action, setAction] = useState<"buy" | "sell">("buy");
  const [shares, setShares] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Distinct, prominent notice for a rejected-on-drift (409 "price moved") fill.
  const [staleNotice, setStaleNotice] = useState<string | null>(null);
  const [result, setResult] = useState<TradeResponse | null>(null);
  // Hydration-safe: read localStorage only after mount.
  const [hasKey, setHasKey] = useState(false);
  const [email, setEmail] = useState("");

  useEffect(() => {
    // In the static demo the browser IS the account (localStorage engine), so
    // no registration key is needed; live mode reads the stored trading key.
    setHasKey(IS_STATIC || getTraderKey() !== null);
  }, []);

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
  const preview = tradeCost(qty, price, action);

  async function register(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setStaleNotice(null);
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
    if (price === null) {
      setError("No live price for this side right now — try again shortly.");
      return;
    }
    setBusy(true);
    setError(null);
    setStaleNotice(null);
    setResult(null);
    // Static demo: execute against the in-browser engine (localStorage), no
    // backend. Same money math as the server (parity-tested).
    if (IS_STATIC) {
      try {
        const { placeLocalTrade } = await import("@/lib/localTrader");
        const { trader, trade } = placeLocalTrade(
          { id: market.id, question: market.question, yes_price: market.yes_price, outcome: market.outcome ?? null, close_time: market.close_time },
          side,
          action,
          qty,
        );
        const pos = trader.positions.find((p) => p.event_id === market.id && p.side === side);
        setResult({
          balance: trader.balance,
          trade: { ...trade, question: market.question },
          position: pos
            ? { event_id: pos.event_id, side: pos.side, shares: pos.shares, avg_price: pos.avg_price, realized_pnl: pos.realized_pnl, settled: pos.settled }
            : { event_id: market.id, side, shares: 0, avg_price: 0, realized_pnl: 0, settled: false },
        });
        setShares("");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Trade rejected.");
      } finally {
        setBusy(false);
      }
      return;
    }
    try {
      const res = await fetch(`${API_URL}/api/markets/${market.id}/trade`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        // expected_price = the exact YES/NO price this ticket is showing for the
        // selected side; the backend 409s if the live price has drifted >0.02.
        body: JSON.stringify({ side, action, shares: qty, expected_price: price }),
      });
      if (res.status === 401) {
        // The stored key is stale/unknown; drop it BEFORE surfacing the error so
        // the onboarding path works on the next attempt instead of looping.
        clearTraderKey();
        setHasKey(false);
        throw new Error(
          "Your trading key is no longer valid — start trading again to get a new play-money key.",
        );
      }
      if (res.status === 409) {
        const detail = await readableError(res, "Price moved before your order filled — try again.");
        if (/price moved/i.test(detail)) {
          setStaleNotice(detail);
          onPriceStale?.(); // let the parent refetch the live price, if it can
          return; // handled: shown prominently, not as a generic error
        }
        throw new Error(detail);
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
      {IS_STATIC && (
        <p className="micro-label mb-3 rounded-lg border border-line bg-surface-2 px-3 py-2 text-ink-2">
          ⓥ Trading locally in your browser — nothing is sent anywhere. Your book persists on this
          device; clear site data to reset to ⓥ10,000.
        </p>
      )}
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
      {staleNotice && (
        <p
          role="alert"
          className="mt-3 rounded-lg border border-neg bg-surface-2 px-3 py-2 text-xs font-semibold text-neg"
        >
          {staleNotice} — the price updated; review it and resubmit.
        </p>
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
