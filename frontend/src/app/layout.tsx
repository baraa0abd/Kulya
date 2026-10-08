import type { Metadata } from "next";
import { Geist } from "next/font/google";
import { Suspense } from "react";

import { AuthProvider } from "@/lib/auth";

import "./globals.css";

const geist = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Dialysis Copilot",
  description: "Dialysis documentation review and session summaries. Synthetic demonstration data only.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geist.variable} h-full antialiased`}>
      <body className="min-h-full font-sans">
        <AuthProvider>
          <Suspense fallback={<p className="p-6 text-sm text-slate-500">Loading…</p>}>{children}</Suspense>
        </AuthProvider>
      </body>
    </html>
  );
}
