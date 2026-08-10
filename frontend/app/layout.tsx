import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "vanta — forecasting intelligence",
  description:
    "Autonomous multi-agent intelligence engine for probabilistic forecasting. What the world believes will happen — and what will actually happen.",
};

const NAV = [
  { href: "/", label: "Feed" },
  { href: "/brief", label: "Morning Brief" },
  { href: "/leaderboard", label: "Accuracy" },
  { href: "/ask", label: "Ask vanta" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <header className="sticky top-0 z-40 border-b border-line bg-bg/85 backdrop-blur">
          <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-5">
            <Link href="/" className="flex items-baseline gap-2">
              <span className="num text-[15px] font-bold tracking-[0.35em] text-ink">VANTA</span>
              <span className="micro-label hidden sm:inline">intelligence engine</span>
            </Link>
            <nav className="flex items-center gap-1">
              {NAV.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="rounded-md px-3 py-1.5 text-[13px] text-ink-2 transition-colors hover:bg-surface-2 hover:text-ink"
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-5 pb-24 pt-8">{children}</main>
        <footer className="border-t border-line py-6">
          <p className="mx-auto max-w-6xl px-5 text-xs text-muted">
            vanta is a forecasting intelligence system, not investment advice. Probabilities are model
            outputs with irreducible uncertainty.
          </p>
        </footer>
      </body>
    </html>
  );
}
