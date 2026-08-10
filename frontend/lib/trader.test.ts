import { describe, expect, it } from "vitest";
import {
  authHeaders,
  clearTraderKey,
  compactUsd,
  daysUntilClose,
  ensureTrader,
  fmtCredits,
  fmtSignedCredits,
  getTraderKey,
  setTraderKey,
  sidePrice,
  tradeCost,
} from "./trader";

function memoryStorage(initial: string | null = null) {
  let value = initial;
  return {
    getItem: () => value,
    setItem: (_: string, v: string) => {
      value = v;
    },
    removeItem: () => {
      value = null;
    },
  };
}

/** A fetch mock that records calls and replies with a canned response. */
function mockFetch(status: number, body: unknown) {
  const calls: { url: string; init?: RequestInit }[] = [];
  const impl = (async (url: unknown, init?: RequestInit) => {
    calls.push({ url: String(url), init });
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
    };
  }) as unknown as typeof fetch;
  return { impl, calls };
}

const neverFetch = (() => {
  throw new Error("network call not expected");
}) as unknown as typeof fetch;

describe("trader key store", () => {
  it("round-trips set → get → clear", () => {
    const storage = memoryStorage();
    expect(getTraderKey(storage)).toBeNull();
    setTraderKey("vk_abc123", storage);
    expect(getTraderKey(storage)).toBe("vk_abc123");
    clearTraderKey(storage);
    expect(getTraderKey(storage)).toBeNull();
  });

  it("treats empty / whitespace values as no key", () => {
    expect(getTraderKey(memoryStorage(""))).toBeNull();
    expect(getTraderKey(memoryStorage("   "))).toBeNull();
  });
});

describe("authHeaders", () => {
  it("is empty without an identity", () => {
    expect(authHeaders(memoryStorage())).toEqual({});
  });

  it("carries the key as X-API-Key", () => {
    const storage = memoryStorage();
    setTraderKey("vk_secret", storage);
    expect(authHeaders(storage)).toEqual({ "X-API-Key": "vk_secret" });
  });
});

describe("ensureTrader", () => {
  it("returns the stored key without touching the network", async () => {
    const storage = memoryStorage();
    setTraderKey("vk_kept", storage);
    const result = await ensureTrader("ignored@example.com", { storage, fetchImpl: neverFetch });
    expect(result).toEqual({ key: "vk_kept", created: false });
  });

  it("registers via POST /api/users and stores the returned key", async () => {
    const storage = memoryStorage();
    const { impl, calls } = mockFetch(201, {
      id: 1,
      email: "t@example.com",
      api_key: "vk_new",
      created_at: "2026-08-10T00:00:00Z",
    });
    const result = await ensureTrader("  t@example.com  ", { storage, fetchImpl: impl });
    expect(result).toEqual({ key: "vk_new", created: true });
    expect(getTraderKey(storage)).toBe("vk_new");
    expect(calls).toHaveLength(1);
    expect(calls[0].url.endsWith("/api/users")).toBe(true);
    expect(calls[0].init?.method).toBe("POST");
    expect(JSON.parse(String(calls[0].init?.body))).toEqual({ email: "t@example.com" });
  });

  it("rejects without an email when no key is stored", async () => {
    await expect(
      ensureTrader(undefined, { storage: memoryStorage(), fetchImpl: neverFetch }),
    ).rejects.toThrow(/email required/);
  });

  it("surfaces the backend 409 detail and stores nothing", async () => {
    const storage = memoryStorage();
    const { impl } = mockFetch(409, { detail: "email already registered" });
    await expect(ensureTrader("dup@example.com", { storage, fetchImpl: impl })).rejects.toThrow(
      "email already registered",
    );
    expect(getTraderKey(storage)).toBeNull();
  });
});

describe("money helpers", () => {
  it("prices each side off the venue YES price", () => {
    expect(sidePrice(0.63, "yes")).toBe(0.63);
    expect(sidePrice(0.63, "no")).toBeCloseTo(0.37, 10);
    expect(sidePrice(null, "yes")).toBeNull();
    expect(sidePrice(0, "yes")).toBeNull();
    expect(sidePrice(1, "no")).toBeNull();
  });

  it("previews cost at 2dp and rejects invalid inputs", () => {
    expect(tradeCost(10, 0.63)).toBe(6.3);
    expect(tradeCost(7, 0.33)).toBe(2.31);
    expect(tradeCost(0, 0.5)).toBeNull();
    expect(tradeCost(-3, 0.5)).toBeNull();
    expect(tradeCost(10, null)).toBeNull();
    expect(tradeCost(10, 1)).toBeNull();
  });

  it("formats ⓥ credits", () => {
    expect(fmtCredits(10000)).toBe("ⓥ10,000.00");
    expect(fmtCredits(6.3)).toBe("ⓥ6.30");
    expect(fmtSignedCredits(12.5)).toBe("+ⓥ12.50");
    expect(fmtSignedCredits(-12.5)).toBe("-ⓥ12.50");
  });

  it("compacts venue volume", () => {
    expect(compactUsd(2_500_000_000)).toBe("$2.5b");
    expect(compactUsd(1_234_567)).toBe("$1.2m");
    expect(compactUsd(530_000)).toBe("$530k");
    expect(compactUsd(980)).toBe("$980");
    expect(compactUsd(0)).toBe("$0");
  });
});

describe("daysUntilClose", () => {
  const now = new Date("2026-08-10T00:00:00Z");

  it("counts whole days, treating offset-less stamps as UTC", () => {
    expect(daysUntilClose("2026-08-13T12:00:00", now)).toBe(4);
    expect(daysUntilClose("2026-08-10T06:00:00Z", now)).toBe(1);
    expect(daysUntilClose("2026-08-10T00:00:00Z", now)).toBe(0);
  });

  it("returns null for missing, garbage, or past times", () => {
    expect(daysUntilClose(null, now)).toBeNull();
    expect(daysUntilClose("not-a-date", now)).toBeNull();
    expect(daysUntilClose("2026-08-01T00:00:00Z", now)).toBeNull();
  });
});
