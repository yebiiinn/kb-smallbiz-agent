"""정책자금·금융상품 에이전트.

데이터 소스:
- semas_crawler   : 소상공인진흥공단 정책 프로그램 (seed + 실시간 크롤링)
- bizinfo_api     : 기업마당 지원사업 공고 (API)
- finlife_api     : 금융감독원 금융상품 비교 (API)
- kb_crawler      : KB국민은행 소상공인 상품 (seed + 실시간 크롤링)
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import OpenAI

from project.config import settings
from project.schemas import BusinessStage, RecommendationItem
from project.state import AgentState
from project.tools import bizinfo_api, finlife_api, kb_crawler, semas_crawler

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# stage → intent 매핑
# ---------------------------------------------------------------------------
_STAGE_INTENT: dict[str, str] = {
    BusinessStage.STARTUP.value:   "창업자금",
    BusinessStage.OPERATION.value: "운전자금",
    BusinessStage.EXPANSION.value: "사업자금",
}

# stage별 맞춤 follow-up 질문
_FOLLOW_UP: dict[str, list[str]] = {
    BusinessStage.STARTUP.value: [
        "예상 창업 자금은 얼마나 필요하신가요?",
        "사업자등록 예정이신가요, 아니면 이미 하셨나요?",
        "담보로 활용 가능한 자산(부동산·보증서 등)이 있으신가요?",
    ],
    BusinessStage.OPERATION.value: [
        "현재 월 매출 규모는 어느 정도인가요?",
        "운영 자금이 필요한 구체적인 이유가 있으신가요? (임대료·재료비·인건비 등)",
        "기존에 이용 중인 대출이 있으신가요?",
    ],
    BusinessStage.EXPANSION.value: [
        "확장 방향이 어떻게 되시나요? (매장 추가 / 리모델링 / 설비 투자)",
        "현재 담보로 활용 가능한 자산이 있으신가요?",
        "사업 기간과 연 매출 규모를 알 수 있을까요?",
    ],
}

# stage별 요약 문구 템플릿
_SUMMARY_TEMPLATE: dict[str, str] = {
    BusinessStage.STARTUP.value:   "창업 단계 소상공인을 위한 정책자금·금융상품을 분석했습니다.",
    BusinessStage.OPERATION.value: "운영 안정화를 위한 운전자금·경영지원 상품을 분석했습니다.",
    BusinessStage.EXPANSION.value: "사업 확장을 위한 시설자금·투자 지원 상품을 분석했습니다.",
}

# 소진공 정책자금 신청 제외 업종 (일부 고위험·투기·사치 업종)
_INELIGIBLE_INDUSTRIES = {
    "유흥", "단란주점", "룸살롱", "노래방", "카지노", "사행", "도박",
    "성인", "마사지", "안마시술", "복권", "경마", "경정",
    "골프장", "스키장", "전문도박",
}


# ---------------------------------------------------------------------------
# 내부 헬퍼 — 상품 유형별 금리/조건 포맷
# ---------------------------------------------------------------------------
def _fmt_loan_rate(prod: dict[str, Any]) -> str:
    """기업대출·주택담보대출 금리 포맷 (min~max%)."""
    lo = prod.get("lend_rate_min")
    hi = prod.get("lend_rate_max")
    if lo is not None and hi is not None:
        return f"대출금리 연 {lo}~{hi}%"
    if lo is not None:
        return f"대출금리 연 {lo}%~"
    return "금리 별도 문의"


def _fmt_credit_rate(prod: dict[str, Any]) -> str:
    """신용대출 평균금리 포맷."""
    rate = prod.get("avg_rate")
    ptype = prod.get("crdt_prdt_type_nm", "")
    if rate is not None:
        return f"{ptype} | 평균금리 연 {rate}%"
    return ptype or "금리 별도 문의"


def _fmt_product_reason(prod: dict[str, Any]) -> str:
    """상품 딕셔너리에서 추천 이유 문구를 생성한다."""
    if "avg_rate" in prod:
        return _fmt_credit_rate(prod)
    if "intr_rate" in prod:
        trm = prod.get("save_trm")
        base = prod.get("intr_rate")
        best = prod.get("intr_rate2")
        trm_str = f"{trm}개월 " if trm else ""
        return f"{trm_str}기본금리 {base}% / 최고 {best}%"
    return _fmt_loan_rate(prod)


def _product_display_name(prod: dict[str, Any]) -> str:
    """금융회사명 + 상품명을 합쳐 표시명을 만든다."""
    co = prod.get("fin_co_name", "")
    nm = prod.get("product_name", "")
    return f"{co} {nm}".strip()


# ---------------------------------------------------------------------------
# 내부 헬퍼 — 경제지표 컨텍스트 파싱
# ---------------------------------------------------------------------------
def _parse_economic_context(economic: dict[str, Any]) -> dict[str, Any]:
    """economic_result 에서 finance 추천에 활용할 핵심 수치를 추출한다.

    Returns:
        rate_direction : "rising" | "falling" | "stable"
        base_rate      : 기준금리 (float 또는 None)
        csi            : 소비자심리지수 (float 또는 None)
        active_scenarios: 활성 거시 시나리오 목록 (list[str])
        indicator_summary : LLM 텍스트 요약
        consumption_trend : LLM 소비 트렌드 요약
        rate_rising    : bool — 금리 상승 기조 여부
        sentiment_weak : bool — 소비 심리 위축 여부 (CSI < 95)
    """
    raw = economic.get("raw", {})
    ecos = raw.get("ecos", {})

    base_rate = ecos.get("기준금리")
    csi = economic.get("consumer_sentiment")
    rate_direction_raw = raw.get("rate_direction", "동결")
    active_scenarios: list[str] = economic.get("active_scenarios", [])

    # economic 에이전트는 "인상"/"인하"/"동결" 로 저장 → 영문으로 정규화
    _DIR_MAP = {"인상": "rising", "인하": "falling", "동결": "stable"}
    rate_direction = _DIR_MAP.get(rate_direction_raw, rate_direction_raw)

    return {
        "rate_direction":     rate_direction,
        "base_rate":          base_rate,
        "csi":                csi,
        "active_scenarios":   active_scenarios,
        "indicator_summary":  economic.get("indicator", ""),
        "consumption_trend":  economic.get("consumption_trend", ""),
        "rate_rising":        rate_direction == "rising",
        "sentiment_weak":     (csi is not None and csi < 95),
    }


# ---------------------------------------------------------------------------
# 내부 헬퍼 — 업종 자격요건 필터
# ---------------------------------------------------------------------------
def _is_eligible_for_policy_fund(industry: str) -> bool:
    """소진공 정책자금 신청 제외 업종인지 판단한다."""
    return not any(kw in industry for kw in _INELIGIBLE_INDUSTRIES)


# ---------------------------------------------------------------------------
# 내부 헬퍼 — 추천 결과 정렬
# ---------------------------------------------------------------------------
def _sort_recommendations(
    recommendations: list[RecommendationItem],
    intent: str,
) -> list[RecommendationItem]:
    """추천 결과를 사용자에게 가장 유리한 순서로 재정렬한다.

    정책자금(policy_fund)은 원래 순서를 유지하되, 금융상품(financial_product)은
    KB 정책자금대출(가장 낮은 금리) 우선 → KB 소상공인 상품 → 기타 순으로 정렬한다.

    여유자금 intent(예금·적금)는 정렬 없이 그대로 반환.
    """
    _NO_SORT_INTENTS = {"여유자금", "주택"}
    if intent in _NO_SORT_INTENTS:
        return recommendations

    policy: list[RecommendationItem] = []
    financial: list[RecommendationItem] = []

    for rec in recommendations:
        if rec.type == "policy_fund":
            policy.append(rec)
        else:
            financial.append(rec)

    def _sort_key(rec: RecommendationItem) -> tuple[int, float]:
        name = rec.name or ""
        reason = rec.reason or ""
        # reason에서 금리 숫자 추출 (공통 유틸)
        m = re.search(r"연\s*(\d+\.\d+)[~%]|(\d+\.\d+)%", reason)
        parsed_rate = float(m.group(1) or m.group(2)) if m else 99.0

        # KB 정책자금대출: 최우선 (소진공 연계, 가장 낮은 금리대)
        if "정책자금대출" in name:
            return (0, parsed_rate)
        # KB 소상공인 상품 (사장님+, 신용대출 등): 두 번째
        if any(kw in name for kw in ("사장님+", "소상공인 신용대출", "소상공인 보증서")):
            return (1, parsed_rate)
        # 나머지 KB 상품
        if "KB" in name:
            return (2, parsed_rate)
        # 기타 finlife 상품 — 금리 낮은 순
        return (3, parsed_rate)

    financial.sort(key=_sort_key)
    return policy + financial


# ---------------------------------------------------------------------------
# 메인 노드 함수
# ---------------------------------------------------------------------------
def finance_node(state: AgentState) -> dict:
    """정책자금·금융상품 에이전트 노드.

    입력:
        state["context"]   : region / industry / stage
        state["user_query"]: 원본 질문 (intent 보정에 활용)

    출력:
        finance_result = {
            "summary"             : str,
            "recommendations"     : list[RecommendationItem],
            "follow_up_questions" : list[str],
            "raw"                 : {semas, bizinfo, finlife, kb} (디버그용),
        }
    """
    ctx = state["context"]
    user_query: str = state.get("user_query", "")
    region: str = ctx.region or "서울"
    industry: str = ctx.industry or "소상공인"
    stage: str = ctx.stage.value
    revenue: int | None = ctx.revenue

    # ── 1. stage + user_query → intent 키워드 결정 ──────────────────────────
    intent = _stage_intent(stage, user_query)

    # ── 1-b. 경제지표 컨텍스트 파싱 ─────────────────────────────────────────
    economic = state.get("economic_result") or {}
    commercial = state.get("commercial_result") or {}
    econ_ctx = _parse_economic_context(economic)

    # ── 1-c. crisis_result 기반 intent 보정 ──────────────────────────────────
    # crisis가 finance보다 먼저 실행되므로 위기 등급을 반영할 수 있다.
    crisis = state.get("crisis_result") or {}
    crisis_level = crisis.get("level", "normal")
    crisis_signals: list[str] = crisis.get("signals", [])

    if crisis_level == "critical" and intent not in {"상환연장", "여유자금", "주택"}:
        intent = "상환연장"
        logger.info("위기등급 critical → intent 강제 보정: 상환연장")
    elif crisis_level == "warning" and econ_ctx["sentiment_weak"] and intent == _STAGE_INTENT.get(stage, "창업자금"):
        logger.info("위기등급 warning + CSI 위축 → 정책자금 우선 강조")

    # ── 2. 4개 데이터 소스 호출 ──────────────────────────────────────────────
    # 2-a. 소진공(SEMAS) — 정책자금 프로그램 (seed + 실시간)
    # 자격 제외 업종이면 소진공 정책자금 결과를 비움 (빈 list)
    if _is_eligible_for_policy_fund(industry):
        semas_results: list[dict[str, Any]] = semas_crawler.search_semas_by_intent(intent)
    else:
        semas_results = []
        logger.info("업종 자격요건 미충족 (%s) — 소진공 정책자금 제외", industry)

    # 2-b. 기업마당(bizinfo) — 지원사업 공고 (API / mock)
    bizinfo_results: list[dict[str, Any]] = bizinfo_api.search_support_programs(
        intent=intent,
        region=region,
    )

    # 2-d. KB국민은행 — KB 소상공인 전용 상품 (seed + 실시간) — finlife 필터링 전에 먼저 호출
    kb_info: dict[str, Any] = kb_crawler.get_kb_sme_info()
    kb_policy: dict[str, Any] = kb_info.get("policy_fund", {})
    kb_sme_products_raw: list[dict[str, Any]] = kb_info.get("sme_products", [])

    # 2-c. 금감원 finlife — 민간 금융상품 (API / mock)
    finlife_result: dict[str, Any] = finlife_api.search_finance_products(
        intent=intent,
    )
    # 은행 다양성 필터: 같은 금융회사 상품이 연속으로 추천되지 않도록 1사 1상품 선택.
    # kb_crawler 가 KB 상품을 성공적으로 가져왔으면 finlife KB 상품 제외(중복 방지).
    skip_kb = bool(kb_policy.get("product_name"))
    finlife_products: list[dict[str, Any]] = _deduplicate_by_bank(
        finlife_result.get("products", []),
        skip_kb=skip_kb,
    )

    # ── 3. RecommendationItem 리스트 조립 ───────────────────────────────────
    recommendations: list[RecommendationItem] = []

    # 3-a. 소진공 프로그램 (최대 2건)
    for prog in semas_results[:2]:
        reason = prog.get("purpose") or prog.get("support_content", [""])[0] if isinstance(
            prog.get("support_content"), list
        ) else prog.get("support_content", "소진공 정책 프로그램")
        recommendations.append(
            RecommendationItem(
                type="policy_fund",
                name=prog.get("title", "소진공 지원 프로그램"),
                reason=str(reason)[:120],
                link=prog.get("url", "https://www.semas.or.kr"),
            )
        )

    # 3-b. 기업마당 지원사업 (최대 2건)
    for prog in bizinfo_results[:2]:
        period = prog.get("apply_period", "")
        summary_txt = prog.get("summary", "")
        reason = f"{summary_txt[:80]} (신청기간: {period})" if period else summary_txt[:100]
        recommendations.append(
            RecommendationItem(
                type="policy_fund",
                name=prog.get("title", "기업마당 지원사업"),
                reason=reason.strip(),
                link=prog.get("url", "https://www.bizinfo.go.kr"),
            )
        )

    # 3-c. 금감원 민간 금융상품 (최대 3건)
    for prod in finlife_products[:3]:
        recommendations.append(
            RecommendationItem(
                type="financial_product",
                name=_product_display_name(prod),
                reason=_fmt_product_reason(prod),
                link="https://finlife.fss.or.kr",
            )
        )

    # 3-d. KB 소상공인 정책자금대출
    #      저축·예치·주택 intent는 대출 추천이 맥락에 맞지 않으므로 제외
    _LOAN_INTENTS = {"창업자금", "운전자금", "사업자금", "상환연장", "경영비용", "대환"}
    if kb_policy.get("product_name") and intent in _LOAN_INTENTS:
        rate = kb_policy.get("interest_rate", {})
        reason_parts: list[str] = []
        if isinstance(rate, dict) and rate.get("min") and rate.get("max"):
            reason_parts.append(f"금리 연 {rate['min']}~{rate['max']}%")
        if kb_policy.get("loan_limit"):
            reason_parts.append(kb_policy["loan_limit"])
        if kb_policy.get("repayment"):
            reason_parts.append(kb_policy["repayment"])
        # 금리 상승 기조일 때 이벤트 혜택 문구 강조
        event = kb_policy.get("event", {})
        if econ_ctx["rate_rising"] and event.get("title"):
            reason_parts.append(f"⚡ {event['title']}")
        recommendations.append(
            RecommendationItem(
                type="financial_product",
                name=kb_policy["product_name"],
                reason=" | ".join(reason_parts) or "KB국민은행 소상공인 정책자금대출",
                link=kb_policy.get("url", "https://obiz.kbstar.com/quics?page=C112610"),
            )
        )

    # 3-e. KB 소상공인 개별 상품 (intent/region/업종 필터 후 최대 2건)
    kb_sme_filtered: list[dict[str, Any]] = []  # 반드시 초기화 후 조건 진입
    if intent in _LOAN_INTENTS:
        kb_sme_filtered = _filter_kb_sme_products(
            products=kb_sme_products_raw,
            intent=intent,
            region=region,
            industry=industry,
        )
        for p in kb_sme_filtered:
            rate_str = f"최저금리 연 {p['min_rate']}%" if p.get("min_rate") else ""
            limit_str = p.get("loan_limit", "")
            reason_parts_kb = [s for s in [rate_str, limit_str, p.get("description", "")] if s]
            recommendations.append(
                RecommendationItem(
                    type="financial_product",
                    name=p["product_name"],
                    reason=" | ".join(reason_parts_kb[:2]) or "KB국민은행 소상공인 전용 상품",
                    link=p.get("url", "https://obiz.kbstar.com/quics?page=C016282"),
                )
            )

    # ── 4. 추천 결과 정렬 (금융상품: 낮은 금리 우선, KB 우선) ──────────────
    recommendations = _sort_recommendations(recommendations, intent)

    # ── 4-b. revenue 기반 대출한도 적합도 필터 ───────────────────────────────
    if revenue is not None and intent in _LOAN_INTENTS:
        recommendations = _filter_by_revenue(recommendations, revenue)

    # ── 5. 요약 문구 ─────────────────────────────────────────────────────────
    n_policy = len(semas_results) + len(bizinfo_results)
    kb_included = kb_policy.get("product_name") and intent in _LOAN_INTENTS
    n_product = len(finlife_products) + (1 if kb_included else 0) + len(kb_sme_filtered)

    _INTENT_SUMMARY: dict[str, str] = {
        "여유자금": "여유자금 운용을 위한 예·적금 상품을 분석했습니다.",
        "주택":     "주택 관련 담보대출 상품을 분석했습니다.",
        "상환연장": "대출 상환 부담 완화를 위한 정책 프로그램을 분석했습니다.",
        "경영비용": "경영비용 지원 바우처·정책 프로그램을 분석했습니다.",
        "대환":     "고금리 대출을 저금리로 전환하기 위한 대환 상품을 분석했습니다.",
    }
    base_summary = _INTENT_SUMMARY.get(intent) or _SUMMARY_TEMPLATE.get(stage, "금융상품 분석 결과입니다.")

    # 경제지표 기반 추가 문구
    econ_note = ""
    if econ_ctx["rate_rising"]:
        econ_note = " 현재 금리 상승 기조로 고정금리·정책자금 우선 추천드립니다."
    elif econ_ctx["sentiment_weak"]:
        econ_note = " 소비 심리 위축 국면으로 저금리 정책자금 활용을 권장드립니다."

    summary = f"{base_summary} 정책자금 {n_policy}건, 금융상품 {n_product}건을 확인했습니다.{econ_note}"

    # ── 6. LLM 추천 이유 개인화 ──────────────────────────────────────────────
    recommendations = _enrich_with_llm(
        recommendations=recommendations,
        region=region,
        industry=industry,
        stage=stage,
        user_query=user_query,
        economic=economic,
        commercial=commercial,
        econ_ctx=econ_ctx,
        crisis_level=crisis_level,
        crisis_signals=crisis_signals,
    )

    return {
        "finance_result": {
            "summary": summary,
            "recommendations": recommendations,
            "follow_up_questions": _dynamic_follow_up(stage, region, industry, commercial, economic),
            "raw": {
                "semas":   semas_results,
                "bizinfo": bizinfo_results,
                "finlife": finlife_result,
                "kb":      kb_info,
            },
        }
    }


# ---------------------------------------------------------------------------
# 내부 헬퍼 — 은행 다양성 필터
# ---------------------------------------------------------------------------
_KB_BANK_NAMES = {"국민은행", "KB국민은행"}

# KB SME 상품 중 기본 제외할 카테고리
_KB_SKIP_CATEGORIES = {"채무조정", "대환대출"}
# 경기도 전용 상품 키워드
_GYEONGGI_KEYWORDS = {
    "경기", "수원", "성남", "의정부", "고양", "부천", "안산",
    "화성", "용인", "시흥", "평택", "안양", "광명", "하남", "파주",
}


def _filter_kb_sme_products(
    products: list[dict[str, Any]],
    intent: str,
    region: str,
    industry: str,
    max_items: int = 2,
) -> list[dict[str, Any]]:
    """intent/region/업종 기준으로 KB 소상공인 상품을 필터링한다.

    - 채무조정·대환 상품: 상환연장·대환 intent 에서만 포함 (이 경우 최우선 배치)
    - 경기도 전용 상품: region 이 경기권이 아니면 제외
    - 프랜차이즈 대출: 프랜차이즈 업종이 아니면 제외
    - 정렬 기준:
        상환연장·대환 intent → 채무조정 카테고리 우선, 그 다음 낮은 금리 순
        일반 대출 intent → 낮은 금리 순 (None 은 뒤로)
    """
    _REFINANCE_INTENTS = {"상환연장", "대환"}
    is_refinance = intent in _REFINANCE_INTENTS

    filtered: list[dict[str, Any]] = []
    for p in products:
        cat = p.get("category", "")

        # 채무조정·대환은 상환 관련 intent 에서만
        if cat in _KB_SKIP_CATEGORIES and not is_refinance:
            continue

        # 경기도 전용 상품 — region 필터
        if any(kw in p.get("description", "") for kw in ("경기도",)):
            if not any(kw in region for kw in _GYEONGGI_KEYWORDS):
                continue

        # 프랜차이즈 대출 — 업종 필터
        if "프랜차이즈" in p.get("product_name", ""):
            franchise_kws = {"프랜차이즈", "가맹점", "체인"}
            if not any(kw in industry for kw in franchise_kws):
                continue

        filtered.append(p)

    # 정렬:
    # - 상환연장·대환: 채무조정 카테고리 먼저, 그 다음 금리 낮은 순
    # - 일반 대출: 금리 낮은 순 (None 은 맨 뒤)
    def _sort_key(p: dict[str, Any]) -> tuple[int, float]:
        cat = p.get("category", "")
        rate = p.get("min_rate")
        if is_refinance and cat in _KB_SKIP_CATEGORIES:
            return (0, rate or 99.0)
        return (1, rate if rate is not None else 99.0)

    filtered.sort(key=_sort_key)
    return filtered[:max_items]


def _deduplicate_by_bank(
    products: list[dict[str, Any]],
    max_items: int = 5,
    skip_kb: bool = True,
) -> list[dict[str, Any]]:
    """같은 금융회사 상품이 중복 추천되지 않도록 1사 1상품으로 추려낸다.

    정렬 기준: lend_rate_min 오름차순 (낮은 금리 우선).
    avg_rate 만 있는 신용대출도 같은 기준으로 처리.

    Args:
        products: finlife 전체 상품 리스트.
        max_items: 최종 반환할 최대 상품 수.
        skip_kb: True 이면 KB국민은행 상품을 제외한다.

    Returns:
        금융회사별 대표 1개씩 추린 리스트.
    """
    def _rate_key(p: dict[str, Any]) -> float:
        return (
            p.get("lend_rate_min")
            or p.get("avg_rate")
            or p.get("intr_rate")
            or 99.0
        )

    seen_banks: set[str] = set()
    result: list[dict[str, Any]] = []

    for prod in sorted(products, key=_rate_key):
        bank = prod.get("fin_co_name", "")
        if skip_kb and bank in _KB_BANK_NAMES:
            continue
        if bank in seen_banks:
            continue
        seen_banks.add(bank)
        result.append(prod)
        if len(result) >= max_items:
            break

    return result


# ---------------------------------------------------------------------------
# 내부 헬퍼 — intent 결정
# ---------------------------------------------------------------------------
def _stage_intent(stage: str, user_query: str) -> str:
    """stage 기본값에 user_query 키워드를 반영해 최종 intent 를 반환한다.

    user_query 에 명시적 키워드가 있으면 override.
    없으면 stage 기반 기본 intent(창업자금/운전자금/사업자금)를 반환한다.
    """
    q = user_query

    # 여유자금·예치 계열
    if any(kw in q for kw in ("저축", "예금", "적금", "예치", "여유자금")):
        return "여유자금"

    # 주택·부동산 계열
    if any(kw in q for kw in ("주택", "부동산", "아파트", "주담대")):
        return "주택"

    # 상환 어려움·연체 계열 → 소진공 상환연장 + 채무조정 상품 우선
    if any(kw in q for kw in (
        "상환", "연장", "코로나", "분할상환",
        "연체", "갚기 힘들", "상환 어려", "만기 연장",
    )):
        return "상환연장"

    # 고금리 대환 계열
    if any(kw in q for kw in ("대환", "갈아타기", "고금리", "금리 전환", "대출 전환")):
        return "대환"

    # 경영 바우처 계열
    if any(kw in q for kw in ("바우처", "공과금", "보험료", "경영비용")):
        return "경영비용"

    return _STAGE_INTENT.get(stage, "창업자금")


# ---------------------------------------------------------------------------
# LLM 추천 이유 개인화
# ---------------------------------------------------------------------------
_STAGE_KO: dict[str, str] = {
    "startup":   "창업 준비",
    "operation": "운영 중",
    "expansion": "확장 계획",
}

_SYSTEM_PROMPT = """\
당신은 소상공인 금융 전문 컨설턴트입니다.
사용자 상황과 현재 경제 환경을 반영해 각 금융상품·정책자금의 추천 이유를 새롭게 작성해 주세요.

규칙:
- 각 항목당 1~2문장, 최대 80자
- 사용자의 업종·지역·사업 단계를 구체적으로 언급할 것
- 숫자(금리·한도·신청기간)가 있으면 반드시 포함할 것
- 경기지표(금리 방향, 소비심리)를 추천 이유에 자연스럽게 녹일 것
- 과장 표현·광고 문구 금지. 실용적이고 간결하게
- 반드시 JSON 객체만 반환. 키는 "items", 값은 배열
"""


def _enrich_with_llm(
    recommendations: list[RecommendationItem],
    region: str,
    industry: str,
    stage: str,
    user_query: str,
    economic: dict[str, Any],
    commercial: dict[str, Any],
    econ_ctx: dict[str, Any] | None = None,
    crisis_level: str = "normal",
    crisis_signals: list[str] | None = None,
) -> list[RecommendationItem]:
    """LLM 으로 각 추천 항목의 reason 을 개인화한다."""
    if not settings.openai_api_key or not recommendations:
        return recommendations

    if econ_ctx is None:
        econ_ctx = _parse_economic_context(economic)

    stage_ko = _STAGE_KO.get(stage, stage)
    comm_summary = commercial.get("summary", "")

    context_lines = [
        f"- 사용자: {region} / {industry} / {stage_ko}",
        f"- 원본 질문: {user_query}",
    ]

    base_rate = econ_ctx.get("base_rate")
    csi = econ_ctx.get("csi")
    rate_dir = econ_ctx.get("rate_direction", "stable")
    scenarios = econ_ctx.get("active_scenarios", [])

    if base_rate is not None:
        context_lines.append(f"- 기준금리: {base_rate}% (방향: {rate_dir})")
    if csi is not None:
        sentiment = "위축" if csi < 95 else ("보통" if csi < 105 else "양호")
        context_lines.append(f"- 소비자심리지수(CSI): {csi} → {sentiment}")
    if scenarios:
        context_lines.append(f"- 활성 경기 시나리오: {', '.join(scenarios[:3])}")

    indicator_summary = econ_ctx.get("indicator_summary", "")
    consumption_trend = econ_ctx.get("consumption_trend", "")
    if indicator_summary:
        context_lines.append(f"- 경기지표 요약: {indicator_summary[:120]}")
    if consumption_trend:
        context_lines.append(f"- 소비 트렌드: {consumption_trend[:100]}")
    if comm_summary:
        context_lines.append(f"- 상권 분석: {comm_summary[:100]}")

    if crisis_level != "normal":
        context_lines.append(f"- 위기 등급: {crisis_level}")
    if crisis_signals:
        context_lines.append(f"- 위기 신호: {'; '.join(crisis_signals[:2])}")

    context_block = "\n".join(context_lines)

    # ── 상품 목록 조립 (current_reason 제외 — LLM 이 베끼지 않도록) ──────
    items_for_llm = [
        {"index": i, "type": r.type, "name": r.name}
        for i, r in enumerate(recommendations)
    ]
    items_block = json.dumps(items_for_llm, ensure_ascii=False, indent=2)

    user_prompt = f"""\
[사용자 상황]
{context_block}

[추천 항목]
{items_block}

위 사용자 상황과 경제 환경을 반영해 각 항목별 추천 이유를 새로 작성하세요.
반환 형식 (JSON 객체):
{{"items": [{{"index": 0, "reason": "..."}}, {{"index": 1, "reason": "..."}}]}}
"""

    try:
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
            max_tokens=700,
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or ""
        parsed = json.loads(raw)

        reason_list: list[dict] = next(
            (v for v in parsed.values() if isinstance(v, list)), []
        )
        reason_map: dict[int, str] = {
            item["index"]: item["reason"]
            for item in reason_list
            if isinstance(item, dict) and "index" in item and "reason" in item
        }
        logger.debug("finance LLM reason_map: %s", reason_map)

        enriched: list[RecommendationItem] = []
        for i, rec in enumerate(recommendations):
            if i in reason_map and reason_map[i].strip():
                enriched.append(rec.model_copy(update={"reason": reason_map[i].strip()}))
            else:
                enriched.append(rec)

        logger.info("finance LLM enrichment 완료: %d건", len(enriched))
        return enriched

    except Exception as exc:
        logger.warning("finance LLM enrichment 실패 (정적 문구 유지): %s", exc)
        return recommendations


# ---------------------------------------------------------------------------
# 내부 헬퍼 — revenue 기반 대출한도 필터
# ---------------------------------------------------------------------------
_REVENUE_TIER: list[tuple[int, str]] = [
    (1_000, "소규모"),    # 1000만원 미만
    (3_000, "중소규모"),  # 3000만원 미만
    (10_000, "중규모"),   # 1억원 미만
]


def _revenue_tier(revenue: int) -> str:
    for threshold, label in _REVENUE_TIER:
        if revenue < threshold:
            return label
    return "대규모"


def _filter_by_revenue(
    recommendations: list[RecommendationItem],
    revenue: int,
) -> list[RecommendationItem]:
    """월 매출(revenue, 만원 단위)을 고려해 대출한도 적합도 안내를 reason에 추가한다.

    상품을 제거하지 않고 reason에 안내를 append해 사용자가 판단하도록 한다.
    """
    tier = _revenue_tier(revenue)
    revenue_fmt = f"{revenue:,}만 원"

    annotated: list[RecommendationItem] = []
    for rec in recommendations:
        reason = rec.reason or ""
        # reason에서 억원 단위 한도 추출 (예: "최대 7천만원", "최대 2억원")
        m = re.search(r"(\d+)\s*억\s*원", reason)
        if m:
            limit_eok = int(m.group(1))
            limit_man = limit_eok * 10_000  # 억원 → 만원
            if limit_man > revenue * 18:  # 월매출 18개월치 초과 한도
                reason = reason + f" (월매출 {revenue_fmt} 기준, 한도 여유 충분)"
        if tier == "소규모":
            reason = reason + f" ※ 월매출 {revenue_fmt} — 소규모 맞춤 한도 확인 권장"
        annotated.append(rec.model_copy(update={"reason": reason}))
    return annotated


# ---------------------------------------------------------------------------
# 내부 헬퍼 — 동적 follow-up 질문 생성
# ---------------------------------------------------------------------------
def _dynamic_follow_up(
    stage: str,
    region: str,
    industry: str,
    commercial: dict[str, Any],
    economic: dict[str, Any],
) -> list[str]:
    """상권·경기 분석 결과를 반영해 개인화된 후속 질문 3개를 생성한다."""
    questions: list[str] = []

    competition_level = commercial.get("competition_level", "")
    sales_trend = commercial.get("sales_trend", "")
    csi = economic.get("consumer_sentiment")
    active_scenarios: list[str] = economic.get("active_scenarios", [])

    if competition_level == "high":
        questions.append(f"{region} {industry} 업종 경쟁이 치열한데, 차별화 전략이 있으신가요?")
    elif competition_level == "low":
        questions.append(f"{region} {industry} 상권 경쟁이 낮습니다. 수요 확보 방안은 검토하셨나요?")

    if sales_trend and "-" in sales_trend and "%" in sales_trend:
        questions.append("매출 하락세가 감지됩니다. 운전자금·경영안정 자금 필요 규모는 얼마인가요?")
    elif sales_trend and "+" in sales_trend:
        questions.append("매출 성장세가 보입니다. 시설 확장이나 추가 투자 계획이 있으신가요?")

    if csi is not None and csi < 95:
        questions.append("소비 심리 위축 국면입니다. 단기 유동성 확보를 위한 대출 규모를 생각해 두셨나요?")
    elif any("금리" in s for s in active_scenarios):
        questions.append("금리 변동 국면입니다. 고정금리·변동금리 중 어떤 방식을 선호하시나요?")

    base = _FOLLOW_UP.get(stage, _FOLLOW_UP[BusinessStage.STARTUP.value])
    for q in base:
        if q not in questions:
            questions.append(q)

    return questions[:3]
