"""위기진단 에이전트 — 상권·경기·공공데이터 기반 위기 신호 분석."""

from project.state import AgentState
from project.tools import crisis_data

LEVEL_ORDER = {"normal": 0, "warning": 1, "critical": 2}
COMMERCIAL_WARNING_SCORE = 45
COMMERCIAL_CRITICAL_SCORE = 35
REVENUE_CRITICAL_THRESHOLD = 500  # 월 500만원 미만 (만원 단위)
LOW_MARKET_COUNT_THRESHOLD = 50
COMPETITION_RATIO_WARNING = 0.05
STORE_COUNT_WARNING = 3_000
CSI_WARNING_THRESHOLD = 100
CSI_CRITICAL_THRESHOLD = 90
SMALL_MARKET_AREA_RATIO = 0.7


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


def _parse_consumer_sentiment(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _economic_csi_is_weak(sentiment: float | None) -> bool:
    return sentiment is not None and sentiment < CSI_WARNING_THRESHOLD


def _economic_csi_is_critical(sentiment: float | None) -> bool:
    return sentiment is not None and sentiment < CSI_CRITICAL_THRESHOLD


def _get_sangkwon(commercial: dict) -> dict:
    return (commercial.get("raw") or {}).get("sangkwon") or {}


def _build_growth_signal(regional: dict) -> str | None:
    growth_count = regional.get("growth_market_count", 0)
    avg_area = regional.get("avg_growth_market_area_m2")
    median_area = regional.get("national_median_market_area_m2")

    if not regional.get("signgu"):
        return None

    if growth_count == 0 and regional.get("major_market_count", 0) == 0:
        return "인근 성장상권 데이터가 없어 상권 활성도를 추가로 확인할 필요가 있습니다."

    if growth_count == 0:
        return None

    if avg_area and median_area and avg_area < median_area * SMALL_MARKET_AREA_RATIO:
        return (
            f"인근 상권 평균 규모({int(avg_area):,}㎡)가 전국 중앙값({int(median_area):,}㎡) 대비 작아 "
            "성장 여력이 제한될 수 있습니다."
        )

    return None


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

    market_names = regional.get("sample_market_names") or []
    if market_names:
        names = ", ".join(market_names[:3])
        actions.append(f"인근 주요상권({names}) 매출·유동 추이 비교")

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
    sangkwon = _get_sangkwon(commercial)
    store_count = sangkwon.get("store_count")
    competition_ratio = sangkwon.get("competition_ratio")
    consumer_sentiment = _parse_consumer_sentiment(economic.get("consumer_sentiment"))

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

    if competition_ratio is not None and competition_ratio >= COMPETITION_RATIO_WARNING:
        if commercial.get("competition_level") != "high":
            level = _max_level(level, "warning")
        ratio_pct = competition_ratio * 100
        signals.append(
            f"{industry} 업종 점포 비중이 {ratio_pct:.1f}%로 높아 상권 내 경쟁 과밀 신호가 있습니다."
        )

    if store_count is not None and store_count >= STORE_COUNT_WARNING:
        level = _max_level(level, "warning")
        signals.append(f"{region} {industry} 점포 수가 {store_count:,}개로 공급 과다 구간입니다.")

    sales_trend = commercial.get("sales_trend", "")
    if _sales_trend_is_negative(sales_trend):
        level = _max_level(level, "warning")
        signals.append(f"추정매출 추세가 약세입니다({sales_trend.rstrip('.')}).")

    if revenue is not None and revenue < REVENUE_CRITICAL_THRESHOLD and stage == "operation":
        level = _max_level(level, "critical")
        signals.append("자기신고 월 매출이 생계·운영 기준 이하로 추정됩니다.")

    if _economic_csi_is_critical(consumer_sentiment):
        level = _max_level(level, "critical")
        signals.append(
            f"소비자심리지수(CSI)가 {consumer_sentiment:.0f}로 위축 구간입니다."
        )
    elif _economic_csi_is_weak(consumer_sentiment):
        level = _max_level(level, "warning")
        signals.append(
            f"소비자심리지수(CSI)가 {consumer_sentiment:.0f}로 기준(100) 미만입니다."
        )
    elif _economic_is_weak(
        economic.get("indicator", ""),
        economic.get("consumption_trend", ""),
    ):
        level = _max_level(level, "warning")
        signals.append("경기·소비 지표에서 둔화 신호가 감지됩니다.")

    growth_signal = _build_growth_signal(regional)
    if growth_signal:
        level = _max_level(level, "warning")
        signals.append(growth_signal)

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
            "growth_market_count": regional.get("growth_market_count"),
            "growth_market_names": regional.get("growth_market_names") or [],
            "education_count": regional.get("education_count"),
            "raw": {
                "regional": regional,
                "commercial_score": commercial_score,
                "store_count": store_count,
                "competition_ratio": competition_ratio,
                "consumer_sentiment": consumer_sentiment,
            },
        }
    }
