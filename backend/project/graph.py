"""LangGraph 오케스트레이터 — 팀원과 함께 확장."""

from langgraph.graph import END, START, StateGraph

from project.agents.commercial import commercial_node
from project.agents.crisis import crisis_node
from project.agents.economic import economic_node
from project.agents.finance import finance_node
from project.state import AgentState


def synthesize_node(state: AgentState) -> dict:
    """각 에이전트 결과를 종합해 최종 답변을 생성."""
    ctx = state["context"]
    commercial = state.get("commercial_result") or {}
    economic = state.get("economic_result") or {}
    finance = state.get("finance_result") or {}
    crisis = state.get("crisis_result") or {}

    insights = {
        "market_summary": commercial.get("summary", "상권 분석 결과 없음"),
        "economic_indicator": economic.get("indicator", "경기지표 분석 결과 없음"),
        "consumption_trend": economic.get("consumption_trend", "소비 트렌드 분석 결과 없음"),
    }

    recommendations = finance.get("recommendations", [])
    crisis_level = crisis.get("level", "normal")

    answer_parts = [
        f"{ctx.region or '해당 지역'} {ctx.industry or '업종'} ({ctx.stage.value}) 기준으로 분석했습니다.",
        f"\n📊 상권: {insights['market_summary']}",
        f"\n📈 경기: {insights['economic_indicator']}",
        f"\n🛒 소비: {insights['consumption_trend']}",
    ]

    if crisis_level != "normal":
        answer_parts.append(f"\n⚠️ 위기진단: {crisis.get('summary', '')}")

    if recommendations:
        answer_parts.append(f"\n💰 추천 {len(recommendations)}건 — 오른쪽 패널을 확인해 주세요.")

    return {
        "insights": insights,
        "recommendations": recommendations,
        "follow_up_questions": finance.get(
            "follow_up_questions",
            ["예상 창업/운영 자본금은 얼마인가요?", "대출 상환 기간은 어떻게 생각하고 계신가요?"],
        ),
        "final_answer": "".join(answer_parts),
    }


def build_graph():
    """멀티 에이전트 그래프 구성."""
    graph = StateGraph(AgentState)

    graph.add_node("commercial", commercial_node)
    graph.add_node("economic", economic_node)
    graph.add_node("finance", finance_node)
    graph.add_node("crisis", crisis_node)
    graph.add_node("synthesize", synthesize_node)

    graph.add_edge(START, "commercial")
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
