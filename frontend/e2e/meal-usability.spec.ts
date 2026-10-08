import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

test("patient records a meal directly, corrects it, filters the diary, and withdraws the test entry", async ({
  page,
}) => {
  const password =
    process.env.E2E_PASSWORD ??
    fs
      .readFileSync(path.resolve(__dirname, "../../.env"), "utf8")
      .match(/^DEMO_PASSWORD=(.+)$/m)?.[1]
      .trim() ??
    "";
  await page.addInitScript(() => localStorage.setItem("kulya.locale", "en"));
  await page.goto("/login/");
  await page.getByLabel("Username", { exact: true }).fill("patient1");
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
  await page.goto("/patient/nutrition/add/");
  await page.getByLabel("Search the food list").fill("cucumber");
  await page.getByRole("button", { name: "cucumber", exact: true }).click();
  await expect(page.getByLabel("What it was")).toHaveValue("cucumber");
  await expect(page.getByLabel("What it was")).not.toBeEditable();
  await page.getByLabel("Amount", { exact: true }).fill("٢");
  await page.getByRole("button", { name: "Save meal", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Confirm each food" })).toBeVisible();
  await page.getByLabel("This food and amount are right").check();
  const createdResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/nutrition/meals/") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Save meal", exact: true }).click();
  const created = await (await createdResponse).json();
  await expect(page.getByRole("heading", { name: "Meal saved", exact: true })).toBeVisible();
  const access = await page.evaluate(
    () => JSON.parse(sessionStorage.getItem("kulya.session")!).access,
  );
  const headers = { Authorization: `Bearer ${access}` };
  try {
    expect(created.estimate.potassium_mg).toBe(294);
    await page.getByRole("link", { name: "Open the diary" }).click();
    const card = page.locator("main li").filter({ hasText: "cucumber (2 piece)" }).first();
    await card.getByRole("button", { name: "Correct meal" }).click();
    await page.getByLabel("Amount", { exact: true }).fill("١٫٥");
    await page.getByLabel("This food and amount are right").check();
    await page.getByRole("button", { name: "Save meal", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Meal diary", exact: true })).toBeVisible();
    const response = await page.request.get(`/api/nutrition/meals/${created.id}/`, { headers });
    const corrected = await response.json();
    expect(corrected.components[0].quantity).toBe("1.50");
    expect(corrected.estimate.potassium_mg).toBe(220.5);
    await page.getByLabel("Show meals").selectOption("confirmed");
    await expect(
      page.locator("main li").filter({ hasText: "cucumber (1.5 piece)" }).first(),
    ).toBeVisible();
    await page.getByLabel("From", { exact: true }).fill("2099-01-02");
    await expect(page.getByRole("alert").filter({ hasText: "valid date range" })).toBeVisible();
  } finally {
    await page.request.delete(`/api/nutrition/meals/${created.id}/`, { headers });
  }
});
