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
  title: "소상공인 금융 지원 에이전트 | KB AI Challenge",
  description: "상권·경기·정책자금·금융상품을 종합 분석하는 AI 에이전트",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col bg-zinc-50 text-zinc-900">
        <header className="border-b border-zinc-200 bg-white">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
            <Link href="/" className="text-lg font-bold text-amber-600">
              소상공인 금융 지원 에이전트
            </Link>
            <nav className="flex gap-4 text-sm">
              <Link href="/onboarding" className="text-zinc-600 hover:text-amber-600">
                온보딩
              </Link>
              <Link href="/agent" className="text-zinc-600 hover:text-amber-600">
                AI 에이전트
              </Link>
            </nav>
          </div>
        </header>
        <main className="flex-1">{children}</main>
      </body>
    </html>
  );
}
