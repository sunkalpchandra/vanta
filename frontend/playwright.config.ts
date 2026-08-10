import { defineConfig, devices } from "@playwright/test";

/** E2E over the static export — the exact artifact GitHub Pages serves.
 * `e2e/serve.sh` mounts out/ under /vanta so basePath-prefixed links resolve. */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  // A python -m http.server backs the run; too many workers starve hydration
  // and the specs read as flaky when the app is just slow to boot.
  workers: 3,
  expect: { timeout: 10_000 },
  forbidOnly: !!process.env.CI,
  retries: 1, // browser cold-start can starve first-load hydration; one retry is standard
  reporter: process.env.CI ? "github" : "list",
  use: {
    // Trailing slash matters: specs use relative paths ("." , "brief/") so
    // new URL(path, baseURL) stays under the /vanta base path.
    baseURL: "http://127.0.0.1:4173/vanta/",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "bash e2e/serve.sh",
    url: "http://127.0.0.1:4173/vanta/",
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
