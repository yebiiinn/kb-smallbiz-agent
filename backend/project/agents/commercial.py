"""지역 상권 분석 에이전트 — 담당자 A.

API:
- 소진공 상권 정보 API
- 서울시 추정매출 API
- 카카오맵 API
"""

from project.state import AgentState
from project.tools import kakao_map_api, sangkwon_api, seoul_sales_api


def commercial_node(state: AgentState) -> dict:
    ctx = state["context"]
    region = ctx.region or "서울 강남구"
    industry = ctx.industry or "카페"

    sangkwon = sangkwon_api.fetch_commercial_district(region=region, industry=industry)
    seoul_sales = seoul_sales_api.fetch_estimated_sales(region=region, industry=industry)
    kakao_map = kakao_map_api.search_nearby_competition(region=region, industry=industry)

    summary_parts = [
        sangkwon.get("summary", ""),
        seoul_sales.get("summary", ""),
        kakao_map.get("summary", ""),
    ]
    summary = " ".join(part for part in summary_parts if part)

    return {
        "commercial_result": {
            "region": region,
            "industry": industry,
            "summary": summary,
            "score": sangkwon.get("score", 0),
            "foot_traffic": sangkwon.get("foot_traffic", ""),
            "competition": kakao_map.get("summary", sangkwon.get("competition", "")),
            "monthly_sales": seoul_sales.get("monthly_sales", ""),
            "sales_trend": seoul_sales.get("sales_trend", ""),
            "poi_count": kakao_map.get("poi_count"),
            "competition_level": kakao_map.get("competition_level", ""),
            "raw": {
                "sangkwon": sangkwon,
                "seoul_sales": seoul_sales,
                "kakao_map": kakao_map,
            },
        }
    }
