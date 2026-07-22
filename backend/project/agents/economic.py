"""경기지표·소비트렌드 에이전트 — 담당자 A or B.

API:
- 한국은행 ECOS API  (tools/ecos_api.py)
- 통계청 KOSIS API   (tools/kosis_api.py)

데이터 참조:
- project/data/indicator_mapping.json
  업종-지표 상관관계 매핑표. 모듈 로딩 시 1회 읽어 캐시.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from openai import OpenAI

from project.config import settings
from project.state import AgentState
from project.tools import ecos_api, kosis_api

# ── indicator_mapping.json 1회 로딩 ────────────────────────────────────────────
_MAPPING_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "indicator_mapping.json"
)


def _load_mapping() -> dict:
    try:
        with open(_MAPPING_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


_MAPPING: dict = _load_mapping()


# ── 헬퍼: 업종 키워드 감지 ────────────────────────────────────────────────────

def _detect_industry_key(industry: str) -> str:
    """사용자 업종 텍스트 → indicator_mapping 분류키 변환.

    industry_keyword_map 을 순회하며 키워드가 포함되면 해당 분류키 반환.
    매칭 실패 시 기본값 '음식점주점' 반환.
    """
    keyword_map: dict[str, str] = _MAPPING.get("industry_keyword_map", {})
    for keyword, key in keyword_map.items():
        if keyword in industry:
            return key
    return "음식점주점"


# ── 헬퍼: 최근 3개월 기간 계산 ───────────────────────────────────────────────

def _recent_period() -> tuple[str, str]:
    """(start, end) 형식의 YYYYMM 문자열 반환. ECOS·KOSIS 공통 사용."""
    today = datetime.today()
    end = today.strftime("%Y%m")
    start = (today - timedelta(days=90)).strftime("%Y%m")
    return start, end


# ── 헬퍼: ECOS 지표 최신값 조회 ──────────────────────────────────────────────

def _fetch_ecos_values(indicator_names: list[str]) -> dict[str, float | None]:
    """지표명 목록의 ECOS 최신값을 조회해 {지표명: 값} 딕셔너리로 반환.

    API 키 없거나 조회 실패 시 None 값으로 채움.
    """
    ecos_cfg: dict[str, dict] = _MAPPING.get("ecos_indicators", {})
    start, end = _recent_period()
    result: dict[str, float | None] = {}

    for name in indicator_names:
        cfg = ecos_cfg.get(name)
        if not cfg:
            result[name] = None
            continue
        series = ecos_api.fetch_indicator_series(
            stat_code=cfg["stat_code"],
            item_code=cfg["item_code"],
            item_code2=cfg.get("item_code2", ""),
            cycle=cfg.get("cycle", "M"),
            start=start,
            end=end,
        )
        result[name] = series[-1]["value"] if series else None

    return result


# ── 헬퍼: KOSIS 지표 최신값 조회 ─────────────────────────────────────────────

def _fetch_kosis_values(indicator_names: list[str]) -> dict[str, float | None]:
    """지표명 목록의 KOSIS 최신값을 조회해 {지표명: 값} 딕셔너리로 반환."""
    kosis_cfg: dict[str, dict] = _MAPPING.get("kosis_indicators", {})
    start, end = _recent_period()
    result: dict[str, float | None] = {}

    for name in indicator_names:
        cfg = kosis_cfg.get(name)
        if not cfg:
            result[name] = None
            continue
        series = kosis_api.fetch_indicator_series(
            tbl_id=cfg["tbl_id"],
            itm_id=cfg["itm_id"],
            obj_l1=cfg["obj_l1"],
            org_id=cfg.get("org_id", "101"),
            prd_se=cfg.get("prd_se", "M"),
            start=start,
            end=end,
        )
        result[name] = series[-1]["value"] if series else None

    return result


# ── 헬퍼: 기준금리 방향성 자동 감지 ──────────────────────────────────────────

def _fetch_rate_direction() -> str:
    """ECOS API에서 최근 2개월 기준금리를 비교해 방향성 반환.

    Returns
    -------
    "인상" | "인하" | "동결"
    금리가 얼마든 코드 수정 없이 자동 판단. API 조회 실패 시 "동결" 반환.
    """
    cfg = _MAPPING.get("ecos_indicators", {}).get("기준금리", {})
    if not cfg:
        return "동결"

    today = datetime.today()
    end = today.strftime("%Y%m")
    start = (today - timedelta(days=65)).strftime("%Y%m")  # 최근 2개월 확보

    series = ecos_api.fetch_indicator_series(
        stat_code=cfg["stat_code"],
        item_code=cfg["item_code"],
        item_code2=cfg.get("item_code2", ""),
        cycle="M",
        start=start,
        end=end,
    )

    if not series or len(series) < 2:
        return "동결"

    current = series[-1]["value"]
    previous = series[-2]["value"]

    if current > previous:
        return "인상"
    elif current < previous:
        return "인하"
    else:
        return "동결"


# ── 헬퍼: 거시 시나리오 판별 ─────────────────────────────────────────────────

def _detect_scenarios(
    ecos_values: dict[str, float | None],
    kosis_values: dict[str, float | None],
    rate_direction: str,
) -> list[str]:
    """현재 지표값으로 macro_interpretation 키 목록을 반환.

    기준금리 방향성은 절댓값 임계치 대신 _fetch_rate_direction() 비교 결과를 사용.
    나머지 지표는 경제적 통념에 근거한 임계치 적용.
    - 현재경기판단CSI ≥ 100 → 소비심리_개선_시
    - 실업률 > 4.0%         → 실업률_상승_시
    - 원달러환율 > 1350      → 환율_상승_시
    """
    scenarios: list[str] = []

    # 기준금리: 절댓값이 아니라 전월 대비 방향으로 판단
    if rate_direction == "인상":
        scenarios.append("기준금리_인상_시")
    elif rate_direction == "인하":
        scenarios.append("기준금리_인하_시")
    else:
        scenarios.append("기준금리_동결_시")

    csi = ecos_values.get("현재경기판단CSI")
    if csi is not None and csi >= 100:
        scenarios.append("소비심리_개선_시")

    unemp = kosis_values.get("실업률")
    if unemp is not None and unemp > 4.0:
        scenarios.append("실업률_상승_시")

    fx = ecos_values.get("원달러환율")
    if fx is not None and fx > 1350:
        scenarios.append("환율_상승_시")

    return scenarios


# ── 헬퍼: 경기지표 요약 문장 생성 ────────────────────────────────────────────

def _build_indicator_summary(
    industry_key: str,
    ecos_values: dict[str, float | None],
    active_scenarios: list[str],
) -> str:
    """ECOS 최신값 + 시나리오 효과를 결합한 경기지표 요약 문장."""
    parts: list[str] = []

    rate = ecos_values.get("기준금리")
    csi = ecos_values.get("현재경기판단CSI")
    outlook_csi = ecos_values.get("향후경기전망CSI")
    dining_csi = ecos_values.get("외식비지출전망CSI")
    bsi = ecos_values.get("BSI_서비스업전망")

    if rate is not None:
        parts.append(f"기준금리 {rate:.2f}%")

    if csi is not None:
        mood = "긍정" if csi >= 100 else "부정"
        parts.append(f"현재경기판단CSI {csi:.0f}({mood})")

    if outlook_csi is not None:
        parts.append(f"향후경기전망CSI {outlook_csi:.0f}")

    # 업종 특화 지표
    if industry_key == "음식점주점" and dining_csi is not None:
        trend = "개선" if dining_csi >= 100 else "위축"
        parts.append(f"외식비지출전망CSI {dining_csi:.0f}(외식소비 {trend})")

    if bsi is not None:
        parts.append(f"BSI_서비스업전망 {bsi:.0f}")

    # 거시 시나리오 효과 추가
    macro_interp: dict = _MAPPING.get("macro_interpretation", {})
    for scenario_key in active_scenarios:
        effect = macro_interp.get(scenario_key, {}).get("effect", "")
        if effect:
            parts.append(effect)

    return " / ".join(parts) if parts else "경기지표 조회 중"


# ── 헬퍼: 소비 트렌드 요약 문장 생성 ────────────────────────────────────────

def _build_consumption_summary(
    industry_key: str,
    kosis_values: dict[str, float | None],
    active_scenarios: list[str],
) -> str:
    """KOSIS 최신값 + 업종별 상관관계 해석을 결합한 소비 트렌드 요약 문장."""
    corr: dict = (
        _MAPPING.get("industry_indicator_correlation", {}).get(industry_key, {})
    )
    parts: list[str] = []

    # 업종별 양의 상관 지표 값 + 해석
    for item in corr.get("top_positive", [])[:2]:
        name = item["indicator"]
        val = kosis_values.get(name)
        interp = item.get("interpretation", "")
        if val is not None:
            parts.append(f"{name} {val:.1f} — {interp}")

    # 에이전트 판단 신호
    agent_signal = corr.get("agent_signal", "")
    if agent_signal:
        parts.append(f"[판단신호] {agent_signal}")

    # 거시 시나리오: 수혜·위험 업종 여부 표시
    macro_interp: dict = _MAPPING.get("macro_interpretation", {})
    for scenario_key in active_scenarios:
        scenario = macro_interp.get(scenario_key, {})
        beneficiaries: list[str] = scenario.get("beneficiary", [])
        risks: list[str] = scenario.get("risk", [])

        if industry_key in beneficiaries:
            parts.append(f"현재 국면에서 '{industry_key}' 수혜 업종")

        for risk_desc in risks:
            if industry_key in risk_desc:
                parts.append(f"주의: {risk_desc}")

    return " | ".join(parts) if parts else "소비 트렌드 조회 중"


# ── LLM 자연어 해석 ───────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """당신은 소상공인 경기 분석 전문가입니다.
한국은행(ECOS)·통계청(KOSIS) 지표 데이터와 업종별 상관분석 결과를 바탕으로,
소상공인이 자신의 업종에 맞는 경기 흐름을 쉽게 이해할 수 있도록 분석합니다.

답변 규칙:
- 반드시 한국어로 작성합니다.
- 전문 용어는 괄호로 쉽게 풀어 씁니다. 예: CSI(소비자심리지수)
- 경기가 악화되는 상황이면 "하락" 또는 "위축"이라는 단어를 자연스럽게 포함합니다.
- 경기가 개선되는 상황이면 "개선" 또는 "회복"이라는 단어를 포함합니다.
- 2~3문장으로 간결하게 작성합니다. 불필요한 수식어는 생략합니다."""

_USER_PROMPT_TEMPLATE = """다음 정보를 바탕으로 {industry} 업종({region}) 소상공인을 위한 경기 분석을 작성해주세요.

## 현재 주요 경기지표
{ecos_lines}

## {industry} 업종 관련 실물지표
{kosis_lines}

## 업종별 상관분석 인사이트
- 업종 요약: {industry_summary}
- 판단 신호: {agent_signal}

## 현재 해당되는 거시경제 시나리오
{scenario_lines}

위 정보를 종합해 {industry} 업종 소상공인 관점에서 현재 경기 상황과 주의할 점을 2~3문장으로 설명해주세요."""


def _format_ecos_lines(ecos_values: dict[str, float | None]) -> str:
    """ECOS 지표값을 LLM 프롬프트용 텍스트로 변환."""
    unit_map = {
        "기준금리": "%",
        "소비자물가지수": "(2020=100)",
        "생산자물가지수": "(2020=100)",
        "원달러환율": "원/달러",
        "현재경기판단CSI": "(100 초과=긍정)",
        "향후경기전망CSI": "(100 초과=긍정)",
        "외식비지출전망CSI": "(100 초과=긍정)",
        "BSI_서비스업전망": "(100 초과=긍정)",
    }
    lines = []
    for name, val in ecos_values.items():
        if val is not None:
            unit = unit_map.get(name, "")
            lines.append(f"- {name}: {val:.2f} {unit}")
    return "\n".join(lines) if lines else "- 조회 중"


def _format_kosis_lines(kosis_values: dict[str, float | None]) -> str:
    """KOSIS 지표값을 LLM 프롬프트용 텍스트로 변환."""
    lines = []
    for name, val in kosis_values.items():
        if val is not None:
            lines.append(f"- {name}: {val:.1f} (2020=100 불변지수)")
    return "\n".join(lines) if lines else "- 조회 중"


def _format_scenario_lines(
    active_scenarios: list[str],
    macro_interp: dict,
    industry_key: str,
) -> str:
    """현재 시나리오의 효과·수혜·위험을 텍스트로 변환."""
    if not active_scenarios:
        return "- 특별한 거시경제 이벤트 없음"
    lines = []
    for key in active_scenarios:
        scenario = macro_interp.get(key, {})
        effect = scenario.get("effect", "")
        beneficiaries: list[str] = scenario.get("beneficiary", [])
        risks: list[str] = scenario.get("risk", [])

        label = key.replace("_", " ")
        if effect:
            lines.append(f"- [{label}] {effect}")
        if industry_key in beneficiaries:
            lines.append(f"  → '{industry_key}' 수혜 업종에 해당")
        for risk_desc in risks:
            if industry_key in risk_desc:
                lines.append(f"  → 주의: {risk_desc}")
    return "\n".join(lines) if lines else "- 특별한 거시경제 이벤트 없음"


def _call_llm_summary(
    industry: str,
    region: str,
    industry_key: str,
    ecos_values: dict[str, float | None],
    kosis_values: dict[str, float | None],
    active_scenarios: list[str],
    corr_cfg: dict,
) -> str | None:
    """OpenAI API로 업종 맞춤 경기 해석 생성.

    API 키 없거나 호출 실패 시 None 반환 → 호출부에서 fallback 처리.
    """
    if not settings.openai_api_key:
        return None

    macro_interp: dict = _MAPPING.get("macro_interpretation", {})
    user_prompt = _USER_PROMPT_TEMPLATE.format(
        industry=industry or industry_key,
        region=region or "전국",
        ecos_lines=_format_ecos_lines(ecos_values),
        kosis_lines=_format_kosis_lines(kosis_values),
        industry_summary=corr_cfg.get("summary", "해당 업종 분석 데이터 없음"),
        agent_signal=corr_cfg.get("agent_signal", "없음"),
        scenario_lines=_format_scenario_lines(
            active_scenarios, macro_interp, industry_key
        ),
    )

    try:
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=300,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return None


# ── 메인 노드 ─────────────────────────────────────────────────────────────────

def economic_node(state: AgentState) -> dict:
    """경기지표·소비트렌드 분석 노드.

    실행 순서
    ---------
    1. 업종 키워드 감지 → indicator_mapping.json 분류키 확정
    2. 핵심 ECOS 거시지표 최신값 조회
    3. 업종별 상관 높은 KOSIS 지표 최신값 조회
    4. 거시 시나리오 판별 (금리·CSI·실업률·환율 기준)
    5. 경기지표 요약 + 소비 트렌드 요약 문장 생성
    6. API 키 없거나 전부 None이면 fallback 결과 반환
    """
    ctx = state["context"]
    commercial = state.get("commercial_result") or {}
    region = ctx.region or commercial.get("region", "")
    industry = ctx.industry or commercial.get("industry", "")

    # 1. 업종 분류
    industry_key = _detect_industry_key(industry)

    # 2. ECOS 핵심 거시지표 조회 (업종 공통 + 업종 특화)
    ecos_targets = [
        "기준금리", "소비자물가지수", "생산자물가지수", "원달러환율",
        "현재경기판단CSI", "향후경기전망CSI",
        "외식비지출전망CSI", "BSI_서비스업전망",
    ]
    ecos_values = _fetch_ecos_values(ecos_targets)

    # 3. 업종별 상관 높은 KOSIS 지표 조회
    #    industry_indicator_correlation 의 top_positive 목록 중 KOSIS 지표만 선택
    kosis_cfg = _MAPPING.get("kosis_indicators", {})
    corr_cfg: dict = (
        _MAPPING.get("industry_indicator_correlation", {}).get(industry_key, {})
    )
    kosis_targets: list[str] = [
        item["indicator"]
        for item in corr_cfg.get("top_positive", [])
        if item["indicator"] in kosis_cfg
    ]
    if not kosis_targets:
        kosis_targets = ["서비스업생산_총지수"]

    # 실업률은 시나리오 판별에도 필요하므로 항상 포함
    if "실업률" not in kosis_targets:
        kosis_targets.append("실업률")

    kosis_values = _fetch_kosis_values(kosis_targets)

    # 4. 거시 시나리오 판별
    rate_direction = _fetch_rate_direction()
    active_scenarios = _detect_scenarios(ecos_values, kosis_values, rate_direction)

    # 5. 원시 요약 문장 생성 (LLM fallback 용)
    raw_indicator = _build_indicator_summary(
        industry_key, ecos_values, active_scenarios
    )
    raw_consumption = _build_consumption_summary(
        industry_key, kosis_values, active_scenarios
    )

    # 6. API 키 없어서 전부 None인 경우 → legacy fallback
    all_none = all(v is None for v in {**ecos_values, **kosis_values}.values())
    if all_none:
        fallback_ecos = ecos_api.fetch_economic_indicators()
        fallback_kosis = kosis_api.fetch_consumption_trend(
            region=region, industry=industry
        )
        raw_indicator = fallback_ecos.get("summary", raw_indicator)
        raw_consumption = fallback_kosis.get("summary", raw_consumption)

    # 7. LLM 자연어 해석 생성
    #    성공 시 indicator 필드를 자연어 텍스트로 교체, 실패 시 raw 요약 사용
    llm_summary = _call_llm_summary(
        industry=industry,
        region=region,
        industry_key=industry_key,
        ecos_values=ecos_values,
        kosis_values=kosis_values,
        active_scenarios=active_scenarios,
        corr_cfg=corr_cfg,
    )
    indicator_summary = llm_summary if llm_summary else raw_indicator

    return {
        "economic_result": {
            # synthesize_node + crisis_node 가 직접 참조하는 핵심 필드
            "indicator": indicator_summary,
            "consumption_trend": raw_consumption,
            # 분석 메타
            "industry_key": industry_key,
            "active_scenarios": active_scenarios,
            "consumer_sentiment": ecos_values.get("현재경기판단CSI"),
            "consumption_growth_rate": None,
            # 원시 데이터 (디버깅·고도화용)
            "raw": {
                "ecos": ecos_values,
                "kosis": kosis_values,
                "rate_direction": rate_direction,
                "raw_indicator": raw_indicator,
                "agent_signal": corr_cfg.get("agent_signal", ""),
                "industry_summary": corr_cfg.get("summary", ""),
            },
        }
    }
