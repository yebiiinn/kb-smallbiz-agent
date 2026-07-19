"use client";

import { useEffect, useState } from "react";

import { ChatPanel } from "@/components/chat/ChatPanel";
import { MarketInsightCard } from "@/components/dashboard/MarketInsightCard";
import { ProductRecommendList } from "@/components/recommendation/ProductRecommendList";
import type { BusinessContext } from "@/types/business";
import type { ChatResponse, MarketInsight, RecommendationItem } from "@/types/market";

const DEFAULT_CONTEXT: BusinessContext = {
  region: "서울 강남구",
  industry: "카페",
  stage: "startup",
};

export default function AgentPage() {
  const [context, setContext] = useState<BusinessContext>(DEFAULT_CONTEXT);
  const [insights, setInsights] = useState<MarketInsight | null>(null);
  const [recommendations, setRecommendations] = useState<RecommendationItem[]>([]);

  useEffect(() => {
    const saved = sessionStorage.getItem("businessContext");
    if (saved) {
      setContext(JSON.parse(saved) as BusinessContext);
    }
  }, []);

  function handleResponse(response: ChatResponse) {
    setInsights(response.insights);
    setRecommendations(response.recommendations);
  }

  const stageLabel = { startup: "창업", operation: "운영", expansion: "확장" }[context.stage];

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="mb-6 flex flex-wrap items-center gap-2 text-sm">
        <span className="rounded-full bg-amber-100 px-3 py-1 font-medium text-amber-700">
          {context.region}
        </span>
        <span className="rounded-full bg-zinc-100 px-3 py-1 text-zinc-600">{context.industry}</span>
        <span className="rounded-full bg-zinc-100 px-3 py-1 text-zinc-600">{stageLabel}</span>
      </div>

      <div className="grid h-[calc(100vh-220px)] gap-6 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <ChatPanel context={context} onResponse={handleResponse} />
        </div>
        <div className="space-y-4 overflow-y-auto lg:col-span-2">
          <MarketInsightCard insights={insights} />
          <ProductRecommendList items={recommendations} />
        </div>
      </div>
    </div>
  );
}
