"use client";

import { AiLabel, ErrorNote, Load, Section, Status } from "@/components/feedback";
import { ZForm } from "@/components/forms";
import { Button } from "@/components/ui/button";
import { NutrientTray } from "@/features/nutrition/components/common";
import { LabTable } from "@/features/nutrition/components/labs";
import { type NutritionReport } from "@/features/nutrition/types";
import { api } from "@/lib/api";
import { dateOnly } from "@/lib/format";
import { useAction, useGet } from "@/lib/hooks";
import { tr, Tx } from "@/lib/i18n";
import { FileText, Printer } from "lucide-react";
import { z } from "zod";
const releaseSchema = z.object({ clinician_review: z.string().trim().max(4000) });

function ReportCard({
  report,
  canDecide,
  onChange,
}: {
  report: NutritionReport;
  canDecide: boolean;
  onChange: () => void;
}) {
  const draft = report.ai_draft;
  const summary = report.meal_summary;
  return (
    <li className="space-y-3 rounded-lg border border-line p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-semibold">
          {tr(report.patient_name ?? "")} · {dateOnly(report.period_start)} –{" "}
          {dateOnly(report.period_end)}
        </h3>
        <Status value={report.release_status} />
        <span className="text-sm text-ink-3">
          {tr("Version")} {report.version}
        </span>
        <Button
          size="sm"
          variant="outline"
          className="no-print ms-auto"
          onClick={() => window.print()}
        >
          <Printer className="size-4" aria-hidden />
          <Tx k="Print or save as PDF" />
        </Button>
      </div>
      <h4 className="micro text-ink-2">{tr("Recorded facts")}</h4>
      <p className="text-sm">
        {tr("Meals recorded on")} {summary.days_recorded} {tr("of")} {summary.days_in_period}{" "}
        {tr("days")} · {summary.meals_recorded} {tr("meals")}
      </p>
      <NutrientTray values={report.nutrient_summary.daily_average_on_complete_days} />
      <LabTable labs={report.laboratory_summary} />
      <p className="text-sm text-ink-2">
        {tr("Dialysis sessions in this period")}: {report.dialysis_summary.length}
      </p>
      <h4 className="micro text-ink-2">{tr("Narrative")}</h4>
      {draft ? (
        <div className="space-y-2 rounded-md border-s-4 border-s-ai bg-ai-soft/40 p-3">
          {report.release_status === "released" ? (
            <p className="micro text-ok">
              {tr("AI-drafted, reviewed and released by")} {tr(report.reviewed_by_name ?? "")}
            </p>
          ) : (
            <AiLabel text="Unverified draft. Not visible to the patient until a clinician releases this report." />
          )}
          <p className="leading-7" dir="auto">
            {tr(draft.overview ?? "")}
          </p>
          <ul className="list-disc ps-5 text-sm" dir="auto">
            {draft.observations.map((line) => (
              <li key={line}>{tr(line ?? "")}</li>
            ))}
          </ul>
          <ul className="list-disc ps-5 text-xs text-ink-3">
            {draft.limitations.map((note) => (
              <li key={note}>{tr(note)}</li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="text-sm text-ink-3">
          {tr("No AI narrative: it was unavailable or rejected by the safety checks.")}
        </p>
      )}
      {report.clinician_review && (
        <p className="text-sm" dir="auto">
          <span className="font-medium">{tr("Clinician note")}:</span>{" "}
          {tr(report.clinician_review ?? "")}
        </p>
      )}
      {canDecide && report.release_status !== "released" && (
        <div className="no-print">
          <ZForm
            schema={releaseSchema}
            submitLabel="Release to the patient"
            fields={[{ name: "clinician_review", label: "Clinician note", type: "textarea" }]}
            onSubmit={async (values) => {
              await api.post(`/nutrition/reports/${report.id}/release/`, values);
              onChange();
            }}
          />
        </div>
      )}
    </li>
  );
}

export function ReportsPanel({ patient, canDecide }: { patient: string; canDecide: boolean }) {
  const base = `/nutrition/patients/${patient}/reports/`;
  const reports = useGet<NutritionReport[]>(base);
  const build = useAction();
  return (
    <Section
      icon={FileText}
      title="Nutrition reports"
      description="Facts are calculated from the records. The narrative is an AI draft that a doctor or dietitian reviews before release."
      action={
        canDecide && (
          <Button
            variant="outline"
            className="no-print"
            disabled={build.pending}
            onClick={async () =>
              (await build.run(() => api.post(`${base}generate/`, {}))) && reports.reload()
            }
          >
            <Tx k="Draft a report for the last 30 days" />
          </Button>
        )
      }
    >
      <ErrorNote message={build.error} />
      <Load
        from={reports}
        empty={canDecide ? "No report has been drafted yet." : "No report has been released yet."}
      >
        {(rows) => (
          <ul className="space-y-4">
            {rows.map((report) => (
              <ReportCard
                key={report.id}
                report={report}
                canDecide={canDecide}
                onChange={reports.reload}
              />
            ))}
          </ul>
        )}
      </Load>
    </Section>
  );
}
