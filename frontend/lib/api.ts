import { BASE_PATH, IS_STATIC } from "./config";

// Browser-facing base URL: client-side fetches (AskForm) and links the browser
// follows (share cards).
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Where the share-card SVG for a question lives in the current mode. */
export const shareCardHref = (questionId: number) =>
  IS_STATIC ? `${BASE_PATH}/cards/${questionId}.svg` : `${API_URL}/api/cards/${questionId}.svg`;
