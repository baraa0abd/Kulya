"use client";

import { ErrorNote } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useAction } from "@/lib/hooks";
import { tr, Tx } from "@/lib/i18n";
import { Plus } from "lucide-react";
import { useState } from "react";

interface Row {
  analyte: string;
  value: string;
  unit: string;
  reference_low: string;
  reference_high: string;
}

// Names only, as a typing shortcut. Units and reference ranges differ between laboratories, so
// they are always copied from the printed report and never pre-filled.
const COMMON = ["Potassium", "Phosphate", "Urea", "Albumin", "Hemoglobin"];
const blank = (analyte = ""): Row => ({
  analyte,
  value: "",
  unit: "",
  reference_low: "",
  reference_high: "",
});
const COLUMNS: [keyof Row, string][] = [
  ["analyte", "Analyte"],
  ["value", "Value"],
  ["unit", "Unit"],
  ["reference_low", "Reference low"],
  ["reference_high", "Reference high"],
];

/** Enter one laboratory report. It stays hidden from the patient until a doctor releases it. */
export function LabEntry({ patient, onSaved }: { patient: string; onSaved: () => void }) {
  const [collected, setCollected] = useState("");
  const [source, setSource] = useState("");
  const [rows, setRows] = useState<Row[]>(() => COMMON.map(blank));
  const [problem, setProblem] = useState<string | null>(null);
  const save = useAction();
  const filled = rows.filter((row) => row.value.trim());

  const submit = async () => {
    setProblem(null);
    if (!collected || !source.trim())
      return setProblem("Enter the collection time and laboratory.");
    if (new Date(collected) > new Date())
      return setProblem("The collection time is in the future.");
    if (!filled.length) return setProblem("Enter at least one result.");
    if (filled.some((row) => !row.analyte.trim() || !row.unit.trim() || isNaN(Number(row.value))))
      return setProblem("Each result needs a name, a numeric value and a unit.");
    const at = new Date(collected).toISOString();
    const saved = await save.run(() =>
      api.post("/labs/", {
        patient,
        collected_at: at,
        reported_at: at,
        source: source.trim(),
        results: filled.map((row) => ({
          analyte: row.analyte.trim(),
          value: row.value.trim(),
          unit: row.unit.trim(),
          reference_low: row.reference_low.trim() || null,
          reference_high: row.reference_high.trim() || null,
        })),
      }),
    );
    if (!saved) return;
    setRows(COMMON.map(blank));
    setCollected("");
    onSaved();
  };

  return (
    <details className="mt-4 rounded-lg border border-line p-3 text-sm">
      <summary className="cursor-pointer font-medium text-brand">
        <Tx k="Enter a laboratory report" />
      </summary>
      <p className="my-2 text-ink-3">
        <Tx k="Copy units and reference ranges exactly as printed on the laboratory report." />
      </p>
      <div className="mb-3 grid gap-3 sm:grid-cols-2">
        <label>
          {tr("Collected")}
          <Input
            type="datetime-local"
            value={collected}
            onChange={(e) => setCollected(e.target.value)}
          />
        </label>
        <label>
          {tr("Laboratory")}
          <Input value={source} dir="auto" onChange={(e) => setSource(e.target.value)} />
        </label>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[36rem] border-separate border-spacing-1">
          <thead>
            <tr className="text-start text-xs text-ink-3">
              {COLUMNS.map(([, name]) => (
                <th key={name} scope="col" className="text-start font-medium">
                  {tr(name)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={index}>
                {COLUMNS.map(([field, name]) => (
                  <td key={field}>
                    <Input
                      aria-label={`${tr(name)} ${index + 1}`}
                      inputMode={field === "analyte" || field === "unit" ? undefined : "decimal"}
                      dir={field === "analyte" ? "auto" : "ltr"}
                      value={row[field]}
                      onChange={(e) =>
                        setRows((all) =>
                          all.map((r, i) => (i === index ? { ...r, [field]: e.target.value } : r)),
                        )
                      }
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <Button variant="outline" size="sm" onClick={() => setRows((all) => [...all, blank()])}>
          <Plus className="size-4" aria-hidden />
          <Tx k="Add a result" />
        </Button>
        <Button size="sm" disabled={save.pending} onClick={submit}>
          <Tx k="Save laboratory report" />
        </Button>
        <ErrorNote message={problem ?? save.error} />
      </div>
    </details>
  );
}
