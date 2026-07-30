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

_CAPITAL_PLANNING_KEYWORDS = (
    "자본금",
    "창업 자금",
    "초기 자금",
    "개업 비용",
    "창업 비용",
    "필요한 자금",
    "얼마나 필요",
    "얼마 필요",
    "초기 비용",
    "소요 자금",
    "자금 규모",
    "초기자금",
    "창업비",
)

_STARTUP_TIMING_KEYWORDS = (
    "창업해도 될까",
    "창업 타이밍",
    "지금 창업",
    "창업하는게 좋을까",
    "창업하는 게 좋을까",
    "창업 적합",
    "창업 추천",
    "창업할까",
    "지금 시작해도",
    "요즘 창업",
    "창업 시기",
    "창업 적기",
    "창업해도 되나",
    "창업 괜찮을까",
    "창업 지금 해도",
    "창업 가능할까",
)


def extract_current_query(user_query: str) -> str:
    """멀티턴 augmented 메시지에서 현재 질문만 추출한다."""
    text = (user_query or "").strip()
    marker = "[현재 질문]:"
    if marker in text:
        return text.split(marker, 1)[1].strip()
    return text


def is_capital_planning_query(user_query: str) -> bool:
    """창업·운영에 필요한 자금 규모를 묻는 질문인지 판별한다."""
    query = extract_current_query(user_query)
    return any(keyword in query for keyword in _CAPITAL_PLANNING_KEYWORDS)


def is_startup_timing_query(user_query: str) -> bool:
    """지금 창업해도 될지 타이밍·적합성을 묻는 질문인지 판별한다."""
    query = extract_current_query(user_query)
    return any(keyword in query for keyword in _STARTUP_TIMING_KEYWORDS)


def classify_active_agents(user_query: str) -> list[str]:
    """질문에서 필요한 에이전트 목록을 반환한다."""
    query = extract_current_query(user_query)
    if not query:
        return list(ALL_AGENTS)

    if is_capital_planning_query(query):
        return ["commercial", "economic"]

    if is_startup_timing_query(query):
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
