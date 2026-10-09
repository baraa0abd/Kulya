"use client";

import { ErrorNote } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useAction } from "@/lib/hooks";
import { tr, useLocale } from "@/lib/i18n";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMemo } from "react";
import { type FieldValues, useForm } from "react-hook-form";
import { type z } from "zod";
export interface FieldSpec {
  name: string;
  label: string;
  type?: "text" | "password" | "number" | "textarea" | "select" | "datetime-local" | "date";
  options?: [value: string, text: string][];
  hint?: string;
}

export function ZForm<S extends z.ZodType>({
  schema,
  fields,
  submitLabel,
  onSubmit,
  defaults,
}: {
  schema: S;
  fields: FieldSpec[];
  submitLabel: string;
  onSubmit: (values: z.output<S>) => Promise<unknown>;
  defaults?: Record<string, string>;
}) {
  const initial = useMemo(
    () =>
      Object.fromEntries(
        fields.map((f) => [f.name, defaults?.[f.name] ?? f.options?.[0]?.[0] ?? ""]),
      ),
    [fields, defaults],
  );
  const form = useForm<FieldValues>({
    resolver: zodResolver(schema as never) as never,
    defaultValues: initial,
  });
  const action = useAction();
  useLocale();
  const submit = form.handleSubmit(async (values) => {
    if (await action.run(() => onSubmit(values as z.output<S>))) form.reset(initial);
  });
  const control = "control w-full px-3";
  return (
    <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2" noValidate>
      {fields.map((field) => {
        const id = `${submitLabel}-${field.name}`.replaceAll(" ", "-");
        const error = form.formState.errors[field.name]?.message;
        const wide = field.type === "textarea" ? "sm:col-span-2" : "";
        return (
          <div key={field.name} className={`space-y-1 ${wide}`}>
            <Label htmlFor={id}>{tr(field.label)}</Label>
            {field.type === "textarea" ? (
              <Textarea id={id} rows={3} dir="auto" {...form.register(field.name)} />
            ) : field.type === "select" ? (
              <select id={id} className={control} {...form.register(field.name)}>
                {field.options?.map(([value, text]) => (
                  <option key={value} value={value}>
                    {tr(text)}
                  </option>
                ))}
              </select>
            ) : (
              <Input
                id={id}
                type={field.type === "number" ? "text" : (field.type ?? "text")}
                inputMode={field.type === "number" ? "decimal" : undefined}
                {...form.register(field.name)}
              />
            )}
            {field.hint && <p className="text-xs text-ink-3">{tr(field.hint)}</p>}
            {typeof error === "string" && (
              <p role="alert" className="text-xs text-bad">
                {tr(error)}
              </p>
            )}
          </div>
        );
      })}
      <div className="flex items-center gap-3 sm:col-span-2">
        <Button type="submit" disabled={action.pending}>
          {action.pending ? tr("Saving…") : tr(submitLabel)}
        </Button>
        <ErrorNote message={action.error} />
      </div>
    </form>
  );
}
