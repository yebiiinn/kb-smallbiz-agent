"""질문 의도 기반 에이전트 라우팅."""

from project.state import AgentState

ALL_AGENTS = ("commercial", "economic", "finance", "crisis")

_AGENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "finance": (
        "대출",
        "정책자금",
        "금융",
        "융자",
        "보증",
        "상품",
        "한도",
        "만기",
        "이자",
        "상환",
        "kb",
        "KB",
        "예금",
        "적금",
        "바우처",
    ),
    "commercial": (
        "상권",
        "매출",
        "경쟁",
        "점포",
        "유동",
        "상가",
        "입지",
        "추정매출",
        "밀집",
        "foot",
    ),
    "economic": (
        "경기",
        "CSI",
        "csi",
        "소비",
        "금리",
        "지표",
        "물가",
        "BSI",
        "경기지표",
        "소비트렌드",
        "경기지표",
    ),
    "crisis": (
        "위기",
        "리스크",
        "위험",
        "경영난",
        "부실",
        "위기진단",
        "위기 진단",
    ),
}

_FULL_ANALYSIS_KEYWORDS = (
    "종합",
    "전체 분석",
    "한번에",
    "전반",
    "4가지",
    "다 알려",
    "모두",
)


def classify_active_agents(user_query: str) -> list[str]:
    """질문에서 필요한 에이전트 목록을 반환한다."""
    query = (user_query or "").strip()
    if not query:
        return list(ALL_AGENTS)

    if any(keyword in query for keyword in _FULL_ANALYSIS_KEYWORDS):
        return list(ALL_AGENTS)

    matched = [
        agent
        for agent, keywords in _AGENT_KEYWORDS.items()
        if any(keyword in query for keyword in keywords)
    ]
    if not matched:
        return list(ALL_AGENTS)

    active = set(matched)
    if "crisis" in active:
        active.update({"commercial", "economic", "crisis"})
    return [agent for agent in ALL_AGENTS if agent in active]


def router_node(state: AgentState) -> dict:
    """user_query 기준으로 active_agents 를 결정한다."""
    active_agents = classify_active_agents(state.get("user_query", ""))
    return {"active_agents": active_agents}
