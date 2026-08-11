import { beforeEach, describe, expect, it } from "vitest";
import { loadLocalTrader, placeLocalTrade, resetLocalTrader, type Storage } from "./localTrader";
import { type LocalMarket } from "./localTrading";

function memoryStorage(initial: string | null = null): Storage {
  let value = initial;
  return {
    getItem: () => value,
    setItem: (_k, v) => {
      value = v;
    },
    removeItem: () => {
      value = null;
    },
  };
}

// jsdom provides window.localStorage under vitest.
const market: LocalMarket = {
  id: 7,
  question: "Persisted browser trade?",
  yes_price: 0.25,
  outcome: null,
  close_time: null,
};

describe("localTrader persistence", () => {
  let store: Storage;
  beforeEach(() => {
    store = memoryStorage();
  });

  it("starts every browser at ⓥ10,000", () => {
    expect(loadLocalTrader(store).balance).toBe(10000);
  });

  it("persists a trade across loads", () => {
    placeLocalTrade(market, "yes", "buy", 40, store); // cost 40*0.25 = ⓥ10
    const reloaded = loadLocalTrader(store);
    expect(reloaded.balance).toBe(9990);
    expect(reloaded.positions[0]).toMatchObject({ event_id: 7, side: "yes", shares: 40 });
    expect(reloaded.trades).toHaveLength(1);
  });

  it("reset returns to a fresh book", () => {
    placeLocalTrade(market, "yes", "buy", 40, store);
    resetLocalTrader(store);
    expect(loadLocalTrader(store).balance).toBe(10000);
  });

  it("tolerates corrupt storage", () => {
    expect(loadLocalTrader(memoryStorage("{not json")).balance).toBe(10000);
  });

  it("surfaces rejections from the engine", () => {
    expect(() => placeLocalTrade(market, "yes", "buy", 10_000_000, store)).toThrow(/insufficient/);
  });
});
