"""위기진단 에이전트 — 상권·경기·공공데이터 기반 위기 신호 분석."""

from project.state import AgentState
from project.tools import crisis_data

LEVEL_ORDER = {"normal": 0, "warning": 1, "critical": 2}
COMMERCIAL_WARNING_SCORE = 45
COMMERCIAL_CRITICAL_SCORE = 35
REVENUE_CRITICAL_THRESHOLD = 5_000_000
LOW_MARKET_COUNT_THRESHOLD = 50


def _max_level(current: str, new: str) -> str:
    if LEVEL_ORDER[new] > LEVEL_ORDER[current]:
        return new
    return current


def _sales_trend_is_negative(trend: str) -> bool:
    return "-" in trend and "%" in trend


def _economic_is_weak(indicator: str, consumption: str) -> bool:
    text = f"{indicator} {consumption}"
    weak_keywords = ("하락", "부진", "둔화", "감소", "위축", "축소")
    return any(keyword in text for keyword in weak_keywords)


def _build_regional_signal(region: str, regional: dict) -> str | None:
    major_count = regional.get("major_market_count", 0)
    molit_count = regional.get("molit_market_count", 0)
    national_count = regional.get("national_market_count")

    if major_count == 0 and molit_count == 0:
        return f"{region}에 매칭되는 주요상권 데이터가 없어 상권 리스크 확인이 필요합니다."

    if national_count is not None and national_count <= LOW_MARKET_COUNT_THRESHOLD:
        return (
            f"{regional.get('sido_short')} 지역 상권 수({national_count}개)가 전국 대비 적어 "
            "외부 유입·시장 활성도를 추가로 확인할 필요가 있습니다."
        )

    return None


def _build_summary(
    level: str,
    signals: list[str],
    region: str,
    regional: dict,
) -> str:
    if not signals:
        major = regional.get("major_market_count", 0)
        molit = regional.get("molit_market_count", 0)
        context = ""
        if major or molit:
            context = f" (주요상권 {major}개·국토부 {molit}개 기준)"
        return f"{region} 기준 현재 특별한 위기 신호는 없으며{context}, 정기 모니터링을 권장합니다."

    joined = " ".join(signals)
    if level == "critical":
        return f"{region}에서 경영 위기 신호가 감지되었습니다. {joined}"
    if level == "warning":
        return f"{region}에서 주의가 필요한 신호가 있습니다. {joined}"
    return joined


def _suggest_actions(level: str, regional: dict) -> list[str]:
    actions: list[str] = []
    if level == "critical":
        actions.extend(
            [
                "정책자금·경영안정 지원 사업 우선 확인",
                "대출 만기 연장·상환 유예 등 금융 상담 검토",
            ]
        )
    elif level == "warning":
        actions.extend(
            [
                "소비 트렌드·매출 추세 재분석",
                "단기 유동성·재고·고정비 점검",
            ]
        )
    else:
        actions.append("정기적인 상권·경기 모니터링")

    education = regional.get("education_institutions") or []
    if education:
        names = ", ".join(item.get("name", "") for item in education[:2])
        actions.append(f"인근 소상공인 교육기관 활용 검토 ({names})")

    if regional.get("sample_market_names"):
        actions.append("인근 주요상권(소상공인365·국토교통부) 매출·유동 추이 비교")

    return actions


def _compute_crisis_score(level: str, commercial_score: int, signal_count: int) -> int:
    base = {"critical": 25, "warning": 45, "normal": 70}[level]
    commercial_factor = max(0, min(30, commercial_score // 3))
    penalty = min(20, signal_count * 5)
    return max(0, min(100, base + commercial_factor - penalty))


def crisis_node(state: AgentState) -> dict:
    ctx = state["context"]
    region = ctx.region or "서울 강남구"
    industry = ctx.industry or "카페"
    commercial = state.get("commercial_result") or {}
    economic = state.get("economic_result") or {}

    regional = crisis_data.analyze_regional_context(region)
    commercial_score = int(commercial.get("score") or 50)
    revenue = ctx.revenue
    stage = ctx.stage.value

    level = "normal"
    signals: list[str] = []

    if commercial_score < COMMERCIAL_CRITICAL_SCORE:
        level = _max_level(level, "critical")
        signals.append(
            f"{industry} 상권 종합 점수가 {commercial_score}점으로 낮아 경영 난이도가 높습니다."
        )
    elif commercial_score < COMMERCIAL_WARNING_SCORE:
        level = _max_level(level, "warning")
        signals.append(f"{industry} 상권 종합 점수가 {commercial_score}점으로 주의가 필요합니다.")

    if commercial.get("competition_level") == "high":
        level = _max_level(level, "warning")
        poi_count = commercial.get("poi_count")
        if poi_count is not None:
            signals.append(f"주변 {industry} 경쟁 업체가 {poi_count}곳으로 밀집해 있습니다.")
        else:
            signals.append("주변 경쟁 업체 밀집도가 높습니다.")

    sales_trend = commercial.get("sales_trend", "")
    if _sales_trend_is_negative(sales_trend):
        level = _max_level(level, "warning")
        signals.append(f"추정매출 추세가 약세입니다({sales_trend.rstrip('.')}).")

    if revenue is not None and revenue < REVENUE_CRITICAL_THRESHOLD and stage == "operation":
        level = _max_level(level, "critical")
        signals.append("자기신고 월 매출이 생계·운영 기준 이하로 추정됩니다.")

    if _economic_is_weak(
        economic.get("indicator", ""),
        economic.get("consumption_trend", ""),
    ):
        level = _max_level(level, "warning")
        signals.append("경기·소비 지표에서 둔화 신호가 감지됩니다.")

    regional_signal = _build_regional_signal(region, regional)
    if regional_signal:
        if regional.get("major_market_count", 0) == 0:
            level = _max_level(level, "warning")
        signals.append(regional_signal)

    summary = _build_summary(level, signals, region, regional)
    crisis_score = _compute_crisis_score(level, commercial_score, len(signals))

    return {
        "crisis_result": {
            "level": level,
            "score": crisis_score,
            "signals": signals,
            "summary": summary,
            "recommended_actions": _suggest_actions(level, regional),
            "region": region,
            "industry": industry,
            "major_market_count": regional.get("major_market_count"),
            "molit_market_count": regional.get("molit_market_count"),
            "education_count": regional.get("education_count"),
            "raw": {
                "regional": regional,
                "commercial_score": commercial_score,
            },
        }
    }
