import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "KB 소상공인 금융 지원 에이전트",
  description: "상권·경기·정책자금·금융상품을 종합 분석하는 KB AI 에이전트",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col bg-[#0A0F1E] text-white">
        <header
          className="sticky top-0 z-50 border-b"
          style={{
            background: "rgba(10, 15, 30, 0.85)",
            backdropFilter: "blur(20px)",
            borderColor: "rgba(255, 255, 255, 0.08)",
          }}
        >
          <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">
            <Link href="/" className="flex items-center gap-2.5">
              <div
                className="flex h-8 w-8 items-center justify-center rounded-lg text-xs font-black text-black shadow-lg"
                style={{
                  background: "linear-gradient(135deg, #FFB81C, #FF8C00)",
                  boxShadow: "0 2px 12px rgba(255,184,28,0.4)",
                }}
              >
                KB
              </div>
              <span className="text-sm font-semibold text-white">
                소상공인 금융 지원 에이전트
              </span>
            </Link>

            <nav className="flex items-center gap-1">
              <Link
                href="/onboarding"
                className="rounded-lg px-3 py-1.5 text-xs font-medium transition-colors"
                style={{ color: "rgba(255,255,255,0.55)" }}
              >
                정보 입력
              </Link>
              <Link
                href="/agent"
                className="ml-1 rounded-lg px-4 py-1.5 text-xs font-bold text-black transition-all hover:opacity-90"
                style={{
                  background: "linear-gradient(135deg, #FFB81C, #FF8C00)",
                  boxShadow: "0 2px 10px rgba(255,184,28,0.35)",
                }}
              >
                AI 에이전트 →
              </Link>
            </nav>
          </div>
        </header>

        <main className="flex-1">{children}</main>
      </body>
    </html>
  );
}
