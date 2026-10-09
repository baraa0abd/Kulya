import { expect, type Page, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

/**
 * End-to-end nurse -> AI -> doctor -> patient workflow on the seeded synthetic data.
 * Needs: backend on :8000 (seed_demo run, mock LLM), frontend on :3000, and the demo password
 * in E2E_PASSWORD or in the repo-root .env as DEMO_PASSWORD. The run changes today's session
 * for SYN-001, so reset the demo data afterwards.
 */
function demoPassword(): string {
  if (process.env.E2E_PASSWORD) return process.env.E2E_PASSWORD;
  const env = fs.readFileSync(path.resolve(__dirname, "../../.env"), "utf8");
  const match = env.match(/^DEMO_PASSWORD=(.+)$/m);
  if (!match) throw new Error("Set E2E_PASSWORD or DEMO_PASSWORD");
  return match[1].trim();
}

async function signIn(page: Page, username: string, home: RegExp) {
  await page.goto("/login/");
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password").fill(demoPassword());
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(home);
}

test.describe.configure({ mode: "serial" });

test("the interface is Arabic and right-to-left by default", async ({ page }) => {
  await page.goto("/login/");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.locator("html")).toHaveAttribute("lang", "ar");
  await expect(page.getByRole("button", { name: "تسجيل الدخول" })).toBeVisible();
  await page.getByLabel("اسم المستخدم").fill("nurse1");
  await page.getByLabel("كلمة المرور").fill(demoPassword());
  await page.getByRole("button", { name: "تسجيل الدخول" }).click();
  await expect(page).toHaveURL(/\/nurse\/$/);
  await expect(page.getByRole("heading", { name: "لوحة التمريض" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "جدول الغسيل لليوم" })).toBeVisible();
  // The toggle switches to English, left-to-right.
  await page.getByRole("button", { name: "الإنجليزية" }).click();
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await expect(page.getByRole("heading", { name: "Nurse dashboard" })).toBeVisible();
});

// The workflow tests below assert on the English source strings.
test.beforeEach(async ({ page }, testInfo) => {
  if (testInfo.title.includes("Arabic")) return;
  await page.addInitScript(() => window.localStorage.setItem("kulya.locale", "en"));
});
let sessionUrl = "";

test("doctor signs in and sees only assigned patients and pending reviews", async ({ page }) => {
  await signIn(page, "doctor1", /\/doctor\/$/);
  await expect(page.getByTestId("whoami")).toContainText("Doctor");
  await expect(page.getByRole("cell", { name: "SYN-001" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "SYN-002" })).toBeVisible();
  await expect(page.getByText("SYN-003")).toHaveCount(0); // doctor2's patient
  await expect(page.getByRole("link", { name: "Review" }).first()).toBeVisible();
});

test("nurse starts a session, documents care, sees completeness checks, and completes it", async ({
  page,
}) => {
  await signIn(page, "nurse1", /\/nurse\/$/);
  const access = await page.evaluate(
    () => JSON.parse(sessionStorage.getItem("kulya.session")!).access,
  );
  const headers = { Authorization: `Bearer ${access}` };
  const patients = await page.request.get("/api/patients/", { headers });
  const patient = (await patients.json()).results.find((p: { mrn: string }) => p.mrn === "SYN-001");
  const created = await page.request.post("/api/sessions/", {
    headers,
    data: { patient: patient.id, scheduled_start: new Date().toISOString() },
  });
  expect(created.status()).toBe(201);
  await page.goto(`/nurse/sessions/${(await created.json()).id}/`);
  await expect(page).toHaveURL(/\/nurse\/sessions\/[0-9a-f-]{36}\/$/);
  sessionUrl = new URL(page.url()).pathname;

  await page.getByLabel("Pre-treatment weight (kg)").fill("64.2");
  await page.getByRole("button", { name: "Start session" }).click();
  await expect(page.getByText("In progress")).toBeVisible();

  await page.getByLabel("Value").fill("142");
  await page.getByRole("button", { name: "Record vital sign" }).click();
  await expect(page.getByText("142 mmHg")).toBeVisible();

  // An out-of-range value is refused by the server and nothing is saved.
  await page.getByLabel("Value").fill("1420");
  await page.getByRole("button", { name: "Record vital sign" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "plausible range" })).toBeVisible();

  await page.getByRole("tab", { name: "Nursing action" }).click();
  await page.getByLabel("What was done").fill("E2E: access site checked and dressed.");
  await page.getByRole("button", { name: "Record nursing action" }).click();
  await expect(page.getByText("E2E: access site checked and dressed.")).toBeVisible();
  await expect(page.getByTestId("completeness")).toContainText("Action without reason");

  await page.getByLabel("Post-treatment weight (kg)").fill("62.1");
  await page.getByLabel("Ultrafiltration volume (mL)").fill("2000");
  await page.getByRole("button", { name: "Complete session" }).click();
  await expect(page.getByText("Completed", { exact: true })).toBeVisible();
});

test("doctor reviews the AI draft, sends feedback, verifies and releases the summary", async ({
  page,
}) => {
  await signIn(page, "doctor1", /\/doctor\/$/);
  await page.goto(sessionUrl.replace("/nurse/", "/doctor/"));
  await expect(page.getByRole("heading", { name: "AI documentation review" })).toBeVisible();
  await expect(page.getByTestId("ai-label").first()).toContainText("AI-generated");
  await expect(page.getByText("Action without reason").first()).toBeVisible();
  await expect(page.getByText("synthetic demo policy").first()).toBeVisible(); // cited protocol passage

  await page
    .getByLabel("Feedback", { exact: true })
    .fill("E2E: please document the reason for this action.");
  await page.getByRole("button", { name: "Send feedback" }).click();
  await expect(page.getByText("E2E: please document the reason for this action.")).toBeVisible();

  await expect(page.getByText("Unverified")).toBeVisible();
  await page.getByRole("button", { name: "Verify summary" }).click();
  await page.getByRole("button", { name: "Release to patient" }).click();
  await expect(page.getByText("Released", { exact: true })).toBeVisible();
});

test("nurse sees the doctor's feedback", async ({ page }) => {
  await signIn(page, "nurse1", /\/nurse\/$/);
  await expect(
    page.getByText("E2E: please document the reason for this action.").first(),
  ).toBeVisible();
});

test("patient sees the released summary and nothing clinical", async ({ page }) => {
  await signIn(page, "patient1", /\/patient\/$/);
  await expect(page.getByText("Your dialysis session was recorded.").first()).toBeVisible();
  expect(
    await page.getByText("Your dialysis session was recorded.").count(),
  ).toBeGreaterThanOrEqual(3);
  await expect(page.getByText("AI documentation review")).toHaveCount(0);
  await page.getByRole("link", { name: "Family and home" }).first().click();
  await expect(page.getByRole("heading", { name: "Family sharing" })).toBeVisible();
});

test("unauthorized users are denied", async ({ page }) => {
  // A patient cannot open staff screens: sent back to their own dashboard.
  await signIn(page, "patient1", /\/patient\/$/);
  await page.goto("/doctor/");
  await expect(page).toHaveURL(/\/patient\/$/);
  // And the API refuses regardless of what the browser shows.
  const tokens = await page.evaluate(() =>
    JSON.parse(window.sessionStorage.getItem("kulya.session") ?? "{}"),
  );
  const headers = { Authorization: `Bearer ${tokens.access}` };
  expect((await page.request.get("/api/nursing-actions/", { headers })).status()).toBe(403);
  expect(
    (
      await page.request.get(
        `/api${sessionUrl.replace("/nurse", "")}`
          .replace("/sessions/", "/ai/reviews/?session=")
          .replace(/\/$/, ""),
        { headers },
      )
    ).status(),
  ).toBe(403);

  // A nurse from another care team gets "Not found" for this patient's session.
  await signIn(page, "nurse4", /\/nurse\/$/);
  await page.goto(sessionUrl);
  await expect(page.getByRole("alert").filter({ hasText: "Not found." })).toBeVisible();

  // Signed out: straight to login.
  await page.getByRole("button", { name: "Sign out" }).click();
  await page.goto("/nurse/");
  await expect(page).toHaveURL(/\/login\/$/);
});
