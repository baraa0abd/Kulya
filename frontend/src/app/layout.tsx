import type { Metadata } from "next";
import { Geist, Noto_Sans_Arabic } from "next/font/google";
import { Suspense } from "react";

import { AuthProvider } from "@/lib/auth";
import { LocaleBoot } from "@/lib/i18n";

import "./globals.css";

const geist = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const arabic = Noto_Sans_Arabic({ variable: "--font-arabic", subsets: ["arabic"] });

export const metadata: Metadata = {
  title: "مساعد الغسيل الكلوي · Dialysis Copilot",
  description: "Dialysis documentation review and session summaries. Synthetic demonstration data only.",
};

// Arabic and right-to-left by default; LocaleBoot applies a saved English preference after load.
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ar" dir="rtl" className={`${geist.variable} ${arabic.variable} h-full antialiased`}>
      <body className="min-h-full" style={{ fontFamily: "var(--font-arabic), var(--font-geist-sans), sans-serif" }}>
        <LocaleBoot />
        <AuthProvider>
          <Suspense fallback={<p className="p-6 text-sm text-slate-500">…</p>}>{children}</Suspense>
        </AuthProvider>
      </body>
    </html>
  );
}
