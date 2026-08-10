import { describe, expect, it } from "vitest";
import { getWatched, getWatchedIds, isMoved, toggleWatch } from "./watch";

function keyedStorage(key: string | null = "vk_test") {
  return {
    getItem: () => key,
    setItem: () => {},
    removeItem: () => {},
  };
}

/** A fetch mock that records calls and replies with a canned response. */
function mockFetch(status: number, body: unknown = null) {
  const calls: { url: string; init?: RequestInit }[] = [];
  const impl = (async (url: unknown, init?: RequestInit) => {
    calls.push({ url: String(url), init });
    return { ok: status >= 200 && status < 300, status, json: async () => body };
  }) as unknown as typeof fetch;
  return { impl, calls };
}

const neverFetch = (() => {
  throw new Error("network call not expected");
}) as unknown as typeof fetch;

describe("isMoved", () => {
  it("flags a move at or beyond the 5-point threshold", () => {
    expect(isMoved(0.05)).toBe(true);
    expect(isMoved(0.15)).toBe(true);
    expect(isMoved(-0.08)).toBe(true); // sign-agnostic
    expect(isMoved(-1)).toBe(true);
  });

  it("treats sub-threshold, zero, null, and non-finite deltas as no move", () => {
    expect(isMoved(0.049)).toBe(false);
    expect(isMoved(0)).toBe(false);
    expect(isMoved(null)).toBe(false);
    expect(isMoved(undefined)).toBe(false);
    expect(isMoved(Number.NaN)).toBe(false);
    expect(isMoved(Number.POSITIVE_INFINITY)).toBe(false);
  });
});

describe("getWatched / getWatchedIds", () => {
  it("returns [] without a trader identity and never hits the network", async () => {
    expect(await getWatched({ storage: keyedStorage(null), fetchImpl: neverFetch })).toEqual([]);
    expect(await getWatchedIds({ storage: keyedStorage(null), fetchImpl: neverFetch })).toEqual([]);
  });

  it("sends the trader key and maps ids out of the payload", async () => {
    const payload = [
      { event_id: 7, question: "Q7", yes_price: 0.5, delta_24h: 0.1, moved: true },
      { event_id: 9, question: "Q9", yes_price: null, delta_24h: null, moved: false },
    ];
    const { impl, calls } = mockFetch(200, payload);
    const deps = { storage: keyedStorage("vk_abc"), fetchImpl: impl };
    expect(await getWatched(deps)).toEqual(payload);
    expect(await getWatchedIds(deps)).toEqual([7, 9]);
    expect(calls[0].url.endsWith("/api/watch")).toBe(true);
    expect((calls[0].init?.headers as Record<string, string>)["X-API-Key"]).toBe("vk_abc");
  });

  it("degrades to [] on a non-ok response or a thrown fetch", async () => {
    expect(await getWatched({ storage: keyedStorage(), fetchImpl: mockFetch(500).impl })).toEqual([]);
    expect(await getWatched({ storage: keyedStorage(), fetchImpl: neverFetch })).toEqual([]);
  });
});

describe("toggleWatch", () => {
  it("POSTs to add and DELETEs to remove, carrying the key", async () => {
    const add = mockFetch(201);
    expect(await toggleWatch(4, true, { storage: keyedStorage("vk_z"), fetchImpl: add.impl })).toBe(true);
    expect(add.calls[0].url.endsWith("/api/watch/4")).toBe(true);
    expect(add.calls[0].init?.method).toBe("POST");
    expect((add.calls[0].init?.headers as Record<string, string>)["X-API-Key"]).toBe("vk_z");

    const del = mockFetch(204);
    expect(await toggleWatch(4, false, { storage: keyedStorage(), fetchImpl: del.impl })).toBe(true);
    expect(del.calls[0].init?.method).toBe("DELETE");
  });

  it("counts a 404 on remove as already-unwatched", async () => {
    expect(await toggleWatch(4, false, { storage: keyedStorage(), fetchImpl: mockFetch(404).impl })).toBe(true);
  });

  it("reports failure on a rejected add and throws without an identity", async () => {
    expect(await toggleWatch(4, true, { storage: keyedStorage(), fetchImpl: mockFetch(409).impl })).toBe(false);
    await expect(
      toggleWatch(4, true, { storage: keyedStorage(null), fetchImpl: neverFetch }),
    ).rejects.toThrow(/start trading/);
  });
});
