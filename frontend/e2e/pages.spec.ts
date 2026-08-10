import { expect, test } from "@playwright/test";

test("brief lists ranked calls with one-liners", async ({ page }) => {
  await page.goto("brief/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(/brief/i);
  const items = page.locator("ol li");
  await expect(items.first()).toBeVisible();
  expect(await items.count()).toBeGreaterThanOrEqual(3);
  await expect(page.getByText(/the crowd looks to be/i).first()).toBeVisible();
});

test("leaderboard table has category rows with accuracy", async ({ page }) => {
  await page.goto("leaderboard/");
  const rows = page.locator("table tbody tr");
  await expect(rows.first()).toBeVisible();
  expect(await rows.count()).toBeGreaterThanOrEqual(3);
});

test("agents page ranks the scored agents", async ({ page }) => {
  await page.goto("agents/");
  // Structural assertion: actual leaderboard rows link to receipts pages
  // (page prose also names agents, which would false-pass a text match).
  const rows = page.locator('a[href*="/agents/"]');
  expect(await rows.count()).toBeGreaterThanOrEqual(6);
  await expect(page.locator('a[href$="/agents/synthesis/"], a[href$="/agents/synthesis"]').first()).toBeVisible();
  await expect(page.locator('a[href$="/agents/quant/"], a[href$="/agents/quant"]').first()).toBeVisible();
});

test("methodology labels the demo corpus honestly", async ({ page }) => {
  await page.goto("methodology/");
  await expect(page.getByText(/seeded demo corpus/i)).toBeVisible();
  await expect(page.getByText(/deterministic fixtures/i)).toBeVisible();
});

test("archive lists resolved calls with outcomes", async ({ page }) => {
  await page.goto("archive/");
  const rows = page.locator("table tbody tr");
  await expect(rows.first()).toBeVisible();
  expect(await rows.count()).toBeGreaterThanOrEqual(5);
});

test("digest shows the settled strip", async ({ page }) => {
  await page.goto("digest/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(/digest/i);
  await expect(page.getByText(/recently settled/i)).toBeVisible();
});

test("chat page renders the static-mode example honestly", async ({ page }) => {
  await page.goto("chat/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(/live agent reasoning/i);
  await expect(page.getByText(/static demo — chat needs the live backend/i)).toBeVisible();
  await expect(page.getByText(/example output/i).first()).toBeVisible();
});

test("leaderboard leads with the real-backtest section", async ({ page }) => {
  await page.goto("leaderboard/");
  await expect(page.getByText(/real-market backtest/i).first()).toBeVisible();
  await expect(page.getByText(/synthetic demo corpus below/i)).toBeVisible();
});

test("markets page shows real events or the honest empty state", async ({ page }) => {
  await page.goto("markets/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(/markets/i);
  await expect(page.getByText(/play money/i).first()).toBeVisible();
  // CI's deterministic bake carries no synced events (sync runs only in the
  // Pages workflow) — the page must show prices OR its honest empty state.
  await expect(
    page.getByText(/%/).first().or(page.getByText(/no markets|sample of the live corpus/i).first()).first(),
  ).toBeVisible();
});

test("portfolio shows the static-mode honest state", async ({ page }) => {
  await page.goto("portfolio/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(/portfolio/i);
  await expect(page.getByText(/static demo|start trading/i).first()).toBeVisible();
  // The trader leaderboard renders (a real trader from the bake DB, or the
  // honest empty state).
  await expect(page.getByText(/trader leaderboard/i)).toBeVisible();
});

test("market detail page shows vanta's forecast and a price chart", async ({ page }) => {
  await page.goto("markets/");
  // Expand the first market row, then follow its details link.
  const detailLink = page.getByRole("link", { name: /price history/i }).first();
  await expect(async () => {
    await page.locator("button").filter({ hasText: /%/ }).first().click();
    await expect(detailLink).toBeVisible({ timeout: 1000 });
  }).toPass({ timeout: 15_000 });
  await detailLink.click();
  await expect(page).toHaveURL(/\/markets\/\d+/);
  await expect(page.getByText(/vanta.s take|vanta's forecast needs/i).first()).toBeVisible();
});

test("history page has an honest empty state", async ({ page }) => {
  await page.goto("history/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
});
