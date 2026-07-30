export interface CrisisInsight {
  level: "normal" | "warning" | "critical";
  score: number;
  summary: string;
  recommended_actions: string[];
  growth_market_names?: string[];
}

export interface MarketInsight {
  market_summary: string;
  economic_indicator: string;
  consumption_trend: string;
  crisis?: CrisisInsight | null;
  sales_data_note?: string;
}

export interface MarketInsightResponse extends MarketInsight {
  region: string;
  industry: string;
  score: number;
}

export interface PolicyFundItem {
  id: string;
  name: string;
  description: string;
  eligibility: string;
  max_amount: string;
  stage: string;
  link: string;
}

export interface RecommendationItem {
  type: "policy_fund" | "financial_product";
  name: string;
  reason: string;
  link: string;
}

export interface ChatResponse {
  answer: string;
  insights: MarketInsight | null;
  recommendations: RecommendationItem[];
  follow_up_questions: string[];
  active_agents?: string[];
}
