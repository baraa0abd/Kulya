import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const password = () => process.env.E2E_PASSWORD ?? fs.readFileSync(path.resolve(__dirname, "../../.env"), "utf8").match(/^DEMO_PASSWORD=(.+)$/m)?.[1].trim() ?? "";

test("Arabic login validation and invalid credentials are localized", async ({ page }) => {
  await page.goto("/login/");
  await page.getByRole("button", { name: "تسجيل الدخول", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "مطلوب" })).toHaveCount(2);
  await page.getByLabel("اسم المستخدم", { exact: true }).fill("LJLK");
  await page.getByLabel("كلمة المرور", { exact: true }).fill("incorrect");
  await page.getByRole("button", { name: "تسجيل الدخول", exact: true }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText("لم يتم العثور على حساب نشط");
  await expect(page.locator("main").getByRole("alert")).not.toContainText(/[a-z]/i);
  await page.getByRole("button", { name: "الإنجليزية", exact: true }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText("No active account");
});

for (const role of ["doctor", "nurse", "patient", "dietitian", "family"]) {
  test(`${role}: every screen has Arabic controls and RTL layout`, async ({ page }) => {
    await page.goto("/login/");
    await page.getByLabel("اسم المستخدم", { exact: true }).fill(`${role}1`);
    await page.getByLabel("كلمة المرور", { exact: true }).fill(password());
    await page.getByRole("button", { name: "تسجيل الدخول", exact: true }).click();
    await expect(page.getByRole("button", { name: "تسجيل الخروج" })).toBeVisible();
    const access = await page.evaluate(() => JSON.parse(sessionStorage.getItem("kulya.session")!).access);
    const headers = { Authorization: `Bearer ${access}` };
    let routes: string[];
    if (role === "patient" || role === "family") {
      routes = ["/patient/", ...["", "add/", "history/", "suggestions/", "labs/", "reports/"].map(s => `/patient/nutrition/${s}`)];
    } else {
      const response = await page.request.get(role === "dietitian" ? "/api/nutrition/overview/" : "/api/patients/", { headers });
      expect(response.ok()).toBeTruthy();
      const data = await response.json();
      const patient = role === "dietitian" ? data[0].patient : data.results[0].id;
      routes = [`/${role}/`, ...["", "lab-review/", "reports/"].map(s => `/doctor/patients/${patient}/nutrition/${s}`)];
      if (role === "doctor") routes.push(`/doctor/patients/${patient}/`);
      if (role !== "dietitian") {
        const sessions = await page.request.get(`/api/sessions/?patient=${patient}`, { headers });
        routes.push(`/${role}/sessions/${(await sessions.json()).results[0].id}/`);
      }
    }
    for (const route of routes) {
      await test.step(route, async () => {
        await page.goto(route);
        await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
        await expect(page.getByText("جارٍ التحميل…", { exact: true })).toHaveCount(0);
        await expect(page.locator("html")).toHaveAttribute("lang", "ar");
        await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
        const copy = await page.locator("header h1, main h2, main h3, main button, header button, nav a, main label, main option, main th, main [aria-label]").evaluateAll(elements => elements.flatMap(e => [e.textContent ?? "", e.getAttribute("aria-label") ?? ""]).map(s => s.replace(/SYN-\d+/g, "")));
        expect(copy.filter(text => /[a-z]/i.test(text))).toEqual([]);
        await expect(page.locator("main").getByRole("alert")).toHaveCount(0);
      });
    }
    await page.getByRole("button", { name: "الإنجليزية", exact: true }).click();
    await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
    await page.getByRole("button", { name: "العربية", exact: true }).click();
    await expect(page.getByRole("button", { name: "تسجيل الخروج" })).toBeVisible();
  });
}
