import { defineConfig } from "@playwright/test";

// Runs against an already running stack (backend :8000 with seeded demo data, frontend :3000).
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  workers: 1,
  use: { baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000", trace: "retain-on-failure" },
  reporter: [["list"]],
});
