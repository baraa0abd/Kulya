"use client";

import { Activity } from "lucide-react";
import { useRouter } from "next/navigation";

import { LanguageToggle } from "@/components/feedback";
import { ZForm } from "@/components/forms";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { HOME, useAuth } from "@/lib/auth";
import { DEMO } from "@/lib/format";
import { Tx, useLocale } from "@/lib/i18n";
import { loginSchema } from "@/lib/validation";

export default function LoginPage() {
  useLocale();
  const { login } = useAuth();
  const router = useRouter();
  return (
    <main className="flex min-h-screen items-center justify-center bg-canvas p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>
            <span className="mb-3 flex size-11 items-center justify-center rounded-lg bg-brand text-white">
              <Activity className="size-6" aria-hidden />
            </span>
            <h1 className="text-2xl font-semibold text-brand-strong">
              <Tx k="Kulya" />
            </h1>
          </CardTitle>
          <CardDescription>
            <Tx
              k={
                DEMO
                  ? "Sign in. This demonstration runs on synthetic data only and is not a medical device."
                  : "Sign in. Decision support only. Not a medical device."
              }
            />
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ZForm
            schema={loginSchema}
            submitLabel="Sign in"
            fields={[
              { name: "username", label: "Username" },
              { name: "password", label: "Password", type: "password" },
            ]}
            onSubmit={async ({ username, password }) => {
              const user = await login(username, password);
              router.replace(HOME[user.role]);
            }}
          />
          <div className="mt-3 text-end">
            <LanguageToggle />
          </div>
        </CardContent>
      </Card>
    </main>
  );
}
