import type { Metadata } from "next";
import { Inter, Noto_Sans_Arabic } from "next/font/google";

import { AuthProvider } from "@/lib/auth";
import { LocaleBoot } from "@/lib/i18n";

import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });
const arabic = Noto_Sans_Arabic({ variable: "--font-arabic", subsets: ["arabic"] });

export const metadata: Metadata = {
  title: "كُلية",
  description: "مراجعة توثيق الغسيل وملخصات الجلسات. بيانات تجريبية مصطنعة فقط.",
};

// Arabic and right-to-left by default; LocaleBoot applies a saved English preference after load.
// No Suspense boundary around the pages: the whole tree must hydrate in one pass, before
// LocaleBoot switches language, or the server-rendered Arabic would not match.
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ar" dir="rtl" className={`${inter.variable} ${arabic.variable} h-full antialiased`}>
      <body className="min-h-full font-sans">
        <LocaleBoot />
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
