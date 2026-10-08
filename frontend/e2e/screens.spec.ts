import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const password = () =>
  process.env.E2E_PASSWORD ??
  fs
    .readFileSync(path.resolve(__dirname, "../../.env"), "utf8")
    .match(/^DEMO_PASSWORD=(.+)$/m)?.[1]
    .trim() ??
  "";

async function login(page: Page, username: string) {
  await page.addInitScript(() => localStorage.setItem("kulya.locale", "en"));
  await page.goto("/login/");
  await page.getByLabel("Username", { exact: true }).fill(username);
  await page.getByLabel("Password", { exact: true }).fill(password());
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
}

async function headers(page: Page) {
  const access = await page.evaluate(
    () => JSON.parse(sessionStorage.getItem("kulya.session")!).access,
  );
  return { Authorization: `Bearer ${access}` };
}

test("login rejects empty and invalid credentials, then recovers", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("kulya.locale", "en"));
  await page.goto("/login/");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Username is required.")).toBeVisible();
  await expect(page.getByText("Password is required.")).toBeVisible();
  await page.getByLabel("Username", { exact: true }).fill("LJLK");
  await page.getByLabel("Password", { exact: true }).fill("incorrect");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText("No active account");
  await expect(page).toHaveURL(/\/login\/$/);
  await page.getByLabel("Username", { exact: true }).fill("patient1");
  await page.getByLabel("Password", { exact: true }).fill(password());
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/patient\/$/);
});

for (const role of ["patient1", "doctor1", "nurse1", "dietitian1", "family1", "family2"]) {
  test(`${role}: every permitted screen loads without runtime errors`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await login(page, role);
    const auth = await headers(page);
    let routes: string[];
    if (role.startsWith("patient") || role.startsWith("family")) {
      routes = [
        "/",
        "/patient/",
        ...["", "add/", "history/", "suggestions/", "labs/", "reports/"].map(
          (s) => `/patient/nutrition/${s}`,
        ),
      ];
    } else {
      const response = await page.request.get(
        role === "dietitian1" ? "/api/nutrition/overview/" : "/api/patients/",
        { headers: auth },
      );
      expect(response.ok()).toBeTruthy();
      const data = await response.json();
      const patient = role === "dietitian1" ? data[0].patient : data.results[0].id;
      routes = [
        `/${role.replace(/1$/, "")}/`,
        ...["", "lab-review/", "reports/"].map((s) => `/doctor/patients/${patient}/nutrition/${s}`),
      ];
      if (role === "doctor1") routes.push(`/doctor/patients/${patient}/`);
      if (role !== "dietitian1") {
        const sessions = await page.request.get(`/api/sessions/?patient=${patient}`, {
          headers: auth,
        });
        const session = (await sessions.json()).results[0].id;
        routes.push(`/${role === "doctor1" ? "doctor" : "nurse"}/sessions/${session}/`);
      }
    }
    for (const route of routes) {
      await test.step(route, async () => {
        await page.goto(route);
        await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
        await expect(page.getByText("Loading…", { exact: true })).toHaveCount(0);
        await expect(page.locator("main").getByRole("alert")).toHaveCount(0);
        await expect(page.getByText("Application error", { exact: false })).toHaveCount(0);
      });
    }
    await page.reload();
    await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
    expect(errors).toEqual([]);
    await page.getByRole("button", { name: "Sign out" }).click();
    await page.goto(routes.at(-1)!);
    await expect(page).toHaveURL(/\/login\/$/);
  });
}

test("patient blank measurement is blocked, boundary errors do not save, valid measurement saves", async ({
  page,
}) => {
  await login(page, "patient1");
  const form = page
    .getByRole("button", { name: "Submit measurement" })
    .locator("xpath=ancestor::form");
  await form.getByRole("button").click();
  await expect(form.getByRole("alert")).toContainText("Enter a number");
  await form.getByLabel("Value", { exact: true }).fill("9999");
  await form.getByRole("button").click();
  await expect(form.getByRole("alert")).toContainText("plausible range");
  await form.getByLabel("Value", { exact: true }).fill("64.2");
  const saved = page.waitForResponse(
    (r) => r.url().includes("/api/vitals/") && r.request().method() === "POST",
  );
  await form.getByRole("button").click();
  expect((await saved).status()).toBe(201);
  await expect(form.getByRole("alert")).toHaveCount(0);
});

test("staff forms reject invalid weights, blank readings and blank notes", async ({ page }) => {
  await login(page, "nurse1");
  const auth = await headers(page);
  const patients = await page.request.get("/api/patients/", { headers: auth });
  const patient = (await patients.json()).results[0].id;
  const created = await page.request.post("/api/sessions/", {
    headers: auth,
    data: {
      patient,
      scheduled_start: new Date(Date.now() + 86400000 * 30 + Math.random() * 1000000).toISOString(),
    },
  });
  expect(created.status()).toBe(201);
  const id = (await created.json()).id;
  await page.goto(`/nurse/sessions/${id}/`);
  await page.getByLabel("Pre-treatment weight (kg)").fill("19.99");
  await page.getByRole("button", { name: "Start session" }).click();
  await expect(page.locator("main").getByRole("alert")).toBeVisible();
  await page.getByLabel("Pre-treatment weight (kg)").fill("64");
  await page.getByRole("button", { name: "Start session" }).click();
  await expect(page.getByText("In progress", { exact: true })).toBeVisible();
  for (const [tab, button] of [
    ["Vital sign", "Record vital sign"],
    ["Machine reading", "Record machine reading"],
    ["Note", "Add note"],
    ["Nursing action", "Record nursing action"],
    ["Event / incident", "Record event"],
  ]) {
    await page.getByRole("tab", { name: tab, exact: true }).click();
    await page.getByRole("button", { name: button, exact: true }).click();
    await expect(page.getByRole("tabpanel").getByRole("alert").first()).toBeVisible();
  }
  await page.getByLabel("Post-treatment weight (kg)").fill("301");
  await page.getByRole("button", { name: "Complete session" }).click();
  await expect(page.getByText("In progress", { exact: true })).toBeVisible();
  await page.getByLabel("Post-treatment weight (kg)").fill("62");
  await page.getByLabel("Ultrafiltration volume (mL)").fill("2000");
  await page.getByRole("button", { name: "Complete session" }).click();
  await expect(page.getByText("Completed", { exact: true })).toBeVisible();
});

test("doctor prescription boundaries and nutrition plan limits reject invalid input", async ({
  page,
}) => {
  await login(page, "doctor1");
  const patients = await page.request.get("/api/patients/", { headers: await headers(page) });
  const id = (await patients.json()).results[0].id;
  await page.goto(`/doctor/patients/${id}/`);
  for (const duration of ["", "29", "601", "30.5", "abc"]) {
    await page.getByLabel("Duration (min)").fill(duration);
    await page.getByRole("button", { name: "Create new order version" }).click();
    await expect(page.locator("main").getByRole("alert").first()).toBeVisible();
  }
  await page.goto(`/doctor/patients/${id}/nutrition/`);
  for (const limit of ["0", "100001", "abc"]) {
    await page.getByLabel("Potassium limit per meal (mg)").fill(limit);
    await page.getByRole("button", { name: "Approve new plan version" }).click();
    await expect(page.locator("main").getByRole("alert").first()).toBeVisible();
  }
});

test("API error screen supports retry after transient failure", async ({ page }) => {
  await login(page, "patient1");
  await page.route("**/api/nutrition/overview/", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        error: { code: "unavailable", message: "Temporary test failure", details: {} },
      }),
    }),
  );
  await page.goto("/patient/nutrition/");
  await expect(page.locator("main").getByRole("alert")).toContainText("Temporary test failure");
  await page.unroute("**/api/nutrition/overview/");
  await page.getByRole("button", { name: "Retry" }).click();
  await expect(page.locator("main").getByRole("alert")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Nutrition plan", exact: true })).toBeVisible();
});

test("meal entry rejects invalid amounts and safely saves Unicode text", async ({ page }) => {
  await login(page, "patient1");
  await page.goto("/patient/nutrition/add/");
  await expect(page.getByRole("heading", { name: "Choose foods and portions" })).toBeVisible();
  await page.getByLabel("What it was").fill("وجبة تجريبية <script>alert(1)</script>");
  for (const amount of ["", "0", "-1", "abc"]) {
    await page.getByLabel("Amount", { exact: true }).fill(amount);
    await page.getByRole("button", { name: "Save meal" }).click();
    await expect(page.locator("main").getByRole("alert")).toContainText("amount above zero");
  }
  await page.getByLabel("Amount", { exact: true }).fill("1");
  await page.getByLabel("This food and amount are right").check();
  await page.getByRole("button", { name: "Save meal" }).click();
  await expect(page.getByRole("heading", { name: "Meal saved" })).toBeVisible();
  await expect(page.getByText("Needs review", { exact: true })).toBeVisible();
  await page.goto("/patient/nutrition/history/");
  await expect(
    page.locator("main p").filter({ hasText: "وجبة تجريبية <script>alert(1)</script>" }).first(),
  ).toBeVisible();
});

test("mobile Arabic login remains usable and language choice survives reload", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/login/");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.getByLabel("اسم المستخدم")).toBeVisible();
  await expect(page.getByRole("button", { name: "تسجيل الدخول" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  await page.getByRole("button", { name: "الإنجليزية", exact: true }).click();
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await expect(page.getByLabel("Username", { exact: true })).toBeVisible();
});

test("patient is redirected away from every staff route", async ({ page }) => {
  await login(page, "patient1");
  const id = "00000000-0000-0000-0000-000000000001";
  for (const route of [
    "/doctor/",
    "/nurse/",
    "/dietitian/",
    `/doctor/patients/${id}/`,
    `/doctor/sessions/${id}/`,
    `/nurse/sessions/${id}/`,
    ...["", "reports/", "lab-review/"].map((s) => `/doctor/patients/${id}/nutrition/${s}`),
  ]) {
    await page.goto(route);
    await expect(page).toHaveURL(/\/patient\/$/);
  }
});
