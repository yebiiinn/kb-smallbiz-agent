"""정책자금·금융상품 에이전트.

데이터 소스:
- semas_crawler   : 소상공인진흥공단 정책 프로그램 (seed + 실시간 크롤링)
- bizinfo_api     : 기업마당 지원사업 공고 (API)
- finlife_api     : 금융감독원 금융상품 비교 (API)
- kb_crawler      : KB국민은행 소상공인 상품 (seed + 실시간 크롤링)
"""

from __future__ import annotations

from typing import Any

from project.schemas import BusinessStage, RecommendationItem
from project.state import AgentState
from project.tools import bizinfo_api, finlife_api, kb_crawler, semas_crawler

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
    # 신용대출은 avg_rate 키를 가짐
    if "avg_rate" in prod:
        return _fmt_credit_rate(prod)
    # 예·적금은 intr_rate 키를 가짐
    if "intr_rate" in prod:
        trm = prod.get("save_trm")
        base = prod.get("intr_rate")
        best = prod.get("intr_rate2")
        trm_str = f"{trm}개월 " if trm else ""
        return f"{trm_str}기본금리 {base}% / 최고 {best}%"
    # 기업대출·주택담보대출
    return _fmt_loan_rate(prod)


def _product_display_name(prod: dict[str, Any]) -> str:
    """금융회사명 + 상품명을 합쳐 표시명을 만든다."""
    co = prod.get("fin_co_name", "")
    nm = prod.get("product_name", "")
    return f"{co} {nm}".strip()


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
    stage: str = ctx.stage.value  # "startup" | "operation" | "expansion"

    # ── 1. stage + user_query → intent 키워드 결정 ──────────────────────────
    # user_query 에 명시적 키워드가 있으면 우선 반영, 없으면 stage 기본값 사용
    intent = _stage_intent(stage, user_query)

    # ── 2. 4개 데이터 소스 병렬 호출 ────────────────────────────────────────
    # 2-a. 소진공(SEMAS) — 정책자금 프로그램 (seed + 실시간)
    semas_results: list[dict[str, Any]] = semas_crawler.search_semas_by_intent(intent)

    # 2-b. 기업마당(bizinfo) — 지원사업 공고 (API / mock)
    bizinfo_results: list[dict[str, Any]] = bizinfo_api.search_support_programs(
        intent=intent,
        region=region,
    )

    # 2-d. KB국민은행 — KB 소상공인 전용 상품 (seed + 실시간) — finlife 필터링 전에 먼저 호출
    kb_info: dict[str, Any] = kb_crawler.get_kb_sme_info()
    kb_policy: dict[str, Any] = kb_info.get("policy_fund", {})

    # 2-c. 금감원 finlife — 민간 금융상품 (API / mock)
    finlife_result: dict[str, Any] = finlife_api.search_finance_products(
        intent=intent,
    )
    # 은행 다양성 필터: 같은 금융회사 상품이 연속으로 추천되지 않도록 1사 1상품 선택.
    # kb_crawler 가 KB 상품을 성공적으로 가져왔으면 finlife KB 상품 제외(중복 방지).
    # kb_crawler 결과가 비어있으면 finlife KB 상품도 포함(fallback).
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
        summary = prog.get("summary", "")
        reason = f"{summary[:80]} (신청기간: {period})" if period else summary[:100]
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
    _LOAN_INTENTS = {"창업자금", "운전자금", "사업자금", "상환연장", "경영비용"}
    if kb_policy.get("product_name") and intent in _LOAN_INTENTS:
        rate = kb_policy.get("interest_rate", {})
        reason_parts: list[str] = []
        if isinstance(rate, dict) and rate.get("min") and rate.get("max"):
            reason_parts.append(f"금리 연 {rate['min']}~{rate['max']}%")
        if kb_policy.get("loan_limit"):
            reason_parts.append(kb_policy["loan_limit"])
        if kb_policy.get("repayment"):
            reason_parts.append(kb_policy["repayment"])
        recommendations.append(
            RecommendationItem(
                type="financial_product",
                name=kb_policy["product_name"],
                reason=" | ".join(reason_parts) or "KB국민은행 소상공인 정책자금대출",
                link=kb_policy.get("url", "https://obiz.kbstar.com/quics?page=C112610"),
            )
        )

    # ── 4. 요약 문구 ─────────────────────────────────────────────────────────
    n_policy = len(semas_results) + len(bizinfo_results)
    kb_included = kb_policy.get("product_name") and intent in _LOAN_INTENTS
    n_product = len(finlife_products) + (1 if kb_included else 0)

    # intent 가 stage 기본값을 override 했으면 intent 맞춤 문구 사용
    _INTENT_SUMMARY: dict[str, str] = {
        "여유자금": "여유자금 운용을 위한 예·적금 상품을 분석했습니다.",
        "주택":     "주택 관련 담보대출 상품을 분석했습니다.",
        "상환연장": "대출 상환 부담 완화를 위한 정책 프로그램을 분석했습니다.",
        "경영비용": "경영비용 지원 바우처·정책 프로그램을 분석했습니다.",
    }
    base_summary = _INTENT_SUMMARY.get(intent) or _SUMMARY_TEMPLATE.get(stage, "금융상품 분석 결과입니다.")
    summary = f"{base_summary} 정책자금 {n_policy}건, 금융상품 {n_product}건을 확인했습니다."

    return {
        "finance_result": {
            "summary": summary,
            "recommendations": recommendations,
            "follow_up_questions": _FOLLOW_UP.get(stage, _FOLLOW_UP[BusinessStage.STARTUP.value]),
            # 디버그·다운스트림 활용 가능한 원시 데이터
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
            kb_crawler 가 KB 소상공인 정책자금대출(금리 실데이터 포함)을
            정상 반환했을 때 True 로 설정해 finlife KB 상품(금리 정보 없는
            일반신용대출 등)과의 중복을 방지한다.
            kb_crawler 결과가 비어있으면 False 로 설정해
            finlife KB 상품을 fallback 으로 포함한다.

    Returns:
        금융회사별 대표 1개씩 추린 리스트.
    """
    def _rate_key(p: dict[str, Any]) -> float:
        """정렬용 금리 키 (낮을수록 앞에 오도록)."""
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

    user_query 에 명시적 키워드(저축·예치·주택 등)가 있으면 override 한다.
    없으면 stage 기반 기본 intent(창업자금/운전자금/사업자금)를 반환한다.
    """
    q = user_query

    # 여유자금·예치 계열
    if any(kw in q for kw in ("저축", "예금", "적금", "예치", "여유자금")):
        return "여유자금"

    # 주택·부동산 계열
    if any(kw in q for kw in ("주택", "부동산", "아파트", "주담대")):
        return "주택"

    # 상환 어려움 계열 → 소진공 상환연장 우선 매칭
    if any(kw in q for kw in ("상환", "연장", "코로나", "분할상환")):
        return "상환연장"

    # 경영 바우처 계열
    if any(kw in q for kw in ("바우처", "공과금", "보험료", "경영비용")):
        return "경영비용"

    return _STAGE_INTENT.get(stage, "창업자금")
