"use client";

import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { dateOnly, withUnit } from "@/lib/format";
import { tr, Tx, useLocale } from "@/lib/i18n";
import { type LabReport } from "@/lib/types";
import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
/** Laboratory values over time, one analyte at a time, with unit and reference range. */
export function LabTrends({ reports }: { reports: LabReport[] }) {
  const analytes = useMemo(
    () => [...new Set(reports.flatMap((r) => r.results.map((x) => x.analyte)))].sort(),
    [reports],
  );
  const [chosen, setChosen] = useState<string | null>(null);
  useLocale();
  const analyte = chosen ?? analytes[0];
  const points = reports
    .flatMap((r) =>
      r.results.filter((x) => x.analyte === analyte).map((x) => ({ report: r, result: x })),
    )
    .sort((a, b) => a.report.collected_at.localeCompare(b.report.collected_at));
  if (points.length === 0)
    return (
      <p className="text-sm text-ink-3">
        <Tx k="No laboratory results available." />
      </p>
    );
  const { unit, reference_low: low, reference_high: high } = points[0].result;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Label htmlFor="analyte">
          <Tx k="Analyte" />
        </Label>
        <select
          id="analyte"
          className="control px-2"
          value={analyte}
          onChange={(e) => setChosen(e.target.value)}
        >
          {analytes.map((name) => (
            <option key={name} value={name}>
              {tr(name)}
            </option>
          ))}
        </select>
        <span className="text-ink-3">
          {tr("Unit:")} {tr(unit)}
          {low && high
            ? ` · ${tr("Laboratory reference range")} ${Number(low)}–${Number(high)} ${tr(unit)}`
            : ""}
        </span>
      </div>
      <div
        className="h-56 w-full"
        dir="ltr"
        role="img"
        aria-label={`${tr(analyte)} ${tr("trend in")} ${tr(unit)}`}
      >
        <ResponsiveContainer>
          <LineChart
            data={points.map((p) => ({
              date: dateOnly(p.report.collected_at),
              value: Number(p.result.value),
            }))}
            margin={{ left: 0, right: 16, top: 8, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" fontSize={12} />
            <YAxis domain={["auto", "auto"]} fontSize={12} width={48} />
            <Tooltip formatter={(value) => [`${value} ${tr(unit)}`, tr(analyte)]} />
            <Line type="linear" dataKey="value" stroke="#176b87" strokeWidth={2} dot />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>
              <Tx k="Collected" />
            </TableHead>
            <TableHead>{tr(analyte)}</TableHead>
            <TableHead>
              <Tx k="Released to patient" />
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {points.map((p) => (
            <TableRow key={p.result.id}>
              <TableCell>{dateOnly(p.report.collected_at)}</TableCell>
              <TableCell>{withUnit(p.result.value, p.result.unit)}</TableCell>
              <TableCell>{tr(p.report.released_to_patient ? "Yes" : "No")}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
