import { expect, type Page, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

/**
 * Renal nutrition end to end on the seeded synthetic data: the patient records a meal, the
 * dietitian reviews and releases, the nurse can only observe, the family follows consent.
 * Needs the same running stack as workflow.spec.ts. It adds a meal and releases a report for
 * SYN-001, so reset the demo data afterwards.
 */
function demoPassword(): string {
  if (process.env.E2E_PASSWORD) return process.env.E2E_PASSWORD;
  const env = fs.readFileSync(path.resolve(__dirname, "../../.env"), "utf8");
  const match = env.match(/^DEMO_PASSWORD=(.+)$/m);
  if (!match) throw new Error("Set E2E_PASSWORD or DEMO_PASSWORD");
  return match[1].trim();
}

async function signIn(page: Page, username: string, home: RegExp, english = true) {
  if (english) await page.addInitScript(() => window.localStorage.setItem("kulya.locale", "en"));
  await page.goto("/login/");
  await page.getByLabel(english ? "Username" : "اسم المستخدم").fill(username);
  await page.getByLabel(english ? "Password" : "كلمة المرور").fill(demoPassword());
  await page.getByRole("button", { name: english ? "Sign in" : "تسجيل الدخول" }).click();
  await expect(page).toHaveURL(home);
}

/** Optional screenshots for a visual check: E2E_SHOTS=<directory>. */
async function shot(page: Page, name: string) {
  if (process.env.E2E_SHOTS) await page.screenshot({ path: path.join(process.env.E2E_SHOTS, `${name}.png`), fullPage: true });
}

test.describe.configure({ mode: "serial" });
let reviewUrl = "";

// Establish this suite's plan explicitly, so prior runs cannot change its assumptions.
test.beforeAll(async ({ request }) => {
  const login = await request.post("/api/auth/login/", { data: { username: "dietitian1", password: demoPassword() } });
  expect(login.ok()).toBeTruthy();
  const headers = { Authorization: `Bearer ${(await login.json()).access}` };
  const overview = await request.get("/api/nutrition/overview/", { headers });
  const patient = (await overview.json()).find((row: { patient_name: string }) => row.patient_name === "Synthetic Patient One").patient;
  const plan = await request.post(`/api/nutrition/patients/${patient}/plans/`, { headers, data: { prescribed_targets: { potassium_mg_max: 600, sodium_mg_max: 600, phosphorus_mg_max: 350 }, allergies: ["fish"], guidance: "Synthetic browser test plan." } });
  expect(plan.status()).toBe(201);
});

test("patient sees the approved plan and records a meal after confirming each food", async ({ page }) => {
  await signIn(page, "patient1", /\/patient\/$/);
  await page.getByRole("link", { name: "Nutrition" }).first().click();
  await expect(page).toHaveURL(/\/patient\/nutrition\/$/);
  await expect(page.getByText(/Potassium: up to 600 mg per meal/)).toBeVisible();
  await expect(page.getByText(/Estimates only/).first()).toBeVisible();
  await shot(page, "patient-overview-en");

  await page.getByRole("link", { name: "Add a meal" }).first().click();
  await page.getByText(/^Optional: describe/).click();
  await page.getByLabel("What did you eat?").fill("2 boiled eggs and 1 cup rice");
  await page.getByRole("button", { name: "Find foods" }).click();
  const ticks = page.getByLabel("This food and amount are right");
  await expect(ticks).toHaveCount(2); // proposed, not saved
  await expect(page.getByText("The assistant was not sure. Please check.")).toHaveCount(2);
  await shot(page, "patient-add-en");
  for (const tick of await ticks.all()) await tick.check();
  await page.getByRole("button", { name: "Save meal" }).click();
  await expect(page.getByRole("heading", { name: "Meal saved" })).toBeVisible();
  await expect(page.getByText("Confirmed")).toBeVisible();
  await expect(page.getByText("181.3 mg")).toBeVisible(); // potassium: 100 g egg + 158 g rice, from the catalogue
});

test("patient sees only reviewed personalized ideas and no unreleased report", async ({ page }) => {
  await signIn(page, "patient1", /\/patient\/$/);
  await page.goto("/patient/nutrition/suggestions/");
  await expect.poll(() => page.getByText(/approved by Dietitian Demo/).count()).toBeGreaterThanOrEqual(2);
  await expect(page.getByRole("button", { name: "Approve" })).toHaveCount(0);
  await page.goto("/patient/nutrition/reports/");
  await expect(page.getByRole("button", { name: "Release to the patient" })).toHaveCount(0);
  await page.goto("/patient/nutrition/labs/");
  await expect(page.getByText("No review has been shared yet.")).toBeVisible();
});

test("dietitian reviews a meal idea and releases the report", async ({ page }) => {
  await signIn(page, "dietitian1", /\/dietitian\/$/);
  await expect(page.getByTestId("whoami")).toContainText("Renal dietitian");
  await expect(page.getByRole("link", { name: "Open nutrition review" })).toHaveCount(3);
  await shot(page, "dietitian-dashboard-en");
  await page.getByRole("row", { name: /Synthetic Patient One/ }).getByRole("link").click();
  await expect(page).toHaveURL(/\/doctor\/patients\/[0-9a-f-]+\/nutrition\/$/);
  reviewUrl = page.url();
  await expect(page.getByRole("button", { name: "Approve new plan version" })).toBeVisible();
  await page.getByLabel("Potassium limit per meal (mg)").fill("600");
  await page.getByLabel("Sodium limit per meal (mg)").fill("600");
  await page.getByLabel("Phosphorus limit per meal (mg)").fill("350");
  await page.getByLabel("Allergies (comma separated)").fill("fish");
  const planSaved = page.waitForResponse(r => r.url().includes("/plans/") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Approve new plan version" }).click();
  expect((await planSaved).status()).toBe(201);
  await page.getByRole("button", { name: "Look for meal ideas" }).click();
  const approve = page.getByRole("button", { name: "Approve", exact: true });
  await expect(approve.first()).toBeVisible();
  const approved = page.getByText("Approved", { exact: true });
  const approvedBefore = await approved.count();
  await approve.first().click();
  await expect.poll(() => approved.count()).toBeGreaterThan(approvedBefore);
  await shot(page, "clinician-nutrition-en");

  await page.getByRole("link", { name: "Food and lab results" }).first().click();
  await expect(page.getByText(/no cause is implied/).first()).toBeVisible();
  await expect(page.getByTestId("ai-label").first()).toBeVisible();

  await page.getByRole("link", { name: "Nutrition reports" }).first().click();
  await page.getByRole("button", { name: "Draft a report for the last 30 days" }).click();
  await expect(page.getByText("Draft", { exact: true }).first()).toBeVisible();
  await page.getByLabel("Clinician note").first().fill("Reviewed. Synthetic demo release.");
  await page.getByRole("button", { name: "Release to the patient" }).first().click();
  await expect(page.getByText(/AI-drafted, reviewed and released by Dietitian Demo/).first()).toBeVisible();
});

test("patient now sees the released report", async ({ page }) => {
  await signIn(page, "patient1", /\/patient\/$/);
  await page.goto("/patient/nutrition/reports/");
  await expect(page.getByText(/reviewed and released by Dietitian Demo/).first()).toBeVisible();
  await expect(page.getByText("Reviewed. Synthetic demo release.").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Print or save as PDF" }).first()).toBeVisible();
  await shot(page, "patient-report-en");
});

test("nurse can read and record an observation but cannot approve anything", async ({ page }) => {
  await signIn(page, "nurse1", /\/nurse\/$/);
  await page.goto(reviewUrl);
  await expect(page.getByRole("heading", { name: "Nursing observations about eating" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Record observation" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve new plan version" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Approve", exact: true })).toHaveCount(0);
});

test("family access follows the patient's consent", async ({ browser }) => {
  const allowed = await browser.newPage();
  await signIn(allowed, "family1", /\/patient\/$/);
  await allowed.goto("/patient/nutrition/");
  await expect(allowed.getByRole("link", { name: "Add a meal" }).first()).toBeVisible(); // delegated entry granted
  await expect(allowed.getByText(/Potassium: up to 600 mg per meal/)).toBeVisible();
  await allowed.close();
  const expired = await browser.newPage();
  await signIn(expired, "family2", /\/patient\/$/);
  await expired.goto("/patient/nutrition/");
  await expect(expired.getByText("No patient has shared their nutrition information with you.")).toBeVisible();
  await expired.close();
});

test("the nutrition area is Arabic and right-to-left by default", async ({ page }) => {
  await signIn(page, "patient1", /\/patient\/$/, false);
  await page.goto("/patient/nutrition/");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.getByRole("heading", { name: "التغذية", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "خطة التغذية" })).toBeVisible();
  await shot(page, "patient-overview-ar");
  await page.goto("/patient/nutrition/suggestions/");
  await expect(page.getByRole("heading", { name: "أفكار للوجبات" })).toBeVisible();
  await shot(page, "patient-suggestions-ar");
});
