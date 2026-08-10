import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-md py-24 text-center">
      <div className="num text-5xl font-bold text-muted">404</div>
      <h1 className="mt-4 text-lg font-bold">No forecast at this address</h1>
      <p className="mt-2 text-sm text-ink-2">
        The question you&apos;re looking for doesn&apos;t exist — or hasn&apos;t been asked yet.
      </p>
      <Link
        href="/"
        className="mt-6 inline-block rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90"
      >
        Back to the feed
      </Link>
    </div>
  );
}
