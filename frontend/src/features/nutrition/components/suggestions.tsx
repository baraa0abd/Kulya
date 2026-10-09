"use client";

import { ErrorNote, Load, Section, Status } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { Disclaimer, localName, NutrientTray } from "@/features/nutrition/components/common";
import { type Recommendation } from "@/features/nutrition/types";
import { api } from "@/lib/api";
import { useAction, useGet } from "@/lib/hooks";
import { tr, Tx } from "@/lib/i18n";
import { FlaskConical, Salad } from "lucide-react";
import Link from "next/link";

/** The patient's dashboard: ideas a clinician approved, by name, with a link to the details. */
export function ApprovedIdeas() {
  const ideas = useGet<Recommendation[]>("/nutrition/ai/suggestions/");
  const approved = ideas.data?.filter((idea) => idea.review_status === "approved") ?? [];
  if (!approved.length) return null;
  const names = [
    ...new Set(approved.map((i) => localName(i.recipe.localized_names, i.recipe.name))),
  ];
  return (
    <div className="mt-4 rounded-lg border border-ok/20 bg-ok-soft p-3 text-sm">
      <p className="font-semibold">
        <Tx k="Meal ideas approved by your care team" />
      </p>
      <p dir="auto">{names.slice(0, 5).join(" · ")}</p>
      <Link
        className="font-medium text-brand hover:underline"
        href="/patient/nutrition/suggestions/"
      >
        <Tx k="Open meal ideas" />
      </Link>
    </div>
  );
}

export function Suggestions({
  patient,
  canDecide,
  canDecideLabBased = canDecide,
  canRequest,
}: {
  patient: string;
  canDecide: boolean;
  /** Ideas ordered by a laboratory report quote its values, so only a doctor approves them. */
  canDecideLabBased?: boolean;
  canRequest: boolean;
}) {
  const path = `/nutrition/ai/suggestions/?patient=${patient}`;
  const ideas = useGet<Recommendation[]>(path);
  const act = useAction();
  const decide = async (id: string, approve: boolean) =>
    (await act.run(() => api.post(`/nutrition/recommendations/${id}/review/`, { approve }))) &&
    ideas.reload();
  return (
    <Section
      id="suggestions"
      icon={Salad}
      title="Meal ideas"
      description="Recipes are compared with the approved plan and the latest blood test by fixed rules. A personalized idea is shown to the patient only after a clinician approves it; an idea based on a blood test needs the doctor."
      action={
        canRequest && (
          <Button
            variant="outline"
            disabled={act.pending}
            onClick={async () =>
              (await act.run(() => api.post("/nutrition/ai/suggestions/", { patient }))) &&
              ideas.reload()
            }
          >
            <Tx k="Look for meal ideas" />
          </Button>
        )
      }
    >
      <div className="space-y-3">
        <Disclaimer />
        <ErrorNote message={act.error} />
        <Load from={ideas} empty="No meal ideas to show yet.">
          {(rows) => (
            <ul className="grid gap-3 lg:grid-cols-2">
              {rows.map((idea) => (
                <li key={idea.id} className="space-y-2 rounded-lg border border-line p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-semibold" dir="auto">
                      {localName(idea.recipe.localized_names, idea.recipe.name)}
                    </h3>
                    <Status value={idea.category} />
                    {canDecide && <Status value={idea.review_status} />}
                  </div>
                  <p className="micro flex flex-wrap items-center gap-1 text-ink-3">
                    {idea.lab_based && <FlaskConical className="size-3" aria-hidden />}
                    {idea.lab_based
                      ? tr("Based on the latest blood test")
                      : idea.personalized
                        ? tr("Compared with the approved plan")
                        : tr("General idea, not personalized")}
                    {idea.reviewed_by_name && idea.review_status === "approved"
                      ? ` · ${tr("approved by")} ${tr(idea.reviewed_by_name)}`
                      : ""}
                  </p>
                  <p className="text-sm leading-6" dir="auto">
                    {tr(idea.reasoning_summary)}
                  </p>
                  <NutrientTray values={idea.nutrient_estimates} dense />
                  <details className="text-sm">
                    <summary className="cursor-pointer font-medium text-brand">
                      {tr("How to prepare")}
                    </summary>
                    <ol className="mt-1 list-decimal space-y-1 ps-5" dir="auto">
                      {idea.recipe.preparation_method.map((step) => (
                        <li key={step}>{tr(step ?? "")}</li>
                      ))}
                    </ol>
                  </details>
                  <ul className="list-disc ps-5 text-xs text-ink-3">
                    {idea.limitations.map((note) => (
                      <li key={note}>{tr(note)}</li>
                    ))}
                  </ul>
                  {canDecide &&
                    idea.review_status === "pending" &&
                    idea.lab_based &&
                    !canDecideLabBased && (
                      <p className="text-sm text-ink-3">
                        <Tx k="Waiting for the doctor's approval." />
                      </p>
                    )}
                  {(idea.lab_based ? canDecideLabBased : canDecide) &&
                    idea.review_status === "pending" && (
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          disabled={act.pending}
                          onClick={() => decide(idea.id, true)}
                        >
                          <Tx k="Approve" />
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={act.pending}
                          onClick={() => decide(idea.id, false)}
                        >
                          <Tx k="Reject" />
                        </Button>
                      </div>
                    )}
                </li>
              ))}
            </ul>
          )}
        </Load>
      </div>
    </Section>
  );
}
