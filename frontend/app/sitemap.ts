import type { MetadataRoute } from "next";
import { BASE_PATH } from "@/lib/config";
import { getQuestions } from "@/lib/data";

const ORIGIN = "https://sunkalpchandra.github.io";

export const dynamic = "force-static";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = `${ORIGIN}${BASE_PATH}`;
  const questions = await getQuestions();
  return [
    { url: `${base}/` },
    { url: `${base}/brief/` },
    { url: `${base}/leaderboard/` },
    { url: `${base}/agents/` },
    { url: `${base}/archive/` },
    { url: `${base}/methodology/` },
    { url: `${base}/ask/` },
    ...questions.map((q) => ({ url: `${base}/questions/${q.id}/` })),
  ];
}
