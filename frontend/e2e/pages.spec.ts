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

test("agents page ranks the seven agents", async ({ page }) => {
  await page.goto("agents/");
  for (const agent of ["quant", "skeptic", "synthesis"]) {
    await expect(page.getByText(new RegExp(agent, "i")).first()).toBeVisible();
  }
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
