import type { MarketInsight } from "@/types/market";

interface MarketInsightCardProps {
  insights: MarketInsight | null;
}

export function MarketInsightCard({ insights }: MarketInsightCardProps) {
  if (!insights) {
    return (
      <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
        <h3 className="mb-2 text-sm font-semibold text-zinc-900">📊 시장 인사이트</h3>
        <p className="text-sm text-zinc-400">대화를 시작하면 상권·경기·소비 분석이 표시됩니다.</p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
      <h3 className="mb-4 text-sm font-semibold text-zinc-900">📊 시장 인사이트</h3>
      <div className="space-y-3 text-sm">
        <div>
          <p className="mb-1 font-medium text-amber-600">상권 분석</p>
          <p className="leading-relaxed text-zinc-600">{insights.market_summary}</p>
        </div>
        <div>
          <p className="mb-1 font-medium text-amber-600">경기 지표</p>
          <p className="leading-relaxed text-zinc-600">{insights.economic_indicator}</p>
        </div>
        <div>
          <p className="mb-1 font-medium text-amber-600">소비 트렌드</p>
          <p className="leading-relaxed text-zinc-600">{insights.consumption_trend}</p>
        </div>
      </div>
    </div>
  );
}
