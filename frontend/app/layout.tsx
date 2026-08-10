import type { Metadata } from "next";
import Link from "next/link";
import { BASE_PATH } from "@/lib/config";
import "./globals.css";

export const viewport = {
  themeColor: "#08090d",
};

export const metadata: Metadata = {
  // metadata.manifest is not basePath-prefixed automatically — do it ourselves.
  manifest: `${BASE_PATH}/site.webmanifest`,
  title: "vanta — forecasting intelligence",
  description:
    "Autonomous multi-agent intelligence engine for probabilistic forecasting. What the world believes will happen — and what will actually happen.",
  metadataBase: new URL("https://sunkalpchandra.github.io"),
  openGraph: {
    title: "vanta — forecasting intelligence",
    description:
      "Seven agents deliberate on every question about the future. Market probability vs vanta's — with the full debate.",
    url: "https://sunkalpchandra.github.io/vanta/",
    siteName: "vanta",
    type: "website",
  },
};

const NAV = [
  { href: "/", label: "Feed" },
  { href: "/brief", label: "Brief" },
  { href: "/leaderboard", label: "Accuracy" },
  { href: "/agents", label: "Agents" },
  { href: "/archive", label: "Archive" },
  { href: "/methodology", label: "Method" },
  { href: "/ask", label: "Ask" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-accent focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-white"
        >
          Skip to content
        </a>
        <header className="sticky top-0 z-40 border-b border-line bg-bg/85 backdrop-blur">
          <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-3 px-5">
            <Link href="/" className="flex shrink-0 items-baseline gap-2">
              <span className="num text-[15px] font-bold tracking-[0.35em] text-ink">VANTA</span>
              <span className="micro-label hidden md:inline">intelligence engine</span>
            </Link>
            {/* Scrolls horizontally on phone widths instead of overflowing the page */}
            <nav className="flex min-w-0 items-center gap-1 overflow-x-auto whitespace-nowrap [scrollbar-width:none]">
              {NAV.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="shrink-0 rounded-md px-3 py-1.5 text-[13px] text-ink-2 transition-colors hover:bg-surface-2 hover:text-ink"
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
        </header>
        <main id="main" className="mx-auto max-w-6xl px-5 pb-24 pt-8">{children}</main>
        <footer className="border-t border-line py-6">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-5">
            <p className="text-xs text-muted">
              vanta is a forecasting intelligence system, not investment advice. Probabilities are
              model outputs with irreducible uncertainty.
            </p>
            <div className="flex items-center gap-4">
              <Link href="/methodology" className="text-xs text-muted transition-colors hover:text-ink-2">
                Methodology
              </Link>
              <a
                href="https://github.com/sunkalpchandra/vanta/blob/main/docs/API.md"
                className="text-xs text-muted transition-colors hover:text-ink-2"
              >
                API docs ↗
              </a>
              <a
                href="https://github.com/sunkalpchandra/vanta"
                className="text-xs text-muted transition-colors hover:text-ink-2"
              >
                GitHub ↗
              </a>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
