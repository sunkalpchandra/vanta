// Client-side starring — a reader's personal watchlist, localStorage-backed
// so it works identically on the live app and the static demo.

const KEY = "vanta:starred";

function safeParse(raw: string | null): number[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((x) => Number.isInteger(x)) : [];
  } catch {
    return [];
  }
}

export function getStarred(storage: Pick<Storage, "getItem" | "setItem"> = localStorage): number[] {
  return safeParse(storage.getItem(KEY));
}

export function toggleStar(
  id: number,
  storage: Pick<Storage, "getItem" | "setItem"> = localStorage,
): number[] {
  const current = getStarred(storage);
  const next = current.includes(id) ? current.filter((x) => x !== id) : [...current, id];
  storage.setItem(KEY, JSON.stringify(next));
  return next;
}
