import type { BusinessContext } from "@/types/business";
import type {
  ChatResponse,
  MarketInsightResponse,
  PolicyFundItem,
  RecommendationItem,
} from "@/types/market";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function postChat(
  message: string,
  context: BusinessContext,
  sessionId?: string,
): Promise<ChatResponse> {
  return fetchJson<ChatResponse>("/api/v1/agent/chat", {
    method: "POST",
    body: JSON.stringify({ message, context }),
    headers: sessionId ? { "X-Session-Id": sessionId } : {},
  });
}

export async function getMarketInsights(
  region: string,
  industry: string,
): Promise<MarketInsightResponse> {
  const params = new URLSearchParams({ region, industry });
  return fetchJson<MarketInsightResponse>(`/api/v1/market/insights?${params}`);
}

export async function getPolicyFunds(
  stage?: string,
): Promise<{ items: PolicyFundItem[] }> {
  const params = stage ? `?stage=${stage}` : "";
  return fetchJson<{ items: PolicyFundItem[] }>(`/api/v1/policy/funds${params}`);
}

export async function postRecommendProducts(
  region: string,
  industry: string,
  stage: string,
): Promise<{ items: RecommendationItem[] }> {
  return fetchJson<{ items: RecommendationItem[] }>("/api/v1/recommend/products", {
    method: "POST",
    body: JSON.stringify({ region, industry, stage }),
  });
}
