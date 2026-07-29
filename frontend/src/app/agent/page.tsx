"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ChatPanel } from "@/components/chat/ChatPanel";
import { MarketInsightCard } from "@/components/dashboard/MarketInsightCard";
import { ProductRecommendList } from "@/components/recommendation/ProductRecommendList";
import type { BusinessContext } from "@/types/business";
import type { ChatResponse, MarketInsight, RecommendationItem } from "@/types/market";

const DEFAULT_CONTEXT: BusinessContext = {
  region: "",
  industry: "",
  stage: "startup",
  revenue: null,
};

const STAGE_LABEL: Record<string, string> = {
  startup: "창업 준비",
  operation: "운영 중",
  expansion: "확장 계획",
};

export default function AgentPage() {
  const [context, setContext] = useState<BusinessContext>(DEFAULT_CONTEXT);
  const [insights, setInsights] = useState<MarketInsight | null>(null);
  const [recommendations, setRecommendations] = useState<RecommendationItem[]>([]);
  const [sideLoading, setSideLoading] = useState(false);

  useEffect(() => {
    const saved = sessionStorage.getItem("businessContext");
    if (saved) setContext(JSON.parse(saved) as BusinessContext);
  }, []);

  function handleResponse(response: ChatResponse) {
    setSideLoading(false);
    setInsights(response.insights);
    setRecommendations(response.recommendations);
  }

  function handleLoadingStart() {
    setSideLoading(true);
  }

  return (
    <div
      className="min-h-screen px-6 py-5"
      style={{ background: "linear-gradient(160deg, #0A0F1E 0%, #111827 100%)" }}
    >
      <div className="mx-auto flex max-w-7xl flex-col gap-4">
        {/* Context bar */}
        <div className="flex flex-wrap items-center gap-2">
          {context.region ? (
            <>
              {[
                { icon: "📍", label: context.region },
                { icon: "🏪", label: context.industry },
                { icon: "🏢", label: STAGE_LABEL[context.stage] ?? context.stage, highlight: true },
                ...(context.revenue
                  ? [{ icon: "💵", label: `월 ${context.revenue.toLocaleString()}만원` }]
                  : []),
              ].map((tag) => (
                <span
                  key={tag.label}
                  className="flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium backdrop-blur-sm"
                  style={
                    tag.highlight
                      ? {
                          background: "rgba(255,184,28,0.12)",
                          borderColor: "rgba(255,184,28,0.35)",
                          color: "#FFB81C",
                        }
                      : {
                          background: "rgba(255,255,255,0.06)",
                          borderColor: "rgba(255,255,255,0.12)",
                          color: "rgba(255,255,255,0.7)",
                        }
                  }
                >
                  {tag.icon} {tag.label}
                </span>
              ))}
              <Link
                href="/onboarding"
                className="ml-1 text-xs transition-colors"
                style={{ color: "rgba(255,255,255,0.3)" }}
              >
                수정
              </Link>
            </>
          ) : (
            <div
              className="flex items-center gap-2 rounded-xl border px-4 py-2 text-sm backdrop-blur-sm"
              style={{
                background: "rgba(255,184,28,0.08)",
                borderColor: "rgba(255,184,28,0.25)",
                color: "#FFB81C",
              }}
            >
              <span>💡</span>
              <span>
                사업 정보를 입력하면 더 정확한 분석이 가능합니다.{" "}
                <Link href="/onboarding" className="font-bold underline-offset-2 hover:underline">
                  정보 입력하기 →
                </Link>
              </span>
            </div>
          )}
        </div>

        {/* Main layout */}
        <div className="grid h-[calc(100vh-140px)] gap-4 lg:grid-cols-5">
          <div className="lg:col-span-3">
            <ChatPanel
              context={context}
              onResponse={handleResponse}
              onLoadingStart={handleLoadingStart}
            />
          </div>
          <div className="flex flex-col gap-4 overflow-y-auto lg:col-span-2">
            <MarketInsightCard insights={insights} loading={sideLoading} />
            <ProductRecommendList items={recommendations} loading={sideLoading} />
          </div>
        </div>
      </div>
    </div>
  );
}
