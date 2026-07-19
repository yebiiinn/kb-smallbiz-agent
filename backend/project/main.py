"""FastAPI 진입점."""

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from project.config import settings
from project.graph import run_graph
from project.schemas import (
    BusinessStage,
    ChatRequest,
    ChatResponse,
    MarketInsight,
    MarketInsightResponse,
    PolicyFundsResponse,
    ProductRecommendRequest,
    ProductRecommendResponse,
)
from project.tools import bizinfo_api, finlife_api, sangkwon_api

app = FastAPI(
    title="소상공인 금융 지원 에이전트 API",
    description="KB AI Challenge — LangGraph 멀티 에이전트 API",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/v1/agent/chat", response_model=ChatResponse)
async def agent_chat(request: ChatRequest) -> ChatResponse:
    result = await run_graph(request.message, request.context)
    insights_data = result.get("insights") or {}

    return ChatResponse(
        answer=result.get("final_answer", ""),
        insights=MarketInsight(
            market_summary=insights_data.get("market_summary", ""),
            economic_indicator=insights_data.get("economic_indicator", ""),
            consumption_trend=insights_data.get("consumption_trend", ""),
        ),
        recommendations=result.get("recommendations", []),
        follow_up_questions=result.get("follow_up_questions", []),
    )


@app.get("/api/v1/market/insights", response_model=MarketInsightResponse)
async def market_insights(
    region: str = Query(default="서울 강남구"),
    industry: str = Query(default="카페"),
):
    data = sangkwon_api.fetch_commercial_district(region=region, industry=industry)
    return MarketInsightResponse(
        region=region,
        industry=industry,
        market_summary=data.get("summary", ""),
        economic_indicator="경기지표 API 연동 예정",
        consumption_trend="소비 트렌드 API 연동 예정",
        score=float(data.get("score", 0)),
    )


@app.get("/api/v1/policy/funds", response_model=PolicyFundsResponse)
async def policy_funds(
    stage: BusinessStage | None = Query(default=None),
    region: str = Query(default=""),
):
    from project.schemas import PolicyFundItem

    data = bizinfo_api.search_support_programs(region=region, stage=stage.value if stage else "")
    items = [
        PolicyFundItem(
            id=f"policy-{i}",
            name=item["name"],
            description=item.get("description", ""),
            eligibility="",
            max_amount=item.get("max_amount", ""),
            stage=stage or BusinessStage.STARTUP,
            link=item.get("link", ""),
        )
        for i, item in enumerate(data.get("items", []))
    ]
    return PolicyFundsResponse(items=items)


@app.post("/api/v1/recommend/products", response_model=ProductRecommendResponse)
async def recommend_products(request: ProductRecommendRequest) -> ProductRecommendResponse:
    from project.schemas import RecommendationItem

    data = finlife_api.search_financial_products(
        region=request.region,
        industry=request.industry,
        stage=request.stage.value,
    )
    items = [
        RecommendationItem(
            type=item.get("type", "financial_product"),
            name=item["name"],
            reason=item.get("reason", ""),
            link=item.get("link", ""),
        )
        for item in data.get("items", [])
    ]
    return ProductRecommendResponse(items=items)
