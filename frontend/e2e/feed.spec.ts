import { expect, test } from "@playwright/test";

// Feed cards, as opposed to movers/alerts cards, always carry a horizon chip.
const feedCards = (page: import("@playwright/test").Page) =>
  page.locator("a.card").filter({ hasText: "d horizon" });

test("feed renders cards with market vs vanta numbers", async ({ page }) => {
  await page.goto(".");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(/intelligence feed/i);
  const cards = feedCards(page);
  await expect(cards.first()).toBeVisible();
  expect(await cards.count()).toBeGreaterThanOrEqual(5);
  await expect(cards.first().getByText("Market", { exact: true })).toBeVisible();
  await expect(cards.first().getByText("vanta", { exact: true })).toBeVisible();
});

test("category filter narrows the feed", async ({ page }) => {
  await page.goto(".");
  const cards = feedCards(page);
  const all = await cards.count();
  const techButton = page
    .getByRole("group", { name: "Filter by category" })
    .getByRole("button", { name: "technology" });
  // Retry the click until it takes: a click that lands before hydration is
  // swallowed by inert server HTML.
  await expect(async () => {
    await techButton.click();
    await expect(techButton).toHaveAttribute("aria-pressed", "true", { timeout: 1000 });
  }).toPass({ timeout: 15_000 });
  await expect.poll(async () => cards.count(), { timeout: 5000 }).toBeLessThan(all);
  const remaining = await cards.count();
  expect(await cards.filter({ hasText: "technology" }).count()).toBe(remaining);
});

test("search filters questions by text", async ({ page }) => {
  await page.goto(".");
  const box = page.getByRole("searchbox", { name: "Search questions" });
  // Same hydration race as the filter click — retry the fill until it takes.
  await expect(async () => {
    await box.fill("zzz-no-such-question");
    await expect(page.getByText("No live questions match.")).toBeVisible({ timeout: 1000 });
  }).toPass({ timeout: 15_000 });
});
