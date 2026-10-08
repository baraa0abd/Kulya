"use client";

import { AiLabel, ErrorNote, Load, Section, Status } from "@/components/feedback";
import { ZForm } from "@/components/forms";
import { Button } from "@/components/ui/button";
import { DiaryFacts } from "@/features/nutrition/components/common";
import { type FoodLabReview, type LabFact, type LabTrendsData } from "@/features/nutrition/types";
import { api } from "@/lib/api";
import { dateOnly, withUnit } from "@/lib/format";
import { useAction, useGet } from "@/lib/hooks";
import { tr, Tx } from "@/lib/i18n";
import { FlaskConical, Sparkles } from "lucide-react";
import { z } from "zod";
export function LabTable({ labs }: { labs: LabFact[] }) {
  if (!labs.length) {
    return (
      <p className="text-sm text-ink-3">
        <Tx k="No laboratory results to show for this period." />
      </p>
    );
  }
  return (
    <ul className="divide-y divide-line text-sm">
      {labs.map((lab) => (
        <li key={lab.id} className="flex flex-wrap gap-x-4 gap-y-1 py-1.5">
          <span className="font-medium">{tr(lab.analyte ?? "")}</span>
          <span className="font-semibold">{withUnit(lab.value, lab.unit)}</span>
          {lab.reference_low !== null && lab.reference_high !== null && (
            <span className="text-ink-3">
              {tr("laboratory range")}{" "}
              <span dir="ltr">{`${lab.reference_low}–${lab.reference_high} ${tr(lab.unit)}`}</span>
            </span>
          )}
          <time className="ms-auto text-ink-3">{dateOnly(lab.collected_at)}</time>
        </li>
      ))}
    </ul>
  );
}

const noteSchema = z.object({ notes: z.string().trim().max(2000) });

function ReviewCard({
  review,
  canDecide,
  onChange,
}: {
  review: FoodLabReview;
  canDecide: boolean;
  onChange: () => void;
}) {
  const open = review.review_status === "pending" || review.review_status === "ai_unavailable";
  const send = (approve: boolean) => async (values: { notes: string }) => {
    await api.post(`/nutrition/lab-reviews/${review.id}/review/`, { approve, notes: values.notes });
    onChange();
  };
  return (
    <li className="space-y-2 rounded-lg border border-line p-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-semibold">
          {dateOnly(review.date_from)} – {dateOnly(review.date_to)}
        </span>
        <Status value={review.review_status} />
        {review.reviewed_by_name && (
          <span className="text-ink-3">{tr(review.reviewed_by_name ?? "")}</span>
        )}
      </div>
      {review.review_status === "approved" ? (
        <p className="micro text-ok">{tr("Reviewed by a clinician")}</p>
      ) : (
        <AiLabel text="Unverified draft. It describes records side by side and does not show that food changed any result." />
      )}
      {review.ai_error.length > 0 && (
        <p className="text-sm text-bad">
          {tr(
            "The AI draft was unavailable or rejected by the safety checks. The recorded facts are still shown.",
          )}
        </p>
      )}
      <ul className="list-disc space-y-1 ps-5 text-sm leading-6" dir="auto">
        {review.possible_associations.map((item) => (
          <li key={item.text}>{tr(item.text ?? "")}</li>
        ))}
      </ul>
      {review.questions.length > 0 && canDecide && (
        <ul className="list-disc ps-5 text-sm text-ink-2" dir="auto">
          {review.questions.map((q) => (
            <li key={q}>{tr(q ?? "")}</li>
          ))}
        </ul>
      )}
      <ul className="list-disc ps-5 text-xs text-ink-3">
        {review.limitations.map((note) => (
          <li key={note}>{tr(note)}</li>
        ))}
      </ul>
      {review.review_notes && (
        <p className="text-sm" dir="auto">
          <span className="font-medium">{tr("Clinician note")}:</span>{" "}
          {tr(review.review_notes ?? "")}
        </p>
      )}
      {canDecide && open && (
        <div className="grid gap-2 lg:grid-cols-2">
          <ZForm
            schema={noteSchema}
            submitLabel="Approve for the patient"
            fields={[{ name: "notes", label: "Clinician note", type: "textarea" }]}
            onSubmit={send(true)}
          />
          <ZForm
            schema={noteSchema}
            submitLabel="Reject draft"
            fields={[{ name: "notes", label: "Reason", type: "textarea" }]}
            onSubmit={send(false)}
          />
        </div>
      )}
    </li>
  );
}

export function LabPanel({ patient, canDecide }: { patient: string; canDecide: boolean }) {
  const trends = useGet<LabTrendsData>(`/nutrition/patients/${patient}/lab-trends/`);
  const analyze = useAction();
  return (
    <>
      <Section
        icon={FlaskConical}
        title="Food diary and laboratory results"
        description="The last 30 days, shown side by side. Many things other than food affect laboratory results."
      >
        <Load from={trends}>
          {(data) => (
            <div className="space-y-4">
              <DiaryFacts summary={data.diary} />
              <LabTable labs={data.laboratory_results} />
            </div>
          )}
        </Load>
      </Section>
      <Section
        icon={Sparkles}
        tone="ai"
        title="Food and laboratory review"
        description="A descriptive draft for the clinician. It never states a cause."
        action={
          canDecide && (
            <Button
              variant="outline"
              disabled={analyze.pending}
              onClick={async () =>
                (await analyze.run(() => api.post("/nutrition/ai/analyze/", { patient }))) &&
                trends.reload()
              }
            >
              <Tx k="Draft a review" />
            </Button>
          )
        }
      >
        <ErrorNote message={analyze.error} />
        <Load from={trends}>
          {(data) =>
            data.reviews.length ? (
              <ul className="space-y-3">
                {data.reviews.map((review) => (
                  <ReviewCard
                    key={review.id}
                    review={review}
                    canDecide={canDecide}
                    onChange={trends.reload}
                  />
                ))}
              </ul>
            ) : (
              <p className="text-sm text-ink-3">
                <Tx k="No review has been shared yet." />
              </p>
            )
          }
        </Load>
      </Section>
    </>
  );
}
