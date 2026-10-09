import { getLocale, tr } from "./i18n";

// Arabic month names with Latin digits, so numbers read the same as the measurements beside them.
const format = (options: Intl.DateTimeFormatOptions) =>
  new Intl.DateTimeFormat(getLocale() === "ar" ? "ar-u-nu-latn" : "en-GB", options);

export const dateTime = (iso: string | null | undefined) =>
  iso ? format({ dateStyle: "medium", timeStyle: "short" }).format(new Date(iso)) : "—";
export const dateOnly = (iso: string | null | undefined) =>
  iso ? format({ dateStyle: "medium" }).format(new Date(iso)) : "—";
export const timeOnly = (iso: string | null | undefined) =>
  iso ? format({ timeStyle: "short" }).format(new Date(iso)) : "—";

/** "systolic_bp" -> "Systolic bp", then translated for the current language. */
export const label = (code: string) => {
  const text = code.replaceAll("_", " ");
  return tr(text.charAt(0).toUpperCase() + text.slice(1));
};

/**
 * A value is always shown with its unit; a missing value is shown as missing, never as zero.
 * Arabic unit labels are isolated with their original numeric values to keep the pair together.
 */
export const withUnit = (value: string | number | null | undefined, unit: string) => {
  if (value === null || value === undefined || value === "") return tr("Not recorded");
  const text = `${Number(value)} ${tr(unit)}`;
  return getLocale() === "ar" ? `⁦${text}⁩` : text;
};

export const minutesBetween = (start: string | null, end: string | null): number | null =>
  start && end ? Math.round((new Date(end).getTime() - new Date(start).getTime()) / 60000) : null;

/** Local YYYY-MM-DD for the "today" schedule filter. */
export const today = () => {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
};

/** Monday of the week a date falls in, as YYYY-MM-DD. */
export const weekOf = (iso: string) => {
  const day = new Date(iso);
  day.setDate(day.getDate() - ((day.getDay() + 6) % 7));
  return day.toISOString().slice(0, 10);
};

/** False only in a build made with NEXT_PUBLIC_DEMO_MODE=false: no demo seed, real records. */
export const DEMO = process.env.NEXT_PUBLIC_DEMO_MODE !== "false";
