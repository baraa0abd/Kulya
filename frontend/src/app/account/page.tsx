"use client";

import { KeyRound } from "lucide-react";
import { useState } from "react";
import { z } from "zod";

import { Section } from "@/components/feedback";
import { ZForm } from "@/components/forms";
import { Shell } from "@/components/layout/shell";
import { api } from "@/lib/api";
import { HOME, useAuth } from "@/lib/auth";
import { Tx, useLocale } from "@/lib/i18n";

const schema = z
  .object({
    current_password: z.string().min(1, "Password is required."),
    new_password: z.string().min(10, "Use at least 10 characters."),
    repeat: z.string(),
  })
  .refine((v) => v.new_password === v.repeat, {
    path: ["repeat"],
    message: "The two passwords do not match.",
  });

export default function AccountPage() {
  useLocale();
  const { user } = useAuth();
  const [done, setDone] = useState(false);
  if (!user) return null;
  return (
    <Shell title="My account" back={HOME[user.role]}>
      <Section
        icon={KeyRound}
        title="Change password"
        description="Choose a password only you know. Do not share your account."
      >
        <ZForm
          schema={schema}
          submitLabel="Change password"
          fields={[
            { name: "current_password", label: "Current password", type: "password" },
            { name: "new_password", label: "New password", type: "password" },
            { name: "repeat", label: "Repeat the new password", type: "password" },
          ]}
          onSubmit={async ({ current_password, new_password }) => {
            setDone(false);
            await api.post("/auth/password/", { current_password, new_password });
            setDone(true);
          }}
        />
        {done && (
          <p role="status" className="mt-3 text-sm text-ok">
            <Tx k="Password changed." />
          </p>
        )}
      </Section>
    </Shell>
  );
}
