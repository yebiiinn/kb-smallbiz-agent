from enum import Enum

from pydantic import BaseModel, Field


class BusinessStage(str, Enum):
    STARTUP = "startup"
    OPERATION = "operation"
    EXPANSION = "expansion"


class BusinessContext(BaseModel):
    region: str = ""
    industry: str = ""
    stage: BusinessStage = BusinessStage.STARTUP
    revenue: int | None = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    context: BusinessContext = Field(default_factory=BusinessContext)


class MarketInsight(BaseModel):
    market_summary: str
    economic_indicator: str
    consumption_trend: str


class RecommendationItem(BaseModel):
    type: str  # policy_fund | financial_product
    name: str
    reason: str
    link: str = ""


class ChatResponse(BaseModel):
    answer: str
    insights: MarketInsight | None = None
    recommendations: list[RecommendationItem] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
