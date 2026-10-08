"use client";

import { useRouter } from "next/navigation";
import { z } from "zod";

import { LanguageToggle, requiredText, ZForm } from "@/components/app";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { HOME, useAuth } from "@/lib/auth";
import { Tx, useLocale } from "@/lib/i18n";

const schema = z.object({ username: requiredText("Username"), password: requiredText("Password") });

export default function LoginPage() {
  useLocale();
  const { login } = useAuth();
  const router = useRouter();
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>
            <h1 className="text-2xl text-teal-800"><Tx k="Kulya" /></h1>
          </CardTitle>
          <CardDescription>
            <Tx k="Sign in. This demonstration runs on synthetic data only and is not a medical device." />
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ZForm
            schema={schema}
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
