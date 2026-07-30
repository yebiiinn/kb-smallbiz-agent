"""Intent router 분류 스모크 테스트."""

from project.agents.router import ALL_AGENTS, classify_active_agents, is_capital_planning_query


def test_finance_only():
    assert classify_active_agents("소상공인 대출 상품 추천해줘") == ["finance"]


def test_capital_planning():
    agents = classify_active_agents("초기 자본금 얼마나 필요해?")
    assert agents == ["commercial", "economic"]
    assert is_capital_planning_query("초기 자본금 얼마나 필요해?")


def test_crisis_includes_commercial_economic():
    agents = classify_active_agents("위기진단 해줘")
    assert "crisis" in agents
    assert "commercial" in agents
    assert "economic" in agents
    assert "finance" not in agents


def test_full_analysis():
    assert classify_active_agents("종합 분석해줘") == list(ALL_AGENTS)


def test_economic_only():
    agents = classify_active_agents("금리 전망이 어때?")
    assert agents == ["economic"]
