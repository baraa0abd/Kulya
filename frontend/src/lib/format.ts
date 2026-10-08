const DATE_TIME = new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" });
const DATE = new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" });
const TIME = new Intl.DateTimeFormat("en-GB", { timeStyle: "short" });

export const dateTime = (iso: string | null | undefined) => (iso ? DATE_TIME.format(new Date(iso)) : "—");
export const dateOnly = (iso: string | null | undefined) => (iso ? DATE.format(new Date(iso)) : "—");
export const timeOnly = (iso: string | null | undefined) => (iso ? TIME.format(new Date(iso)) : "—");

/** "systolic_bp" -> "Systolic bp" */
export const label = (code: string) => {
  const text = code.replaceAll("_", " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
};

/** A value is always shown with its unit; a missing value is shown as missing, never as zero. */
export const withUnit = (value: string | number | null | undefined, unit: string) =>
  value === null || value === undefined || value === "" ? "Not recorded" : `${Number(value)} ${unit}`;

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
