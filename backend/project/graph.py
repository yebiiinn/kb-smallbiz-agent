"""LangGraph 오케스트레이터 — 팀원과 함께 확장."""

import json
import logging

from langgraph.graph import END, START, StateGraph
from openai import OpenAI

from project.agents.commercial import commercial_node
from project.agents.crisis import crisis_node
from project.agents.economic import economic_node
from project.agents.finance import finance_node
from project.agents.router import ALL_AGENTS, router_node
from project.config import settings
from project.state import AgentState

logger = logging.getLogger(__name__)

_SYNTHESIZE_SYSTEM = """\
당신은 KB 소상공인 금융 지원 전문 컨설턴트입니다.
아래 분석 결과를 종합해 소상공인에게 실질적인 컨설팅 답변을 작성하세요.

규칙:
- 상권·경기·위기·금융 결과를 자연스럽게 연결해 서술 (나열 금지)
- 지역·업종·사업 단계를 구체적으로 언급
- 위기 신호(warning/critical)가 있으면 반드시 언급하고 대응 방향 제시
- 금융 추천 건수와 핵심 상품 유형을 간략히 안내
- 4~6문장, 실용적이고 간결하게
- 이모지 섞어서 가독성 높게 (📊 📈 ⚠️ 💰 등)
- 마지막 줄: 추천 N건은 오른쪽 패널에서 확인 안내
"""


def _llm_synthesize(
    region: str,
    industry: str,
    stage: str,
    commercial: dict,
    economic: dict,
    finance: dict,
    crisis: dict,
) -> str:
    """4-agent 결과를 LLM으로 종합해 자연어 컨설팅 답변을 생성한다."""
    if not settings.openai_api_key:
        return _template_answer(region, industry, stage, commercial, economic, finance, crisis)

    crisis_level = crisis.get("level", "normal")
    recommendations = finance.get("recommendations", [])

    context_block = json.dumps(
        {
            "지역": region,
            "업종": industry,
            "사업단계": stage,
            "상권요약": commercial.get("summary", ""),
            "상권점수": commercial.get("score"),
            "경기지표": economic.get("indicator", ""),
            "소비트렌드": economic.get("consumption_trend", ""),
            "위기등급": crisis_level,
            "위기요약": crisis.get("summary", ""),
            "위기권고행동": (crisis.get("recommended_actions") or [])[:3],
            "금융추천건수": len(recommendations),
            "추천상품유형": list({r.type for r in recommendations}) if recommendations else [],
            "금융요약": finance.get("summary", ""),
        },
        ensure_ascii=False,
        indent=2,
    )

    try:
        client = OpenAI(api_key=settings.openai_api_key)
        resp = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": _SYNTHESIZE_SYSTEM},
                {"role": "user", "content": f"[분석 데이터]\n{context_block}"},
            ],
            max_tokens=400,
            temperature=0.5,
        )
        answer = (resp.choices[0].message.content or "").strip()
        if answer:
            return answer
    except Exception as exc:
        logger.warning("synthesize LLM 실패 (템플릿 fallback): %s", exc)

    return _template_answer(region, industry, stage, commercial, economic, finance, crisis)


def _template_answer(
    region: str,
    industry: str,
    stage: str,
    commercial: dict,
    economic: dict,
    finance: dict,
    crisis: dict,
    active_agents: list[str] | None = None,
) -> str:
    """LLM 실패 또는 단일 에이전트 응답용 템플릿."""
    active = active_agents or list(ALL_AGENTS)
    recommendations = finance.get("recommendations", []) if "finance" in active else []
    crisis_level = crisis.get("level", "normal") if "crisis" in active else "normal"

    if active == ["finance"]:
        intro = f"{region} {industry} ({stage}) 기준으로 금융상품을 분석했습니다."
    elif active == ["commercial"]:
        intro = f"{region} {industry} ({stage}) 상권을 분석했습니다."
    elif active == ["economic"]:
        intro = f"{industry} 업종 기준으로 경기·소비 환경을 분석했습니다."
    elif active == ["commercial", "economic", "crisis"]:
        intro = f"{region} {industry} ({stage}) 기준으로 위기진단을 분석했습니다."
    else:
        intro = f"{region or '해당 지역'} {industry or '업종'} ({stage}) 기준으로 분석했습니다."

    parts = [intro]

    if "commercial" in active and commercial.get("summary"):
        if active == ["commercial"]:
            parts.append("\n\n상세 분석은 오른쪽 **시장 인사이트** 패널에서 확인해 주세요.")
        else:
            parts.append(_format_section("📊 상권", commercial.get("summary", "")))
    if "economic" in active and economic.get("indicator"):
        parts.append(_format_section("📈 경기", economic.get("indicator", "")))
    if "economic" in active and economic.get("consumption_trend"):
        parts.append(_format_section("🛒 소비", economic.get("consumption_trend", "")))
    if "crisis" in active:
        if crisis_level != "normal":
            parts.append(f"\n\n### ⚠️ 위기진단\n- {crisis.get('summary', '')}")
        elif active == ["commercial", "economic", "crisis"]:
            parts.append(f"\n\n### ✅ 위기진단\n- {crisis.get('summary', '현재 특별한 위기 신호 없음')}")
    if recommendations:
        parts.append(f"\n\n💰 **추천 {len(recommendations)}건** — 오른쪽 패널을 확인해 주세요.")

    return "".join(parts)


def _format_bullets(text: str, separators: tuple[str, ...] = (" / ", " | ")) -> str:
    """슬래시·파이프 구분 텍스트를 마크다운 bullet 목록으로 변환."""
    if not text:
        return ""
    if text.strip().startswith("- "):
        return text.strip()
    for separator in separators:
        if separator in text:
            items = [item.strip() for item in text.split(separator) if item.strip()]
            return "\n".join(f"- {item}" for item in items)
    return f"- {text.strip()}"


def _format_section(title: str, body: str) -> str:
    formatted = _format_bullets(body)
    if not formatted:
        return ""
    return f"\n\n### {title}\n{formatted}"


def _is_active(state: AgentState, agent: str) -> bool:
    active_agents = state.get("active_agents") or list(ALL_AGENTS)
    return agent in active_agents


def _maybe_commercial_node(state: AgentState) -> dict:
    if _is_active(state, "commercial"):
        return commercial_node(state)
    return {}


def _maybe_economic_node(state: AgentState) -> dict:
    if _is_active(state, "economic"):
        return economic_node(state)
    return {}


def _maybe_finance_node(state: AgentState) -> dict:
    if _is_active(state, "finance"):
        return finance_node(state)
    return {}


def _maybe_crisis_node(state: AgentState) -> dict:
    if _is_active(state, "crisis"):
        return crisis_node(state)
    return {}


def synthesize_node(state: AgentState) -> dict:
    """활성화된 에이전트 결과를 종합해 최종 답변을 생성."""
    ctx = state["context"]
    active_agents = state.get("active_agents") or list(ALL_AGENTS)
    commercial = state.get("commercial_result") or {}
    economic = state.get("economic_result") or {}
    finance = state.get("finance_result") or {}
    crisis = state.get("crisis_result") or {}

    insights: dict[str, str] = {}
    if "commercial" in active_agents:
        insights["market_summary"] = commercial.get("summary", "상권 분석 결과 없음")
    if "economic" in active_agents:
        insights["economic_indicator"] = _format_bullets(
            economic.get("indicator", "경기지표 분석 결과 없음")
        )
        insights["consumption_trend"] = _format_bullets(
            economic.get("consumption_trend", "소비 트렌드 분석 결과 없음")
        )

    recommendations = finance.get("recommendations", []) if "finance" in active_agents else []

    region_label = ctx.region or "해당 지역"
    industry_label = ctx.industry or "업종"
    stage_label = ctx.stage.value

    if active_agents == list(ALL_AGENTS):
        final_answer = _llm_synthesize(
            region=region_label,
            industry=industry_label,
            stage=stage_label,
            commercial=commercial,
            economic=economic,
            finance=finance,
            crisis=crisis,
        )
    else:
        final_answer = _template_answer(
            region_label,
            industry_label,
            stage_label,
            commercial,
            economic,
            finance,
            crisis,
            active_agents=active_agents,
        )

    follow_up = finance.get("follow_up_questions")
    if not follow_up:
        follow_up = [
            "예상 창업/운영 자본금은 얼마인가요?",
            "대출 상환 기간은 어떻게 생각하고 계신가요?",
        ]

    return {
        "insights": insights,
        "recommendations": recommendations,
        "follow_up_questions": follow_up,
        "final_answer": final_answer,
    }


def build_graph():
    """멀티 에이전트 그래프 구성.

    실행 순서:
        START → router → commercial ┐
                         economic  ┘ (병렬) → crisis → finance → synthesize → END
    """
    graph = StateGraph(AgentState)

    graph.add_node("router", router_node)
    graph.add_node("commercial", _maybe_commercial_node)
    graph.add_node("economic", _maybe_economic_node)
    graph.add_node("crisis", _maybe_crisis_node)
    graph.add_node("finance", _maybe_finance_node)
    graph.add_node("synthesize", synthesize_node)

    graph.add_edge(START, "router")
    graph.add_edge("router", "commercial")
    graph.add_edge("router", "economic")
    graph.add_edge("commercial", "crisis")
    graph.add_edge("economic", "crisis")
    graph.add_edge("crisis", "finance")
    graph.add_edge("finance", "synthesize")
    graph.add_edge("synthesize", END)

    return graph.compile()


agent_graph = build_graph()


async def run_graph(message: str, context) -> dict:
    """그래프 실행 헬퍼."""
    initial: AgentState = {
        "messages": [],
        "context": context,
        "user_query": message,
        "active_agents": [],
        "commercial_result": {},
        "economic_result": {},
        "finance_result": {},
        "crisis_result": {},
        "insights": {},
        "recommendations": [],
        "follow_up_questions": [],
        "final_answer": "",
    }
    return await agent_graph.ainvoke(initial)
