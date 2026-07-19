from pydantic import BaseModel, Field

from app.schemas.chat import BusinessStage, RecommendationItem


class MarketInsightResponse(BaseModel):
    region: str
    industry: str
    market_summary: str
    economic_indicator: str
    consumption_trend: str
    score: float = Field(ge=0, le=100, description="상권 활성도 점수")


class PolicyFundItem(BaseModel):
    id: str
    name: str
    description: str
    eligibility: str
    max_amount: str
    stage: BusinessStage
    link: str = ""


class PolicyFundsResponse(BaseModel):
    items: list[PolicyFundItem]


class ProductRecommendRequest(BaseModel):
    region: str
    industry: str
    stage: BusinessStage
    purpose: str = ""


class ProductRecommendResponse(BaseModel):
    items: list[RecommendationItem]
