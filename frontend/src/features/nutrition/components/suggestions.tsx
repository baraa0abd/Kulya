"use client";

import { ErrorNote, Load, Section, Status } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { Disclaimer, localName, NutrientTray } from "@/features/nutrition/components/common";
import { type Recommendation } from "@/features/nutrition/types";
import { api } from "@/lib/api";
import { useAction, useGet } from "@/lib/hooks";
import { tr, Tx } from "@/lib/i18n";
import { Salad } from "lucide-react";
export function Suggestions({
  patient,
  canDecide,
  canRequest,
}: {
  patient: string;
  canDecide: boolean;
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
      description="Recipes are compared with the approved plan by fixed rules. A personalized idea is shown to the patient only after a doctor or dietitian approves it."
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
                  <p className="micro text-ink-3">
                    {idea.personalized
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
                  {canDecide && idea.review_status === "pending" && (
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
