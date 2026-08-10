"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import type { FeedCard } from "@/lib/types";
import { pct } from "@/lib/format";
import { CategoryBadge, EdgeBadge } from "./Badges";
import { Sparkline } from "./Sparkline";

export function FeedCardItem({
  card,
  index,
  sparkline,
}: {
  card: FeedCard;
  index: number;
  sparkline?: number[];
}) {
  const discovery = Math.abs(card.edge) >= 0.05;
  const reduceMotion = useReducedMotion();
  return (
    <motion.div
      initial={reduceMotion ? false : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: Math.min(index * 0.05, 0.4) }}
    >
      <Link
        href={`/questions/${card.question_id}`}
        className="card card-hover block p-5"
        aria-label={card.question}
      >
        <div className="flex items-center gap-2">
          {discovery && (
            <span className="micro-label !text-accent">◆ vanta discovery</span>
          )}
          <CategoryBadge category={card.category} />
          <span className="micro-label ml-auto">{card.horizon_days}d horizon</span>
        </div>
        <h3 className="mt-3 text-[15px] font-semibold leading-snug text-ink">{card.question}</h3>
        <div className="mt-4 grid grid-cols-3 items-end gap-4">
          <div>
            <div className="micro-label">Market</div>
            <div className="num mt-1 text-2xl font-bold text-ink-2">{pct(card.market_probability)}</div>
          </div>
          <div>
            <div className="micro-label">vanta</div>
            <div className="num mt-1 text-2xl font-bold text-accent">{pct(card.vanta_probability)}</div>
          </div>
          <div className="flex flex-col items-end gap-1.5 justify-self-end">
            <EdgeBadge edge={card.edge} />
            {sparkline && <Sparkline points={sparkline} />}
            <div className="micro-label text-right">conf {card.confidence.toFixed(1)}/10</div>
          </div>
        </div>
      </Link>
    </motion.div>
  );
}
