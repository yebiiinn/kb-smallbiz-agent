"""LangGraph 오케스트레이터 — 팀원과 함께 확장."""

from langgraph.graph import END, START, StateGraph

from project.agents.commercial import commercial_node
from project.agents.crisis import crisis_node
from project.agents.economic import economic_node
from project.agents.finance import finance_node
from project.agents.router import ALL_AGENTS, router_node
from project.state import AgentState


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
    """활성화된 에이전트 결과만 종합해 최종 답변을 생성."""
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
    crisis_level = crisis.get("level", "normal") if "crisis" in active_agents else "normal"

    region_label = ctx.region or "해당 지역"
    industry_label = ctx.industry or "업종"
    stage_label = ctx.stage.value

    if active_agents == ["finance"]:
        intro = f"{region_label} {industry_label} ({stage_label}) 기준으로 금융상품을 분석했습니다."
    elif len(active_agents) == 1 and active_agents[0] == "commercial":
        intro = f"{region_label} {industry_label} ({stage_label}) 상권을 분석했습니다."
    elif len(active_agents) == 1 and active_agents[0] == "economic":
        intro = f"{industry_label} 업종 기준으로 경기·소비 환경을 분석했습니다."
    elif active_agents == ["commercial", "economic", "crisis"]:
        intro = f"{region_label} {industry_label} ({stage_label}) 기준으로 위기진단을 분석했습니다."
    else:
        intro = f"{region_label} {industry_label} ({stage_label}) 기준으로 분석했습니다."

    answer_parts = [intro]

    if "commercial" in active_agents and commercial.get("summary"):
        if active_agents == ["commercial"]:
            answer_parts.append("\n\n상세 분석은 오른쪽 **시장 인사이트** 패널에서 확인해 주세요.")
        else:
            answer_parts.append(_format_section("📊 상권", commercial.get("summary", "")))
    if "economic" in active_agents and economic.get("indicator"):
        answer_parts.append(_format_section("📈 경기", economic.get("indicator", "")))
    if "economic" in active_agents and economic.get("consumption_trend"):
        answer_parts.append(_format_section("🛒 소비", economic.get("consumption_trend", "")))
    if "crisis" in active_agents and crisis_level != "normal":
        answer_parts.append(f"\n\n### ⚠️ 위기진단\n- {crisis.get('summary', '')}")
    if recommendations:
        answer_parts.append(f"\n\n💰 **추천 {len(recommendations)}건** — 오른쪽 패널을 확인해 주세요.")

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
        "final_answer": "".join(answer_parts),
    }


def build_graph():
    """멀티 에이전트 그래프 구성."""
    graph = StateGraph(AgentState)

    graph.add_node("router", router_node)
    graph.add_node("commercial", _maybe_commercial_node)
    graph.add_node("economic", _maybe_economic_node)
    graph.add_node("finance", _maybe_finance_node)
    graph.add_node("crisis", _maybe_crisis_node)
    graph.add_node("synthesize", synthesize_node)

    graph.add_edge(START, "router")
    graph.add_edge("router", "commercial")
    graph.add_edge("commercial", "economic")
    graph.add_edge("economic", "finance")
    graph.add_edge("finance", "crisis")
    graph.add_edge("crisis", "synthesize")
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
