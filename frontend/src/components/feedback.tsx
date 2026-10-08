"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { label } from "@/lib/format";
import { type Loaded } from "@/lib/hooks";
import { setLocale, tr, Tx, useLocale } from "@/lib/i18n";
import { CircleAlert, Languages, type LucideIcon, Sparkles } from "lucide-react";
type Tone = "default" | "ok" | "warn" | "bad" | "ai";

const TONE_TEXT: Record<Tone, string> = {
  default: "text-ink",
  ok: "text-ok",
  warn: "text-warn",
  bad: "text-bad",
  ai: "text-ai-ink",
};

export interface Stat {
  label: string;
  value: React.ReactNode;
  hint?: string;
  tone?: Tone;
  icon?: LucideIcon;
}

/** Row of key figures: micro-label on top, one large value, a short hint. Real data only. */
export function Stats({ items }: { items: Stat[] }) {
  useLocale();
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {items.map(({ label: name, value, hint, tone = "default", icon: Icon }) => (
        <div
          key={name}
          className="rounded-lg border border-line bg-white p-4 shadow-[0_1px_3px_0_rgb(23_43_58/0.04)]"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="micro text-ink-2">{tr(name)}</span>
            {Icon && <Icon className="size-4 text-ink-3" aria-hidden />}
          </div>
          <p className={`mt-2 text-3xl leading-9 font-semibold ${TONE_TEXT[tone]}`}>{value}</p>
          {hint && <p className="mt-1 text-sm text-ink-3">{tr(hint)}</p>}
        </div>
      ))}
    </div>
  );
}

export function Section({
  id,
  icon: Icon,
  title,
  description,
  action,
  tone,
  className = "",
  children,
}: {
  id?: string;
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
  /** "ai" marks content written by the model: periwinkle accent on the leading edge. */
  tone?: "ai";
  className?: string;
  children: React.ReactNode;
}) {
  const ai = tone === "ai";
  return (
    <Card id={id} className={`${ai ? "border-s-4! border-s-ai!" : ""} ${className}`}>
      <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          {Icon && (
            <span
              className={`flex size-8 shrink-0 items-center justify-center rounded-md ${ai ? "bg-ai-soft text-ai-ink" : "bg-brand-soft text-brand"}`}
            >
              <Icon className="size-4" aria-hidden />
            </span>
          )}
          <div>
            <CardTitle>
              <h2 className="text-base font-semibold text-ink">{tr(title)}</h2>
            </CardTitle>
            {description && (
              <CardDescription className="mt-0.5 text-[13px] text-ink-2">
                {tr(description)}
              </CardDescription>
            )}
          </div>
        </div>
        {action}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

/** Loading, error and empty states for anything fetched. */
export function Load<T>({
  from,
  empty,
  children,
}: {
  from: Loaded<T>;
  empty?: string;
  children: (data: T) => React.ReactNode;
}) {
  if (from.loading) {
    return (
      <div className="space-y-2" aria-busy="true">
        <p className="text-sm text-ink-3">
          <Tx k="Loading…" />
        </p>
        <div className="h-3 w-2/3 animate-pulse rounded bg-chrome" />
        <div className="h-3 w-1/2 animate-pulse rounded bg-chrome" />
      </div>
    );
  }
  if (from.error) {
    return (
      <div
        role="alert"
        className="flex flex-wrap items-center gap-3 rounded-md border border-bad/25 bg-bad-soft px-3 py-2 text-sm text-bad"
      >
        <CircleAlert className="size-4 shrink-0" aria-hidden />
        <span>{tr(from.error)}</span>
        <Button variant="outline" size="sm" className="ms-auto" onClick={from.reload}>
          <Tx k="Retry" />
        </Button>
      </div>
    );
  }
  if (from.data === null || (Array.isArray(from.data) && from.data.length === 0)) {
    return (
      <p className="rounded-md border border-dashed border-line bg-canvas px-3 py-4 text-center text-sm text-ink-3">
        {tr(empty ?? "Nothing to show yet.")}
      </p>
    );
  }
  return <>{children(from.data)}</>;
}

/** Switches between Arabic (right-to-left, default) and English. */
export function LanguageToggle() {
  const locale = useLocale();
  return (
    <Button variant="ghost" size="sm" onClick={() => setLocale(locale === "ar" ? "en" : "ar")}>
      <Languages className="size-4" aria-hidden />
      {locale === "ar" ? tr("English") : "العربية"}
    </Button>
  );
}

export function ErrorNote({ message }: { message: string | null }) {
  return message ? (
    <p role="alert" className="flex items-center gap-2 text-sm text-bad">
      <CircleAlert className="size-4 shrink-0" aria-hidden />
      {tr(message)}
    </p>
  ) : null;
}

// Clinical status badges: compact, square-cornered, colour by meaning (never colour alone: the
// text always states the status).
const OK = "border-ok/20 bg-ok-soft text-ok";

const WARN = "border-warn/25 bg-warn-soft text-warn";

const BAD = "border-bad/25 bg-bad-soft text-bad";

const INFO = "border-ai-ink/20 bg-ai-soft text-ai-ink";

const NEUTRAL = "border-line bg-chrome text-ink-2";

const STATUS_STYLE: Record<string, string> = {
  scheduled: NEUTRAL,
  in_progress: INFO,
  completed: OK,
  pending_review: WARN,
  unverified: WARN,
  open: WARN,
  processing: NEUTRAL,
  not_released: NEUTRAL,
  ai_unavailable: BAD,
  rejected: BAD,
  cancelled: BAD,
  verified: OK,
  reviewed: OK,
  released: OK,
  confirmed: OK,
  approved: OK,
  compatible: OK,
  needs_review: WARN,
  pending: WARN,
  check_portion: WARN,
  needs_dietitian_review: WARN,
  draft: NEUTRAL,
  general: NEUTRAL,
};

export function Status({ value }: { value: string }) {
  useLocale();
  return (
    <span
      className={`micro inline-flex min-h-5 items-center rounded border px-1.5 whitespace-nowrap ${STATUS_STYLE[value] ?? NEUTRAL}`}
    >
      {label(value)}
    </span>
  );
}

/** Every piece of AI-written content sits under this dashed "unverified draft" banner. */
export function AiLabel({ text }: { text: string }) {
  return (
    <p
      className="flex items-start gap-2 rounded-md border border-dashed border-ai bg-ai-soft px-3 py-2 text-sm text-ai-ink"
      data-testid="ai-label"
    >
      <Sparkles className="mt-0.5 size-4 shrink-0" aria-hidden />
      <span>
        <strong>
          <Tx k="AI-generated." />
        </strong>{" "}
        {tr(text.replace(/^AI-generated draft\.\s*/, ""))}
      </span>
    </p>
  );
}
