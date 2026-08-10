import type { NextConfig } from "next";

// Static demo build (GitHub Pages): exports plain HTML that reads the baked
// snapshot in public/data. Live builds keep server rendering.
const isStatic = process.env.NEXT_PUBLIC_STATIC_MODE === "1";

const nextConfig: NextConfig = {
  output: isStatic ? "export" : undefined,
  basePath: process.env.NEXT_PUBLIC_BASE_PATH || undefined,
  trailingSlash: isStatic ? true : undefined,
  images: { unoptimized: true },
};

export default nextConfig;
