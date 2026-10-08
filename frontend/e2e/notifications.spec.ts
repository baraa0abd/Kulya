import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const password = () =>
  process.env.E2E_PASSWORD ??
  fs
    .readFileSync(path.resolve(__dirname, "../../.env"), "utf8")
    .match(/^DEMO_PASSWORD=(.+)$/m)?.[1]
    .trim() ??
  "";

for (const role of ["patient", "doctor", "nurse"]) {
  test(`${role} notification opens its exact session and marks it read`, async ({ page }) => {
    if (role === "nurse") {
      const doctor = await page.request.post("/api/auth/login/", {
        data: { username: "doctor1", password: password() },
      });
      expect(doctor.ok()).toBeTruthy();
      const auth = { Authorization: `Bearer ${(await doctor.json()).access}` };
      const sessions = await page.request.get("/api/sessions/", { headers: auth });
      const session = (await sessions.json()).results[0].id;
      const feedback = await page.request.post("/api/doctor/feedback/", {
        headers: auth,
        data: {
          session,
          kind: "feedback",
          text: "E2E: please document the reason for this action.",
        },
      });
      expect(feedback.ok()).toBeTruthy();
    }
    await page.addInitScript(() => localStorage.setItem("kulya.locale", "en"));
    await page.goto("/login/");
    await page.getByLabel("Username", { exact: true }).fill(`${role}1`);
    await page.getByLabel("Password", { exact: true }).fill(password());
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
    const access = await page.evaluate(
      () => JSON.parse(sessionStorage.getItem("kulya.session")!).access,
    );
    const headers = { Authorization: `Bearer ${access}` };
    const inbox = await page.request.get("/api/notifications/", { headers });
    const notification = (await inbox.json()).results
      .slice(0, 6)
      .find((n: { session: string | null }) => n.session);
    expect(notification).toBeTruthy();
    const destination = `/${role}/sessions/${notification.session}/`;
    await page.locator("#notifications").locator(`a[href="${destination}"]`).first().click();
    await expect(page).toHaveURL(new RegExp(destination));
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      role === "patient"
        ? "Dialysis session"
        : role === "doctor"
          ? "Session review"
          : "Dialysis session",
    );
    await expect
      .poll(async () => {
        const updated = await page.request.get("/api/notifications/", { headers });
        return (await updated.json()).results.find((n: { id: string }) => n.id === notification.id)
          .read_at;
      })
      .toBeTruthy();
    if (role === "patient") {
      const response = await page.request.get(
        `/api/ai/summaries/?session=${notification.session}`,
        { headers },
      );
      const summaries = (await response.json()).results;
      expect(summaries.length).toBeGreaterThan(0);
      await expect(page.locator("main")).toContainText(summaries[0].text);
      await expect(page.getByRole("button", { name: "Approve summary" })).toHaveCount(0);
      await page.goto("/patient/sessions/00000000-0000-0000-0000-000000000000/");
      await expect(
        page.getByText("No summaries have been released yet.", { exact: true }),
      ).toBeVisible();
    }
  });
}
