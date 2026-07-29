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
    MarketInsight,
    MarketInsightResponse,
    PolicyFundsResponse,
    ProductRecommendRequest,
    ProductRecommendResponse,
)
from project.tools import bizinfo_api, ecos_api, finlife_api, sangkwon_api
from project.tools import kosis_api

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


def _extract_context_from_message(message: str, existing: BusinessContext) -> BusinessContext:
    """region 또는 industry가 비어있을 때만 LLM으로 메시지에서 추출한다."""
    needs_region = not existing.region
    needs_industry = not existing.industry
    if not (needs_region or needs_industry):
        return existing
    if not settings.openai_api_key:
        return existing

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

        region = existing.region or parsed.get("region", "")
        industry = existing.industry or parsed.get("industry", "")
        stage_raw = parsed.get("stage", existing.stage.value)
        try:
            stage = BusinessStage(stage_raw)
        except ValueError:
            stage = existing.stage
        revenue = existing.revenue if existing.revenue is not None else parsed.get("revenue")

        return BusinessContext(region=region, industry=industry, stage=stage, revenue=revenue)
    except Exception as exc:
        logger.debug("context 자동 추출 실패 (기존 값 유지): %s", exc)
        return existing


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
    result = await run_graph(augmented, context)
    insights_data = result.get("insights") or {}

    answer = result.get("final_answer", "")

    if x_session_id is not None:
        ts = time.time()
        _SESSIONS[x_session_id].append({"role": "user", "content": request.message, "ts": ts})
        _SESSIONS[x_session_id].append({"role": "assistant", "content": answer, "ts": ts})

    return ChatResponse(
        answer=answer,
        insights=MarketInsight(
            market_summary=insights_data.get("market_summary", ""),
            economic_indicator=insights_data.get("economic_indicator", ""),
            consumption_trend=insights_data.get("consumption_trend", ""),
        ),
        recommendations=result.get("recommendations", []),
        follow_up_questions=result.get("follow_up_questions", []),
    )


@app.get("/api/v1/market/insights", response_model=MarketInsightResponse)
async def market_insights(
    region: str = Query(default="서울 강남구"),
    industry: str = Query(default="카페"),
):
    data = sangkwon_api.fetch_commercial_district(region=region, industry=industry)

    ecos_data = ecos_api.fetch_economic_indicators()
    kosis_data = kosis_api.fetch_consumption_trend(region=region, industry=industry)

    csi = ecos_data.get("consumer_sentiment")
    base_rate = ecos_data.get("base_rate")
    econ_parts = []
    if base_rate is not None:
        econ_parts.append(f"기준금리 {base_rate:.2f}%")
    if csi is not None:
        sentiment = "위축" if csi < 95 else ("보통" if csi < 105 else "양호")
        econ_parts.append(f"CSI {csi:.0f}({sentiment})")
    economic_indicator = " / ".join(econ_parts) if econ_parts else ecos_data.get("summary", "경기지표 조회 완료")

    consumption_trend = kosis_data.get("summary", kosis_data.get("consumption_trend", "소비 트렌드 조회 완료"))

    return MarketInsightResponse(
        region=region,
        industry=industry,
        market_summary=data.get("summary", ""),
        economic_indicator=economic_indicator,
        consumption_trend=consumption_trend,
        score=float(data.get("score", 0)),
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
