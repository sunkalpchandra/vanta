import { describe, expect, it } from "vitest";
import { buildOgDescription, marketCardHref, type OgMarket } from "./marketCard";

function market(overrides: Partial<OgMarket> = {}): OgMarket {
  return {
    question: "Will BTC close above $100k this year?",
    source: "polymarket",
    yes_price: 0.62,
    volume_usd: 1234,
    outcome: null,
    ...overrides,
  };
}

describe("marketCardHref", () => {
  it("points at the /api/market-cards SVG route (live mode default)", () => {
    const href = marketCardHref(7);
    expect(href).toMatch(/^https?:\/\//);
    expect(href.endsWith("/api/market-cards/7.svg")).toBe(true);
  });

  it("never collides with the /api/markets trading path", () => {
    // A bare id under /api/markets/{id} is markets.router's detail route; the
    // card lives under the distinct /api/market-cards prefix.
    expect(marketCardHref(42)).not.toContain("/api/markets/42");
  });
});

describe("buildOgDescription", () => {
  it("describes an open market with its YES price, source and compact volume", () => {
    const text = buildOgDescription(market({ yes_price: 0.62, volume_usd: 1234 }));
    expect(text).toContain("Will BTC close above $100k this year?");
    expect(text).toContain("62% YES");
    expect(text).toContain("on polymarket");
    expect(text).toContain("$1.2K volume");
    expect(text).toContain("(play money)");
  });

  it("reads a settled market as resolved YES", () => {
    expect(buildOgDescription(market({ outcome: 1 }))).toContain("resolved YES on polymarket");
  });

  it("reads outcome 0 as resolved NO (not swallowed by truthiness)", () => {
    const text = buildOgDescription(market({ outcome: 0 }));
    expect(text).toContain("resolved NO");
    expect(text).not.toContain("resolved YES");
  });

  it("degrades a missing/non-finite price to 'price pending', never NaN%", () => {
    expect(buildOgDescription(market({ yes_price: null }))).toContain("price pending");
    expect(buildOgDescription(market({ yes_price: Number.NaN }))).toContain("price pending");
    expect(buildOgDescription(market({ yes_price: null }))).not.toContain("NaN");
  });

  it("falls back for a blank question and a blank source", () => {
    const text = buildOgDescription(market({ question: "   ", source: "" }));
    expect(text).toContain("Untitled market");
    expect(text).toContain("on market");
  });

  it("always carries the play-money label, resolved or open", () => {
    expect(buildOgDescription(market())).toContain("(play money)");
    expect(buildOgDescription(market({ outcome: 1 }))).toContain("(play money)");
  });
});
