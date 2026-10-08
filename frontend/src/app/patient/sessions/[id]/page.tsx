"use client";

import { FileText, ShieldCheck } from "lucide-react";
import { useParams } from "next/navigation";
import { Load, Section, Shell } from "@/components/app";
import type { ReleasedSummary } from "@/lib/api";
import { useRole } from "@/lib/auth";
import { dateOnly } from "@/lib/format";
import { useList } from "@/lib/hooks";
import { tr, useLocale } from "@/lib/i18n";

export default function PatientSessionPage() {
  useLocale();
  const { id } = useParams<{ id: string }>();
  const user = useRole("patient", "family");
  // This endpoint returns only doctor-verified, released patient text, scoped to the viewer.
  const summaries = useList<ReleasedSummary>(user ? `/ai/summaries/?session=${encodeURIComponent(id)}` : null);
  if (!user) return null;
  return (
    <Shell title="Dialysis session" back="/patient/#notifications">
      <Section icon={FileText} title="Treatment summaries" description="Each summary was reviewed and released by a doctor. Discuss any question with your care team.">
        <Load from={summaries} empty={user.role === "patient" ? "No summaries have been released yet." : "No summaries are shared with you."}>
          {rows => <div className="space-y-3">{rows.map(summary => (
            <article key={summary.id} className="rounded-lg border border-line bg-chrome p-4">
              <h3 className="font-semibold">{tr(summary.patient_name)} · {tr("Session of")} {dateOnly(summary.session_date)}</h3>
              <p className="my-2 flex items-center gap-1 text-sm text-ok"><ShieldCheck className="size-4" aria-hidden />{tr("Doctor reviewed")} · {tr("released")} {dateOnly(summary.released_at)}</p>
              <p dir="auto" className="text-lg leading-8">{tr(summary.text)}</p>
            </article>
          ))}</div>}
        </Load>
      </Section>
    </Shell>
  );
}
