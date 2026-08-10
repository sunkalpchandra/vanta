"use client";

export default function Error({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="mx-auto max-w-md py-24 text-center">
      <div className="micro-label">system fault</div>
      <h1 className="mt-3 text-lg font-bold">Something broke while rendering this view</h1>
      <p className="mt-2 text-sm text-ink-2">
        The forecast data may be temporarily unavailable. Retrying usually fixes it.
      </p>
      <button
        onClick={reset}
        className="mt-6 rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90"
      >
        Retry
      </button>
    </div>
  );
}
