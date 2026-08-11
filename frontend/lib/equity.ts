// Pure builder for the portfolio equity-over-time chart. The backend's
// GET /api/portfolio/equity endpoint returns *cash flow from trades* — the
// caller's starting grant walked forward by each trade's signed cost (a buy
// debits, a sell credits). It is deliberately NOT mark-to-market equity and
// excludes settlement payouts (see the router docstring). This module only
// shapes those points into sorted chart rows — it never invents a number.
//
// play money · paper trading · real market prices — never real money.

// One raw point from the endpoint: an ISO UTC stamp and the ⓥ cash after that
// point's trade (or the opening grant).
export interface EquityPoint {
  timestamp: string;
  cash: number;
}

// One chart row: `t` is the ISO timestamp, `cash` the ⓥ amount (2dp).
export interface EquityRow {
  t: string;
  cash: number;
}

const round2 = (n: number) => Math.round(n * 100) / 100 + 0;

/**
 * Shape raw equity points into chart rows: {t, cash} sorted oldest→newest with
 * cash rounded to the cent. Points missing a usable string timestamp or a
 * finite numeric cash are dropped (cash may legitimately be 0 or negative — a
 * real level, never a falsy drop). Duplicate timestamps are KEPT in input
 * order (JS sort is stable), so two same-instant fills stay as distinct steps.
 * Returns [] for null / undefined / empty input.
 */
export function buildEquitySeries(points: EquityPoint[] | null | undefined): EquityRow[] {
  const rows: EquityRow[] = [];
  for (const point of points ?? []) {
    const t = typeof point?.timestamp === "string" && point.timestamp ? point.timestamp : null;
    const cash = point?.cash;
    if (t === null || typeof cash !== "number" || !Number.isFinite(cash)) continue;
    rows.push({ t, cash: round2(cash) });
  }
  // Sort by real instant, not string order: ISO timestamps with differing
  // fractional-second precision (…:05Z vs …:05.5Z) mis-order under localeCompare.
  // A stable sort keeps same-instant fills in input order.
  return rows
    .map((r, i) => ({ r, i, ms: Date.parse(r.t) }))
    .sort((a, b) => (a.ms - b.ms) || (a.i - b.i))
    .map((x) => x.r);
}
