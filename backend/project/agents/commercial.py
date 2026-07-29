"""지역 상권 분석 에이전트 — 담당자 A.

API:
- 소진공 상권 정보 API
- 서울시 추정매출 API
- 카카오맵 API
"""

from project.state import AgentState
from project.tools import kakao_map_api, sangkwon_api, seoul_sales_api

COMPETITION_LEVEL_SCORE = {"low": 85, "medium": 65, "high": 45}
COMPETITION_LEVEL_LABEL = {"low": "낮음", "medium": "보통", "high": "높음"}


def _format_amount(amount: int | None) -> str:
    if amount is None:
        return ""
    if amount >= 100_000_000:
        return f"약 {amount / 100_000_000:.1f}억 원"
    if amount >= 10_000:
        return f"약 {amount // 10_000:,}만 원"
    return f"{amount:,}원"


def _derive_per_store_sales(seoul_sales: dict, store_count: int | None) -> tuple[str, int | None]:
    total_amount = seoul_sales.get("total_sales_amount")
    if store_count and store_count > 0 and total_amount:
        per_store_amount = total_amount // store_count
        return _format_amount(per_store_amount), per_store_amount
    return seoul_sales.get("monthly_sales", ""), None


def _sales_trend_score(trend: str) -> float:
    if "+" in trend:
        return 75
    if "-" in trend:
        return 45
    return 60


def _compute_combined_score(sangkwon: dict, seoul_sales: dict, kakao_map: dict) -> int:
    market_score = float(sangkwon.get("score") or 60)
    sales_score = _sales_trend_score(seoul_sales.get("sales_trend", ""))
    competition_score = float(
        COMPETITION_LEVEL_SCORE.get(kakao_map.get("competition_level", ""), 60)
    )
    combined = 0.45 * market_score + 0.30 * sales_score + 0.25 * competition_score
    return max(0, min(100, round(combined)))


def _build_summary(
    region: str,
    industry: str,
    sangkwon: dict,
    seoul_sales: dict,
    kakao_map: dict,
    per_store_sales: str,
) -> str:
    store_count = sangkwon.get("store_count")
    ratio_pct = sangkwon.get("competition_ratio")
    if ratio_pct is not None:
        ratio_text = f"{ratio_pct * 100:.1f}%"
    else:
        ratio_text = "집계 중"

    competition_text = sangkwon.get("competition_text") or sangkwon.get("competition", "")
    market_sentence = (
        f"{region} {industry} 업종 상가업소는 {store_count:,}개"
        if store_count
        else f"{region} {industry} 업종 상권"
    )
    if store_count:
        market_sentence += f"(전체 대비 {ratio_text})"
    if competition_text:
        market_sentence += f"이며, {competition_text.rstrip('.')}."

    quarter = seoul_sales.get("quarter", "")
    sales_trend = seoul_sales.get("sales_trend", "")
    industry_name = seoul_sales.get("industry_name", industry)
    if per_store_sales:
        sales_sentence = (
            f"{quarter + ' ' if quarter else ''}{industry_name} 업종 "
            f"점포당 월 추정매출은 {per_store_sales}"
        )
        if sales_trend:
            sales_sentence += f"이며, {sales_trend.rstrip('.')}."
        else:
            sales_sentence += "."
    else:
        sales_sentence = seoul_sales.get("summary", "")

    poi_count = kakao_map.get("poi_count")
    level = kakao_map.get("competition_level", "")
    level_label = COMPETITION_LEVEL_LABEL.get(level, level or "보통")
    if poi_count is not None:
        competition_sentence = (
            f"카카오맵 기준 인근 {industry} {poi_count}곳이 확인되어 "
            f"주변 경쟁 강도는 {level_label}입니다."
        )
    else:
        competition_sentence = kakao_map.get("summary", "")

    parts = [part for part in (market_sentence, sales_sentence, competition_sentence) if part]
    return " ".join(parts)


def commercial_node(state: AgentState) -> dict:
    ctx = state["context"]
    region = ctx.region or "서울 강남구"
    industry = ctx.industry or "카페"

    sangkwon = sangkwon_api.fetch_commercial_district(region=region, industry=industry)
    store_count = sangkwon.get("store_count")
    seoul_sales = seoul_sales_api.fetch_estimated_sales(region=region, industry=industry)
    kakao_map = kakao_map_api.search_nearby_competition(region=region, industry=industry)

    is_sales_mock = seoul_sales.get("source") == "mock"
    per_store_sales, per_store_amount = _derive_per_store_sales(seoul_sales, store_count)
    summary = _build_summary(
        region, industry, sangkwon, seoul_sales, kakao_map, per_store_sales
    )
    if is_sales_mock and "서울" not in region:
        summary += f" (추정매출은 서울 외 지역 참고치이며, 실제 수치는 소진공 상권정보에서 확인하세요.)"

    score = _compute_combined_score(sangkwon, seoul_sales, kakao_map)

    return {
        "commercial_result": {
            "region": region,
            "industry": industry,
            "summary": summary,
            "score": score,
            "foot_traffic": sangkwon.get("foot_traffic", ""),
            "competition": kakao_map.get("summary", sangkwon.get("competition", "")),
            "monthly_sales": per_store_sales,
            "total_monthly_sales": seoul_sales.get("monthly_sales", ""),
            "per_store_sales_amount": per_store_amount,
            "sales_trend": seoul_sales.get("sales_trend", ""),
            "poi_count": kakao_map.get("poi_count"),
            "competition_level": kakao_map.get("competition_level", ""),
            "is_sales_estimated": is_sales_mock,
            "raw": {
                "sangkwon": sangkwon,
                "seoul_sales": seoul_sales,
                "kakao_map": kakao_map,
            },
        }
    }
