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
  // debate mode: agent reports actually rendered (static copy elsewhere on
  // the page also says "synthesis" — scope to the panel)
  const debate = page.getByTestId("debate-panel");
  await expect(debate.getByText(/synthesis/i).first()).toBeVisible();
  await expect(debate.getByText(/quant/i).first()).toBeVisible();
});

test("keyboard ] pages to another question", async ({ page }) => {
  await page.goto(".");
  await page.locator("a.card").filter({ hasText: "d horizon" }).first().click();
  await expect(page).toHaveURL(/\/questions\/(\d+)/);
  const before = page.url();
  // Re-press until hydration has attached the key listener.
  await expect(async () => {
    await page.keyboard.press("]");
    await expect.poll(() => page.url(), { timeout: 1000 }).not.toBe(before);
  }).toPass({ timeout: 15_000 });
  await expect(page).toHaveURL(/\/questions\/\d+/);
});
