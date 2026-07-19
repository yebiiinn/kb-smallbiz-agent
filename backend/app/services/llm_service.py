from openai import OpenAI

from app.config import settings
from app.schemas.chat import ChatRequest, ChatResponse, MarketInsight, RecommendationItem
from app.services.market_service import (
    get_market_insights,
    get_policy_funds,
    get_product_recommendations,
)


def _build_mock_response(request: ChatRequest) -> ChatResponse:
    ctx = request.context
    region = ctx.region or "서울 강남구"
    industry = ctx.industry or "카페"
    stage = ctx.stage

    insights_data = get_market_insights(region, industry)
    policies = get_policy_funds(stage, region)
    products = get_product_recommendations(region, industry, stage)

    policy_recs = [
        RecommendationItem(
            type="policy_fund",
            name=p.name,
            reason=p.description,
            link=p.link,
        )
        for p in policies.items[:2]
    ]

    answer = (
        f"{region} {industry} ({stage.value}) 기준으로 분석했습니다.\n\n"
        f"📊 상권: {insights_data.market_summary}\n\n"
        f"💰 추천 정책자금 {len(policy_recs)}건, 금융상품 {len(products)}건을 확인했습니다. "
        f"자세한 내용은 오른쪽 패널을 참고해 주세요."
    )

    return ChatResponse(
        answer=answer,
        insights=MarketInsight(
            market_summary=insights_data.market_summary,
            economic_indicator=insights_data.economic_indicator,
            consumption_trend=insights_data.consumption_trend,
        ),
        recommendations=policy_recs + products,
        follow_up_questions=[
            "예상 창업/운영 자본금은 얼마인가요?",
            "대출 상환 기간은 어떻게 생각하고 계신가요?",
        ],
    )


async def run_agent_chat(request: ChatRequest) -> ChatResponse:
    if not settings.openai_api_key:
        return _build_mock_response(request)

    ctx = request.context
    insights_data = get_market_insights(ctx.region, ctx.industry)
    policies = get_policy_funds(ctx.stage, ctx.region)
    products = get_product_recommendations(ctx.region, ctx.industry, ctx.stage)

    context_block = f"""
[사업자 정보]
- 지역: {ctx.region or '미입력'}
- 업종: {ctx.industry or '미입력'}
- 단계: {ctx.stage.value}
- 매출: {ctx.revenue or '미입력'}

[시장 데이터]
- 상권: {insights_data.market_summary}
- 경기: {insights_data.economic_indicator}
- 소비: {insights_data.consumption_trend}

[정책자금 후보]
{chr(10).join(f"- {p.name}: {p.description}" for p in policies.items[:3])}

[금융상품 후보]
{chr(10).join(f"- {p.name}: {p.reason}" for p in products[:3])}
"""

    client = OpenAI(api_key=settings.openai_api_key)
    completion = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "당신은 소상공인 금융 지원 AI 에이전트입니다. "
                    "상권·경기·정책자금·금융상품 정보를 바탕으로 "
                    "창업/운영 의사결정을 돕는 답변을 한국어로 제공하세요. "
                    "구체적이고 실용적으로 답변하세요."
                ),
            },
            {"role": "user", "content": f"{context_block}\n\n질문: {request.message}"},
        ],
    )

    answer = completion.choices[0].message.content or _build_mock_response(request).answer
    mock = _build_mock_response(request)
    return ChatResponse(
        answer=answer,
        insights=mock.insights,
        recommendations=mock.recommendations,
        follow_up_questions=mock.follow_up_questions,
    )
