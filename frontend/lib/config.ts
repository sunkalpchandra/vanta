// Static demo mode: the app is exported as plain HTML/JSON (GitHub Pages) and
// reads a baked snapshot instead of a live backend.
export const IS_STATIC = process.env.NEXT_PUBLIC_STATIC_MODE === "1";

// Set when the site is served from a subpath (GitHub Pages: /vanta).
export const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
