"""FastAPI 진입점."""

import json
import logging
import time
from collections import defaultdict

from fastapi import FastAPI, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI

from project.config import settings
from project.graph import run_graph
from project.schemas import (
    BusinessContext,
    BusinessStage,
    ChatRequest,
    ChatResponse,
    CrisisInsight,
    MarketInsight,
    MarketInsightResponse,
    PolicyFundsResponse,
    ProductRecommendRequest,
    ProductRecommendResponse,
)
from project.tools import bizinfo_api, finlife_api

logger = logging.getLogger(__name__)

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

# session_id → [{"role": str, "content": str, "ts": float}, ...]
_SESSIONS: dict[str, list[dict]] = defaultdict(list)
_SESSION_TTL = 3600
_SESSION_MAX_TURNS = 6


def _trim_sessions() -> None:
    now = time.time()
    stale = [sid for sid, turns in _SESSIONS.items() if turns and now - turns[-1]["ts"] > _SESSION_TTL]
    for sid in stale:
        del _SESSIONS[sid]


def _build_augmented_message(session_id: str | None, message: str) -> str:
    if not session_id or session_id not in _SESSIONS or not _SESSIONS[session_id]:
        return message
    history = _SESSIONS[session_id][-_SESSION_MAX_TURNS:]
    lines = [f"[{h['role']}]: {h['content']}" for h in history]
    return "[이전 대화]\n" + "\n".join(lines) + f"\n\n[현재 질문]: {message}"


_CONTEXT_EXTRACT_SYSTEM = """\
사용자 메시지에서 소상공인 사업 정보를 추출하세요.
반드시 JSON만 반환하며 다음 키를 포함합니다:
- region: 지역 (예: "서울 강남구", "부산 해운대구"). 없으면 ""
- industry: 업종 (예: "카페", "한식 음식점"). 없으면 ""
- stage: "startup"(창업 준비) | "operation"(운영 중) | "expansion"(확장). 기본값 "startup"
- revenue: 월 매출 (만원 정수). 없으면 null

추출 불가능한 항목은 기본값/빈 문자열 반환. 절대 추측하지 말 것.
"""


def _enrich_context_from_message(message: str, existing: BusinessContext) -> BusinessContext:
    """메시지에서 금액·사업 정보를 보강한다."""
    from project.agents.finance import parse_amount_manwon

    amount = parse_amount_manwon(message)
    updated = existing
    if amount is not None and existing.revenue is None:
        is_loan_query = any(
            kw in message for kw in ("대출", "융자", "한도", "규모", "추천", "자금", "금융")
        )
        if not is_loan_query:
            updated = existing.model_copy(update={"revenue": amount})

    needs_region = not updated.region
    needs_industry = not updated.industry
    if not (needs_region or needs_industry):
        return updated
    if not settings.openai_api_key:
        return updated

    try:
        client = OpenAI(api_key=settings.openai_api_key)
        resp = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": _CONTEXT_EXTRACT_SYSTEM},
                {"role": "user", "content": message},
            ],
            max_tokens=120,
            temperature=0,
            response_format={"type": "json_object"},
        )
        parsed: dict = json.loads(resp.choices[0].message.content or "{}")

        region = updated.region or parsed.get("region", "")
        industry = updated.industry or parsed.get("industry", "")
        stage_raw = parsed.get("stage", updated.stage.value)
        try:
            stage = BusinessStage(stage_raw)
        except ValueError:
            stage = updated.stage
        revenue = updated.revenue if updated.revenue is not None else parsed.get("revenue")

        return BusinessContext(region=region, industry=industry, stage=stage, revenue=revenue)
    except Exception as exc:
        logger.debug("context 자동 추출 실패 (기존 값 유지): %s", exc)
        return updated


def _extract_context_from_message(message: str, existing: BusinessContext) -> BusinessContext:
    """region/industry/revenue 등 컨텍스트 보강 (LLM + 규칙)."""
    return _enrich_context_from_message(message, existing)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/v1/agent/chat", response_model=ChatResponse)
async def agent_chat(
    request: ChatRequest,
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
) -> ChatResponse:
    _trim_sessions()
    context = _extract_context_from_message(request.message, request.context)
    augmented = _build_augmented_message(x_session_id, request.message)
    result = await run_graph(augmented, context, user_query=augmented)
    insights_data = result.get("insights") or {}

    answer = result.get("final_answer", "")

    if x_session_id is not None:
        ts = time.time()
        _SESSIONS[x_session_id].append({"role": "user", "content": request.message, "ts": ts})
        _SESSIONS[x_session_id].append({"role": "assistant", "content": answer, "ts": ts})

    crisis_data = insights_data.get("crisis")
    crisis_insight = None
    if isinstance(crisis_data, dict) and crisis_data.get("summary"):
        crisis_insight = CrisisInsight(
            level=crisis_data.get("level", "normal"),
            score=float(crisis_data.get("score", 0)),
            summary=crisis_data.get("summary", ""),
            recommended_actions=crisis_data.get("recommended_actions", []),
            growth_market_names=crisis_data.get("growth_market_names", []),
        )

    return ChatResponse(
        answer=answer,
        insights=MarketInsight(
            market_summary=insights_data.get("market_summary", ""),
            economic_indicator=insights_data.get("economic_indicator", ""),
            consumption_trend=insights_data.get("consumption_trend", ""),
            crisis=crisis_insight,
            sales_data_note=insights_data.get("sales_data_note", ""),
        ),
        recommendations=result.get("recommendations", []),
        follow_up_questions=result.get("follow_up_questions", []),
        active_agents=result.get("active_agents", []),
    )


@app.get("/api/v1/market/insights", response_model=MarketInsightResponse)
async def market_insights(
    region: str = Query(default="서울 강남구"),
    industry: str = Query(default="카페"),
):
    from project.agents.commercial import commercial_node
    from project.agents.economic import economic_node
    from project.state import AgentState

    ctx = BusinessContext(region=region, industry=industry, stage=BusinessStage.STARTUP)
    base_state: AgentState = {
        "messages": [],
        "context": ctx,
        "user_query": "",
        "active_agents": ["commercial", "economic"],
        "commercial_result": {},
        "economic_result": {},
        "finance_result": {},
        "crisis_result": {},
        "insights": {},
        "recommendations": [],
        "follow_up_questions": [],
        "final_answer": "",
    }
    commercial_out = commercial_node(base_state)
    economic_out = economic_node({**base_state, **commercial_out})
    commercial = commercial_out.get("commercial_result") or {}
    economic = economic_out.get("economic_result") or {}

    return MarketInsightResponse(
        region=region,
        industry=industry,
        market_summary=commercial.get("summary", ""),
        economic_indicator=economic.get("indicator", "경기지표 분석 결과 없음"),
        consumption_trend=economic.get("consumption_trend", "소비 트렌드 분석 결과 없음"),
        score=float(commercial.get("score") or 0),
    )


@app.get("/api/v1/policy/funds", response_model=PolicyFundsResponse)
async def policy_funds(
    stage: BusinessStage | None = Query(default=None),
    region: str = Query(default=""),
):
    from project.schemas import PolicyFundItem

    stage_intent_map = {
        BusinessStage.STARTUP.value:   "창업자금",
        BusinessStage.OPERATION.value: "운전자금",
        BusinessStage.EXPANSION.value: "사업자금",
    }
    intent = stage_intent_map.get(stage.value if stage else "", "창업자금")
    items_raw: list[dict] = bizinfo_api.search_support_programs(intent=intent, region=region)
    items = [
        PolicyFundItem(
            id=f"policy-{i}",
            name=item.get("title", item.get("name", "")),
            description=item.get("summary", item.get("description", "")),
            eligibility="",
            max_amount=item.get("max_amount", ""),
            stage=stage or BusinessStage.STARTUP,
            link=item.get("url", item.get("link", "")),
        )
        for i, item in enumerate(items_raw)
    ]
    return PolicyFundsResponse(items=items)


@app.post("/api/v1/recommend/products", response_model=ProductRecommendResponse)
async def recommend_products(request: ProductRecommendRequest) -> ProductRecommendResponse:
    from project.schemas import RecommendationItem

    stage_intent_map = {
        BusinessStage.STARTUP.value:   "창업자금",
        BusinessStage.OPERATION.value: "운전자금",
        BusinessStage.EXPANSION.value: "사업자금",
    }
    intent = stage_intent_map.get(request.stage.value if request.stage else "", "창업자금")
    data = finlife_api.search_finance_products(intent=intent)
    items = [
        RecommendationItem(
            type="financial_product",
            name=prod.get("product_name", ""),
            reason=f"대출금리 연 {prod['lend_rate_min']}~{prod['lend_rate_max']}%" if prod.get("lend_rate_min") else "",
            link="https://finlife.fss.or.kr",
        )
        for prod in data.get("products", [])[:6]
    ]
    return ProductRecommendResponse(items=items)
