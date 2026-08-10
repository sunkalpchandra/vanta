export function ConfidenceMeter({ value }: { value: number }) {
  // 10 segments, filled count = confidence 0-10.
  const filled = Math.round(value);
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="micro-label">Confidence</span>
        <span className="num text-sm font-bold text-ink">{value.toFixed(1)}/10</span>
      </div>
      <div className="mt-2 flex gap-1" role="img" aria-label={`Confidence ${value} of 10`}>
        {Array.from({ length: 10 }, (_, i) => (
          <div
            key={i}
            className={`h-1.5 flex-1 rounded-sm ${i < filled ? "bg-accent" : "bg-surface-2"}`}
          />
        ))}
      </div>
    </div>
  );
}
