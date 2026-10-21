import { test, expect } from "@playwright/test";
// Browser contract fixtures are confined to tests; runtime never installs them.
const snapshot = {
  mode: "paper",
  strategy_status: "not_evaluated",
  status: "awaiting_data",
  last_scan_at: null,
  data_age_seconds: null,
  universe: ["ETH"],
  signal_count: 0,
  recorded_outcomes: {},
  signals: [],
};
async function publicApi(page: any) {
  await page.route("**/api/v1/public/**", (route: any) =>
    route.fulfill({
      json: route.request().url().includes("/signals?")
        ? { items: [], total: 0, offset: 0, limit: 20 }
        : snapshot,
    }),
  );
  await page.routeWebSocket("**/ws/public", () => {});
}
test("public ledger has an honest empty state and usable navigation", async ({
  page,
}) => {
  await publicApi(page);
  await page.goto("http://127.0.0.1:5173");
  await expect(page.getByText("No records yet")).toBeVisible();
  await page
    .locator("nav")
    .getByRole("link", { name: "Signals", exact: true })
    .click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Inspect the setup",
  );
  await expect(
    page.getByRole("button", { name: "Next", exact: true }),
  ).toBeDisabled();
});
test("public fetch failure gives retry rather than fabricated metrics", async ({
  page,
}) => {
  await page.route("**/api/**", (r) =>
    r.fulfill({ status: 503, json: { detail: "Test service unavailable" } }),
  );
  await page.routeWebSocket("**/ws/public", () => {});
  await page.goto("http://127.0.0.1:5173");
  await expect(page.getByRole("alert")).toContainText(
    "Test service unavailable",
  );
  await expect(
    page.getByRole("button", { name: "Retry", exact: true }),
  ).toBeVisible();
});
test("operator login offers Google without customer signup", async ({
  page,
}) => {
  await page.route("**/auth/session", (r) =>
    r.fulfill({
      status: 401,
      json: { detail: "Operator authentication required" },
    }),
  );
  await page.goto("http://127.0.0.1:5174");
  await expect(
    page.getByRole("link", { name: /Continue with Google/ }),
  ).toHaveAttribute("href", "/auth/google");
  await expect(page.locator("input[type=password]")).toHaveCount(0);
});
test("session store failure does not turn into an authenticated console", async ({
  page,
}) => {
  await page.route("**/auth/session", (r) =>
    r.fulfill({ status: 503, json: { detail: "Session service unavailable" } }),
  );
  await page.goto("http://127.0.0.1:5174");
  await expect(page.getByRole("alert")).toContainText(
    "Session service unavailable",
  );
  await expect(page.getByText("Run scan", { exact: true })).toHaveCount(0);
});
test("mobile public menu navigates without page overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await publicApi(page);
  await page.goto("http://127.0.0.1:5173");
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page
    .locator("nav")
    .getByRole("link", { name: "Methodology", exact: true })
    .click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Rules you can inspect",
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("theme control preserves the selected shadcn color scheme", async ({ page }) => {
  await publicApi(page);
  await page.goto("http://127.0.0.1:5173");
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.getByRole("button", { name: "Use light theme" }).click();
  await expect(page.locator("html")).not.toHaveClass(/dark/);
  await page.reload();
  await expect(page.locator("html")).not.toHaveClass(/dark/);
});
