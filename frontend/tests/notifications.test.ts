import { notificationHref } from "@/features/notifications/navigation";
import { type Notification } from "@/lib/types";
import { expect, it } from "vitest";

const notification: Notification = {
  id: "n1",
  kind: "summary_released",
  title: "A session summary is available",
  session: "session-1",
  read_at: null,
  created_at: "2026-10-08T12:00:00Z",
};
it.each(["doctor", "nurse", "patient", "family"] as const)(
  "opens the correct session for %s",
  (role) => {
    const area = role === "family" ? "patient" : role;
    expect(notificationHref(notification, role)).toBe(`/${area}/sessions/session-1/`);
  },
);
it("does not direct unsupported roles to clinical session records", () => {
  expect(notificationHref(notification, "dietitian")).toBeNull();
  expect(notificationHref(notification, "auditor")).toBeNull();
});
it("routes nutrition reports separately and leaves untargeted notifications alone", () => {
  expect(
    notificationHref({ ...notification, session: null, kind: "nutrition_report" }, "patient"),
  ).toBe("/patient/nutrition/reports/");
  expect(
    notificationHref({ ...notification, session: null, kind: "unknown" }, "patient"),
  ).toBeNull();
});
