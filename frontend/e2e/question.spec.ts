import { expect, test } from "@playwright/test";

test("feed card opens a question with forecast, chart, and debate", async ({ page }) => {
  await page.goto(".");
  await page.locator("a.card").filter({ hasText: "d horizon" }).first().click();
  await expect(page).toHaveURL(/\/questions\/\d+/);
  await expect(page.getByText("Market probability")).toBeVisible();
  await expect(page.getByText("vanta prediction")).toBeVisible();
  await expect(page.getByText("vanta edge")).toBeVisible();
  // the probability chart mounts as a recharts svg
  await expect(page.locator("svg.recharts-surface").first()).toBeVisible();
  // debate mode: at least the synthesis agent reports in
  await expect(page.getByText(/synthesis/i).first()).toBeVisible();
});

test("keyboard ] pages to another question", async ({ page }) => {
  await page.goto(".");
  await page.locator("a.card").filter({ hasText: "d horizon" }).first().click();
  await expect(page).toHaveURL(/\/questions\/(\d+)/);
  const before = page.url();
  await page.keyboard.press("]");
  await expect.poll(() => page.url(), { timeout: 5000 }).not.toBe(before);
  await expect(page).toHaveURL(/\/questions\/\d+/);
});
