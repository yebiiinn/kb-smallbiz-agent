import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { MarketInsight } from "@/types/market";

interface MarketInsightCardProps {
  insights: MarketInsight | null;
  loading?: boolean;
}

const INSIGHT_ITEMS = [
  {
    key: "market_summary" as const,
    label: "상권 분석",
    icon: "🏪",
    accent: "#3B82F6",
    glow: "rgba(59,130,246,0.12)",
    border: "rgba(59,130,246,0.2)",
  },
  {
    key: "economic_indicator" as const,
    label: "경기 지표",
    icon: "📈",
    accent: "#10B981",
    glow: "rgba(16,185,129,0.12)",
    border: "rgba(16,185,129,0.2)",
  },
  {
    key: "consumption_trend" as const,
    label: "소비 트렌드",
    icon: "🛒",
    accent: "#A855F7",
    glow: "rgba(168,85,247,0.12)",
    border: "rgba(168,85,247,0.2)",
  },
];

const markdownComponents = {
  p: ({ children }: { children?: React.ReactNode }) => (
    <p className="mb-1.5 last:mb-0">{children}</p>
  ),
  ul: ({ children }: { children?: React.ReactNode }) => (
    <ul className="space-y-1.5">{children}</ul>
  ),
  li: ({ children }: { children?: React.ReactNode }) => (
    <li className="leading-relaxed" style={{ color: "rgba(255,255,255,0.72)" }}>
      {children}
    </li>
  ),
  strong: ({ children }: { children?: React.ReactNode }) => (
    <strong className="font-semibold text-white">{children}</strong>
  ),
};

function SkeletonRow() {
  return (
    <div className="space-y-1.5">
      <div className="h-3 w-full animate-pulse rounded-md" style={{ background: "rgba(255,255,255,0.06)" }} />
      <div className="h-3 w-4/5 animate-pulse rounded-md" style={{ background: "rgba(255,255,255,0.06)" }} />
      <div className="h-3 w-3/5 animate-pulse rounded-md" style={{ background: "rgba(255,255,255,0.06)" }} />
    </div>
  );
}

export function MarketInsightCard({ insights, loading }: MarketInsightCardProps) {
  return (
    <div
      className="rounded-2xl p-5"
      style={{
        background: "rgba(255,255,255,0.04)",
        border: "1px solid rgba(255,255,255,0.1)",
        backdropFilter: "blur(20px)",
      }}
    >
      <div className="mb-4 flex items-center gap-2">
        <span className="text-base">📊</span>
        <h3 className="text-sm font-semibold text-white">시장 인사이트</h3>
        {loading && (
          <span className="ml-auto animate-pulse text-xs" style={{ color: "#FFB81C" }}>
            분석 중...
          </span>
        )}
      </div>

      {insights?.sales_data_note && (
        <div
          className="mb-4 rounded-xl px-3 py-2.5 text-xs leading-relaxed"
          style={{
            background: "rgba(255,184,28,0.08)",
            border: "1px solid rgba(255,184,28,0.25)",
            color: "rgba(255,255,255,0.75)",
          }}
        >
          ℹ️ {insights.sales_data_note}
        </div>
      )}

      {!insights && !loading && (
        <p className="text-sm" style={{ color: "rgba(255,255,255,0.3)" }}>
          대화를 시작하면 상권·경기·소비 분석이 여기에 표시됩니다.
        </p>
      )}

      {loading && !insights && (
        <div className="space-y-3">
          {INSIGHT_ITEMS.map((item) => (
            <div
              key={item.key}
              className="rounded-xl p-3"
              style={{ background: item.glow, border: `1px solid ${item.border}` }}
            >
              <div className="mb-2 flex items-center gap-1.5">
                <span className="text-sm">{item.icon}</span>
                <span className="text-xs font-semibold" style={{ color: item.accent }}>
                  {item.label}
                </span>
              </div>
              <SkeletonRow />
            </div>
          ))}
        </div>
      )}

      {insights && (
        <div className="space-y-3">
          {INSIGHT_ITEMS.map((item) => {
            const text = insights[item.key];
            if (!text) return null;
            return (
              <div
                key={item.key}
                className="rounded-xl p-3"
                style={{ background: item.glow, border: `1px solid ${item.border}` }}
              >
                <div className="mb-2 flex items-center gap-1.5">
                  <span className="text-sm">{item.icon}</span>
                  <span className="text-xs font-semibold" style={{ color: item.accent }}>
                    {item.label}
                  </span>
                </div>
                <div className="text-[13px] leading-relaxed">
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                    {text}
                  </ReactMarkdown>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
