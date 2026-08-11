import { describe, expect, it } from "vitest";
import {
  credit,
  debit,
  emptyTrader,
  execPrice,
  executeLocalTrade,
  LocalTradeError,
  localPortfolio,
  type LocalMarket,
} from "./localTrading";

const market = (over: Partial<LocalMarket> = {}): LocalMarket => ({
  id: 1,
  question: "Will the browser engine match the backend?",
  yes_price: 0.3,
  outcome: null,
  close_time: null,
  ...over,
});

describe("house-favorable rounding (parity with backend _debit/_credit)", () => {
  it("charges round UP, payouts round DOWN", () => {
    expect(debit(0.0052)).toBe(0.01);
    expect(credit(0.0052)).toBe(0);
    expect(debit(30)).toBe(30);
    expect(credit(55)).toBe(55);
  });
});

describe("executeLocalTrade — matches the Python engine's numbers", () => {
  it("buy 100 YES @0.30 debits ⓥ30 exactly (backend parity)", () => {
    const { trader, trade } = executeLocalTrade(emptyTrader(), market(), "yes", "buy", 100);
    expect(trader.balance).toBe(9970);
    expect(trade.cost).toBe(-30);
    expect(trader.positions[0]).toMatchObject({ side: "yes", shares: 100, avg_price: 0.3 });
  });

  it("sell after a price rise credits ⓥ55 (10025 total, backend parity)", () => {
    let t = executeLocalTrade(emptyTrader(), market(), "yes", "buy", 100).trader;
    t = executeLocalTrade(t, market({ yes_price: 0.55 }), "yes", "sell", 100).trader;
    expect(t.balance).toBe(10025);
    expect(t.positions[0].shares).toBe(0);
  });

  it("weighted-average cost basis on a second buy", () => {
    let t = executeLocalTrade(emptyTrader(), market({ yes_price: 0.2 }), "yes", "buy", 100).trader;
    t = executeLocalTrade(t, market({ yes_price: 0.4 }), "yes", "buy", 100).trader;
    expect(t.positions[0].shares).toBe(200);
    expect(t.positions[0].avg_price).toBeCloseTo(0.3, 6);
  });

  it("NO side trades at the complement price", () => {
    const { trade } = executeLocalTrade(emptyTrader(), market({ yes_price: 0.3 }), "no", "buy", 10);
    expect(trade.price).toBeCloseTo(0.7, 6);
  });

  it("dust sells cannot mint credits (min notional, full-exit exempt)", () => {
    const t = executeLocalTrade(emptyTrader(), market({ yes_price: 0.4 }), "yes", "buy", 100).trader;
    // 0.013 * 0.4 = 0.0052 < ⓥ0.01 and not a full exit -> rejected.
    expect(() => executeLocalTrade(t, market({ yes_price: 0.4 }), "yes", "sell", 0.013)).toThrow(
      LocalTradeError,
    );
  });

  it("rejects an unaffordable buy", () => {
    expect(() => executeLocalTrade(emptyTrader(), market({ yes_price: 0.5 }), "yes", "buy", 100_000)).toThrow(
      /insufficient balance/,
    );
  });

  it("halts trading past close_time", () => {
    const past = new Date(Date.now() - 3600_000).toISOString();
    expect(() =>
      executeLocalTrade(emptyTrader(), market({ close_time: past }), "yes", "buy", 10),
    ).toThrow(/close time/);
  });

  it("won't sell shares you don't hold", () => {
    expect(() => executeLocalTrade(emptyTrader(), market(), "yes", "sell", 10)).toThrow(/no shares/);
  });

  it("does not mutate the input trader (pure)", () => {
    const start = emptyTrader();
    executeLocalTrade(start, market(), "yes", "buy", 10);
    expect(start.balance).toBe(10000);
    expect(start.positions).toHaveLength(0);
  });
});

describe("localPortfolio", () => {
  it("marks positions to current prices and computes equity", () => {
    const t = executeLocalTrade(emptyTrader(), market({ yes_price: 0.3 }), "yes", "buy", 100).trader;
    const p = localPortfolio(t, () => 0.5); // price rose to 0.50
    expect(p.balance).toBe(9970);
    expect(p.equity).toBe(9970 + 100 * 0.5); // 10020
    expect(p.positions[0].unrealized_pnl).toBeCloseTo(100 * (0.5 - 0.3), 2);
  });

  it("execPrice complements for NO", () => {
    expect(execPrice(0.3, "yes")).toBeCloseTo(0.3, 6);
    expect(execPrice(0.3, "no")).toBeCloseTo(0.7, 6);
  });
});

describe("round2 banker's rounding (backend _round_money parity)", () => {
  it("rounds exact half-cents to even, not up", () => {
    // 1 share bought at 0.625, sold at 0.75 → realized 0.125 → 0.12 (not 0.13)
    let t = executeLocalTrade(emptyTrader(), market({ yes_price: 0.625 }), "yes", "buy", 1).trader;
    t = executeLocalTrade(t, market({ yes_price: 0.75 }), "yes", "sell", 1).trader;
    expect(t.positions[0].realized_pnl).toBe(0.12);
  });
});

describe("localPortfolio marks resolved positions to their settlement value", () => {
  it("a winning YES on a resolved market is worth ⓥ1/share, not the stale price", () => {
    const t = executeLocalTrade(emptyTrader(), market({ yes_price: 0.4 }), "yes", "buy", 100).trader;
    // Market resolved YES; stale price still 0.4 but outcome=1 → mark at 1.0.
    const p = localPortfolio(
      t,
      () => 0.4,
      () => 1,
    );
    expect(p.positions[0].current_price).toBe(1);
    expect(p.equity).toBe(9960 + 100 * 1); // 10060
  });
  it("a losing NO on a YES-resolved market marks to 0", () => {
    const t = executeLocalTrade(emptyTrader(), market({ yes_price: 0.4 }), "no", "buy", 10).trader;
    const p = localPortfolio(
      t,
      () => 0.4,
      () => 1,
    );
    expect(p.positions[0].current_price).toBe(0);
  });
});
