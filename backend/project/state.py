"""LangGraph 공유 State — 팀원과 함께 확장."""

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages

from project.schemas import BusinessContext, RecommendationItem


class AgentState(TypedDict):
    """그래프 전체에서 공유하는 상태."""

    messages: Annotated[list, add_messages]
    context: BusinessContext
    user_query: str
    active_agents: list[str]

    # 에이전트별 결과 (담당자 A/B가 채움)
    commercial_result: dict
    economic_result: dict
    finance_result: dict
    crisis_result: dict

    # 최종 출력
    insights: dict
    recommendations: list[RecommendationItem]
    follow_up_questions: list[str]
    final_answer: str
