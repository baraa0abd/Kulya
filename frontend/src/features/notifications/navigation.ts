import { type Notification, type Role } from "@/lib/types";

/** Destination is chosen from the viewer's role; API authorization still applies. */
export function notificationHref(notification: Notification, role: Role): string | null {
  if (notification.session) {
    const session = encodeURIComponent(notification.session);
    if (role === "doctor" || role === "nurse") return `/${role}/sessions/${session}/`;
    if (role === "patient" || role === "family") return `/patient/sessions/${session}/`;
  }
  if (notification.kind === "nutrition_report" && (role === "patient" || role === "family"))
    return "/patient/nutrition/reports/";
  if (notification.kind === "meal_ideas" && (role === "patient" || role === "family"))
    return "/patient/nutrition/suggestions/";
  if (notification.patient && ["doctor", "nurse", "dietitian"].includes(role)) {
    return `/doctor/patients/${encodeURIComponent(notification.patient)}/nutrition/${notification.kind === "nutrition_review" ? "lab-review/" : ""}`;
  }
  return null;
}
