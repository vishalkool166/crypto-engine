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
  await expect.poll(() => page.locator("html").evaluate((el) => getComputedStyle(el).getPropertyValue("--background").trim())).toBe("0 0% 100%");
  await expect.poll(() => page.locator("html").evaluate((el) => getComputedStyle(el).getPropertyValue("--accent").trim())).toBe("0 0% 96.1%");
  await page.reload();
  await expect(page.locator("html")).not.toHaveClass(/dark/);
});

test("private admin restores full performance and trade journey views", async ({ page }) => {
  await page.route("**/auth/session", (r) => r.fulfill({ json: { user: { email: "operator@example.com" } } }));
  await page.route("**/ws/admin", () => {});
  await page.route("**/api/v1/admin/**", (route) => {
    const url = route.request().url();
    if (url.includes("/trades/open")) return route.fulfill({ json: [{ id: 42, coin: "ETH", direction: "LONG", entry_price: 2000, current_price: 2020, profit_abs: 4 }] });
    if (url.includes("/trades/history")) return route.fulfill({ json: { trades: [{ trade_id: 7, coin: "BTC", direction: "SHORT", outcome: "win", net_pnl: 12, opened_at: "2026-10-20T10:00:00Z" }] } });
    if (url.includes("/journey")) return route.fulfill({ json: { trade_id: 42, journey: [{ timestamp: "2026-10-20T10:00:00Z", price: 2000, pnl_pct: 0, entry_price: 2000, sl_price: 1950, tp_price: 2100, is_entry: true }, { timestamp: "2026-10-20T11:00:00Z", price: 2020, pnl_pct: 1, entry_price: 2000, sl_price: 1950, tp_price: 2100, is_exit: true }] } });
    if (url.includes("/dashboard/performance")) return route.fulfill({ json: { closed: 2, win_rate: 50, wins: 1, losses: 1, total_pnl: 4, profit_factor: 1.2, max_drawdown: 3, best_trade: 8, best_trade_coin: "ETH", equity_curve: [{ date: "2026-10-19", equity: -4 }, { date: "2026-10-20", equity: 4 }], aplus: { total: 1, wins: 1, win_rate: 100, pnl: 8 }, a: { total: 1, wins: 0, win_rate: 0, pnl: -4 }, b: { total: 0, wins: 0, win_rate: 0, pnl: 0 } } });
    if (url.includes("/trades/performance")) return route.fulfill({ json: [{ coin: "ETH", wins: 1, losses: 0, win_rate: 100, profit_abs: 8, commission: 0.2, funding: -0.1 }] });
    if (url.includes("/dashboard/history")) return route.fulfill({ json: [{ id: 7, coin: "BTC", direction: "SHORT", grade: "A", outcome: "win", pnl: 8, timestamp: "2026-10-20T10:00:00Z" }] });
    return route.fulfill({ json: { tables: [], total_tables: 0, data: [], signals: [], coins: [], gate: {} } });
  });
  await page.goto("http://127.0.0.1:5174");
  await page.getByRole("link", { name: "Performance", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("closed trades say");
  await expect(page.getByText("Cumulative net P&L")).toBeVisible();
  await expect(page.getByText("Results by instrument")).toBeVisible();
  await page.getByRole("link", { name: "Paper trades" }).click();
  await page.getByRole("button", { name: "Trade journey" }).first().click();
  await expect(page.getByRole("heading", { name: "ETH · trade journey" })).toBeVisible();
  await expect(page.getByText("Entry 2,000")).toBeVisible();
});
