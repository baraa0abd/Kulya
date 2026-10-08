"use client";

import { useParams } from "next/navigation";
import { z } from "zod";

import { AiLabel, ErrorNote, Load, Measurements, requiredText, Section, Shell, Status, Timeline, ZForm } from "@/components/app";
import { Button } from "@/components/ui/button";
import { type AIReview, type AISummary, api, type Feedback, type SessionDetail } from "@/lib/api";
import { useRole } from "@/lib/auth";
import { tr, Tx, useLocale } from "@/lib/i18n";
import { dateTime, label } from "@/lib/format";
import { useAction, useGet, useList } from "@/lib/hooks";

const feedbackSchema = z.object({
  kind: z.enum(["feedback", "clarification_request"]),
  nursing_action: z.string(),
  text: requiredText("Feedback"),
});

function ReviewCard({ review, onRequest }: { review: AIReview | undefined; onRequest: () => void }) {
  const action = useAction();
  const request = (
    <Button variant="outline" size="sm" disabled={action.pending} onClick={async () => (await action.run(async () => onRequest())) && undefined}>
      <Tx k="Request reanalysis" />
    </Button>
  );
  if (!review) {
    return (
      <Section title="AI documentation review" action={request}>
        <p className="text-sm text-slate-500"><Tx k="No review has been generated for this session yet." /></p>
      </Section>
    );
  }
  const passages = new Map(review.protocol_passages.map((p) => [p.id, p]));
  return (
    <Section title="AI documentation review" description={`${tr("Generated")} ${dateTime(review.created_at)}`} action={request}>
      <div className="space-y-3 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <Status value={review.status} />
          {review.model_name && <span className="text-slate-500">{tr("Model:")} {review.model_name}</span>}
        </div>
        {review.status === "ai_unavailable" && (
          <p role="alert" className="rounded border border-red-200 bg-red-50 px-3 py-2 text-red-900">
            {tr("AI analysis is unavailable for this review")} ({review.ai_error.map((e) => e.code).join(", ") || "—"}).
            <Tx k="The rule-based findings below are still valid, and you can review the session as usual." />
          </p>
        )}
        {review.output && (
          <>
            <AiLabel text={review.label} />
            <p>{review.output.summary}</p>
            {review.output.documentation_gaps.length > 0 && (
              <div>
                <h3 className="font-medium"><Tx k="Documentation gaps" /></h3>
                <ul className="list-disc space-y-1 ps-5">
                  {review.output.documentation_gaps.map((gap) => (
                    <li key={gap.finding_id}>
                      {gap.description}
                      {gap.protocol_reference_ids.map((ref) => {
                        const p = passages.get(ref);
                        return p ? (
                          <span key={ref} className="ml-1 text-slate-500">
                            [{p.title} v{p.protocol_version} — {p.section}
                            {p.is_synthetic ? `, ${tr("synthetic demo policy")}` : ""}]
                          </span>
                        ) : null;
                      })}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {review.output.questions_for_doctor.length > 0 && (
              <div>
                <h3 className="font-medium"><Tx k="Questions for you" /></h3>
                <ul className="list-disc ps-5">
                  {review.output.questions_for_doctor.map((q) => (
                    <li key={q}>{q}</li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
        <div>
          <h3 className="font-medium">{tr("Rule-based documentation checks")} ({review.rule_findings.length})</h3>
          {review.rule_findings.length === 0 ? (
            <p className="text-slate-500"><Tx k="No gaps were found by the automated checks." /></p>
          ) : (
            <ul className="list-disc ps-5">
              {review.rule_findings.map((f) => (
                <li key={f.finding_id}>
                  <span className="font-medium">{label(f.check)}:</span> {f.description}
                </li>
              ))}
            </ul>
          )}
        </div>
        <ErrorNote message={action.error} />
      </div>
    </Section>
  );
}

function SummaryCard({ summary, sessionId, reload }: { summary: AISummary | undefined; sessionId: string; reload: () => void }) {
  const action = useAction();
  const act = (path: string, body?: unknown) => async () => (await action.run(() => api.post(path, body))) && reload();
  const generate = (
    <Button variant="outline" size="sm" disabled={action.pending} onClick={act("/ai/summaries/generate/", { session: sessionId })}>
      <Tx k="Generate new version" />
    </Button>
  );
  if (!summary) {
    return (
      <Section title="AI session summary" action={generate}>
        <p className="text-sm text-slate-500"><Tx k="No summary yet. One is generated when the session is completed." /></p>
        <ErrorNote message={action.error} />
      </Section>
    );
  }
  return (
    <Section title={`${tr("AI session summary")} (${tr("version")} ${summary.version})`} action={generate}>
      <div className="space-y-3 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <Status value={summary.status} />
          <Status value={summary.released ? "released" : "not_released"} />
        </div>
        {summary.status === "ai_unavailable" && (
          <p role="alert" className="rounded border border-red-200 bg-red-50 px-3 py-2 text-red-900">
            {tr("AI summary generation failed or was rejected by validation")} (
            {summary.ai_error.map((e) => e.code).join(", ") || "—"}). {tr("The session record is unaffected.")}
          </p>
        )}
        {summary.output && (
          <>
            <AiLabel text={summary.label} />
            <p>{summary.output.clinical_summary}</p>
            {(
              [
                ["Documented events", summary.output.documented_events],
                ["Nursing actions", summary.output.nursing_actions],
                ["Missing information", summary.output.missing_information],
              ] as const
            ).map(([title, items]) => (
              <div key={title}>
                <h3 className="font-medium">{tr(title)}</h3>
                {items.length === 0 ? (
                  <p className="text-slate-500"><Tx k="None." /></p>
                ) : (
                  <ul className="list-disc ps-5" dir="auto">
                    {items.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
            <div className="rounded border bg-slate-50 p-3">
              <h3 className="font-medium"><Tx k="Patient-friendly version (shown to the patient only after release)" /></h3>
              <p>{summary.output.patient_summary}</p>
            </div>
          </>
        )}
        <div className="flex flex-wrap gap-2">
          {summary.status === "unverified" && (
            <>
              <Button disabled={action.pending} onClick={act(`/ai/summaries/${summary.id}/verify/`)}>
                <Tx k="Verify summary" />
              </Button>
              <Button variant="outline" disabled={action.pending} onClick={act(`/ai/summaries/${summary.id}/reject/`)}>
                <Tx k="Reject" />
              </Button>
            </>
          )}
          {summary.status === "verified" && !summary.released && (
            <Button disabled={action.pending} onClick={act(`/ai/summaries/${summary.id}/release/`)}>
              <Tx k="Release to patient" />
            </Button>
          )}
        </div>
        <ErrorNote message={action.error} />
      </div>
    </Section>
  );
}

export default function DoctorSessionPage() {
  useLocale();
  const user = useRole("doctor");
  const { id } = useParams<{ id: string }>();
  const session = useGet<SessionDetail>(user ? `/sessions/${id}/` : null);
  const reviews = useList<AIReview>(user ? `/ai/reviews/?session=${id}` : null);
  const summaries = useList<AISummary>(user ? `/ai/summaries/?session=${id}` : null);
  const feedback = useList<Feedback>(user ? `/doctor/feedback/?session=${id}` : null);
  if (!user) return null;
  const review = reviews.data?.[0];
  return (
    <Shell title="Session review" back="/doctor/">
      <Load from={session}>
        {(s) => (
          <>
            <Section title={`${s.patient_name} · ${dateTime(s.started_at ?? s.scheduled_start)}`} action={<Status value={s.status} />}>
              <Measurements session={s} />
            </Section>
            <div className="grid gap-4 lg:grid-cols-2">
              <ReviewCard
                review={review}
                onRequest={async () => {
                  await api.post("/ai/reviews/request/", { session: id });
                  reviews.reload();
                }}
              />
              <SummaryCard summary={summaries.data?.[0]} sessionId={id} reload={summaries.reload} />
            </div>
            <Section title="Nursing actions and observations">
              <Timeline session={s} />
            </Section>
            <Section title="Your feedback" description="The nursing team is notified. Feedback cannot be edited after sending.">
              <ZForm
                schema={feedbackSchema}
                submitLabel="Send feedback"
                fields={[
                  {
                    name: "kind",
                    label: "Type",
                    type: "select",
                    options: [["feedback", "Feedback"], ["clarification_request", "Request clarification"]],
                  },
                  {
                    name: "nursing_action",
                    label: "About",
                    type: "select",
                    options: [["", "The whole session"], ...s.nursing_actions.map((a): [string, string] => [a.id, `${label(a.action_type)}: ${a.description.slice(0, 40)}`])],
                  },
                  { name: "text", label: "Feedback", type: "textarea" },
                ]}
                onSubmit={async (values) => {
                  await api.post("/doctor/feedback/", {
                    session: id,
                    kind: values.kind,
                    text: values.text,
                    nursing_action: values.nursing_action || null,
                    ai_review: review?.id ?? null,
                  });
                  feedback.reload();
                  reviews.reload();
                }}
              />
              <div className="mt-4">
                <Load from={feedback} empty="No feedback sent for this session.">
                  {(rows) => (
                    <ul className="divide-y text-sm">
                      {rows.map((f) => (
                        <li key={f.id} className="py-2">
                          <span className="font-medium">{label(f.kind)}</span> · {dateTime(f.created_at)}
                          <p dir="auto">{f.text}</p>
                        </li>
                      ))}
                    </ul>
                  )}
                </Load>
              </div>
            </Section>
          </>
        )}
      </Load>
    </Shell>
  );
}
