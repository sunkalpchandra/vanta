export default function QuestionLoading() {
  return (
    <div aria-busy="true" aria-label="Loading forecast">
      <div className="mb-6 space-y-3">
        <div className="h-5 w-40 animate-pulse rounded bg-surface-2" />
        <div className="h-8 w-3/4 animate-pulse rounded bg-surface-2" />
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="card h-24 animate-pulse" />
        ))}
      </div>
      <div className="card mt-4 h-64 animate-pulse" />
    </div>
  );
}
