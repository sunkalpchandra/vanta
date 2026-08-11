import { describe, expect, it } from "vitest";
import { deleteComment, getComments, MAX_BODY, postComment, validateBody } from "./comments";

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

describe("validateBody", () => {
  it("trims and returns non-empty bodies", () => {
    expect(validateBody("hello")).toBe("hello");
    expect(validateBody("  spaced out  ")).toBe("spaced out");
    expect(validateBody("x")).toBe("x"); // 1 char is allowed
    expect(validateBody("x".repeat(MAX_BODY))).toBe("x".repeat(MAX_BODY)); // exactly the max
  });

  it("rejects empty, whitespace-only, and over-long bodies as null", () => {
    expect(validateBody("")).toBeNull();
    expect(validateBody("   ")).toBeNull();
    expect(validateBody("\n\t ")).toBeNull();
    expect(validateBody("x".repeat(MAX_BODY + 1))).toBeNull();
  });

  it("measures length after trimming", () => {
    // Padding that pushes raw length past the max still passes once trimmed.
    const padded = `  ${"x".repeat(MAX_BODY)}  `;
    expect(validateBody(padded)).toBe("x".repeat(MAX_BODY));
  });
});

describe("getComments", () => {
  it("reads newest-first without an identity and sends the limit", async () => {
    const payload = [
      { id: 2, handle: "bob", body: "second", created_at: "2026-08-10T00:00:01" },
      { id: 1, handle: "alice", body: "first", created_at: "2026-08-10T00:00:00" },
    ];
    const { impl, calls } = mockFetch(200, payload);
    expect(await getComments(7, 25, { fetchImpl: impl })).toEqual(payload);
    expect(calls[0].url.endsWith("/api/markets/7/comments?limit=25")).toBe(true);
    expect(calls[0].init).toBeUndefined(); // plain GET, no auth headers
  });

  it("throws a readable error on a non-ok response", async () => {
    const { impl } = mockFetch(404, { detail: "market not found" });
    await expect(getComments(9, 50, { fetchImpl: impl })).rejects.toThrow(/market not found/);
  });
});

describe("postComment", () => {
  it("sends the key and the trimmed body, returning the created comment", async () => {
    const created = { id: 5, handle: "alice", body: "hi", created_at: "2026-08-10T00:00:00Z" };
    const { impl, calls } = mockFetch(201, created);
    const out = await postComment(3, "  hi  ", { storage: keyedStorage("vk_a"), fetchImpl: impl });
    expect(out).toEqual(created);
    expect(calls[0].url.endsWith("/api/markets/3/comments")).toBe(true);
    expect(calls[0].init?.method).toBe("POST");
    expect((calls[0].init?.headers as Record<string, string>)["X-API-Key"]).toBe("vk_a");
    expect(JSON.parse(String(calls[0].init?.body))).toEqual({ body: "hi" }); // trimmed
  });

  it("rejects locally without an identity or on an invalid body — no network call", async () => {
    await expect(
      postComment(3, "hi", { storage: keyedStorage(null), fetchImpl: neverFetch }),
    ).rejects.toThrow(/start trading/);
    await expect(
      postComment(3, "   ", { storage: keyedStorage("vk_a"), fetchImpl: neverFetch }),
    ).rejects.toThrow(/1–1000/);
  });

  it("surfaces a backend error detail", async () => {
    const { impl } = mockFetch(429, { detail: "rate limit exceeded; slow down" });
    await expect(
      postComment(3, "hi", { storage: keyedStorage("vk_a"), fetchImpl: impl }),
    ).rejects.toThrow(/rate limit/);
  });
});

describe("deleteComment", () => {
  it("DELETEs with the key and resolves on 204", async () => {
    const { impl, calls } = mockFetch(204);
    expect(await deleteComment(3, 5, { storage: keyedStorage("vk_a"), fetchImpl: impl })).toBe(true);
    expect(calls[0].url.endsWith("/api/markets/3/comments/5")).toBe(true);
    expect(calls[0].init?.method).toBe("DELETE");
    expect((calls[0].init?.headers as Record<string, string>)["X-API-Key"]).toBe("vk_a");
  });

  it("treats a 404 as already-gone", async () => {
    expect(await deleteComment(3, 5, { storage: keyedStorage(), fetchImpl: mockFetch(404).impl })).toBe(
      true,
    );
  });

  it("throws on a 403 and without an identity", async () => {
    const { impl } = mockFetch(403, { detail: "only the author can delete this comment" });
    await expect(
      deleteComment(3, 5, { storage: keyedStorage("vk_a"), fetchImpl: impl }),
    ).rejects.toThrow(/only the author/);
    await expect(
      deleteComment(3, 5, { storage: keyedStorage(null), fetchImpl: neverFetch }),
    ).rejects.toThrow(/start trading/);
  });
});
