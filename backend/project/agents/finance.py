"""정책자금·금융상품 에이전트 — 담당자 B.

API:
- 기업마당 지원사업 API
- 금융감독원 금융상품 비교 API (finlife)
"""

from project.state import AgentState
from project.schemas import RecommendationItem
from project.tools import bizinfo_api, finlife_api


def finance_node(state: AgentState) -> dict:
    ctx = state["context"]
    region = ctx.region or "서울"
    industry = ctx.industry or "카페"
    stage = ctx.stage.value

    policies = bizinfo_api.search_support_programs(region=region, stage=stage)
    products = finlife_api.search_financial_products(
        region=region,
        industry=industry,
        stage=stage,
    )

    recommendations: list[RecommendationItem] = []

    for item in policies.get("items", [])[:3]:
        recommendations.append(
            RecommendationItem(
                type="policy_fund",
                name=item["name"],
                reason=item.get("description", ""),
                link=item.get("link", ""),
            )
        )

    for item in products.get("items", [])[:3]:
        recommendations.append(
            RecommendationItem(
                type="financial_product",
                name=item["name"],
                reason=item.get("reason", ""),
                link=item.get("link", ""),
            )
        )

    return {
        "finance_result": {
            "policies": policies,
            "products": products,
            "recommendations": recommendations,
            "follow_up_questions": [
                "예상 창업/운영 자본금은 얼마인가요?",
                "대출 상환 기간은 어떻게 생각하고 계신가요?",
            ],
        }
    }
