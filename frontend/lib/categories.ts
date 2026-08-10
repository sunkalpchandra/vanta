// The one category list — the category pages, sitemap, and ask form all key
// off this. Mirrors the backend's Category literal in app/schemas.py.
export const CATEGORIES = [
  "technology",
  "finance",
  "politics",
  "science",
  "sports",
  "crypto",
] as const;

export type Category = (typeof CATEGORIES)[number];
