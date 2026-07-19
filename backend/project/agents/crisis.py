"""위기진단 에이전트 — 담당자 B."""

from project.state import AgentState


def crisis_node(state: AgentState) -> dict:
    ctx = state["context"]
    commercial = state.get("commercial_result") or {}
    economic = state.get("economic_result") or {}

    score = commercial.get("score", 50)
    revenue = ctx.revenue
    stage = ctx.stage.value

    level = "normal"
    signals: list[str] = []

    if score < 40:
        level = "warning"
        signals.append("상권 활성도가 낮습니다.")

    if revenue is not None and revenue < 5_000_000 and stage == "operation":
        level = "critical"
        signals.append("월 매출이 기준치 이하로 추정됩니다.")

    if "하락" in economic.get("indicator", ""):
        if level == "normal":
            level = "warning"
        signals.append("경기지표 하락세가 감지됩니다.")

    summary = "현재 특별한 위기 신호가 없습니다."
    if signals:
        summary = " ".join(signals)

    return {
        "crisis_result": {
            "level": level,
            "signals": signals,
            "summary": summary,
            "recommended_actions": _suggest_actions(level),
        }
    }


def _suggest_actions(level: str) -> list[str]:
    if level == "critical":
        return ["정책자금·경영안정 지원 사업 확인", "대출 만기 연장·상환 유예 상담"]
    if level == "warning":
        return ["소비 트렌드 재분석", "단기 유동성 확보 방안 검토"]
    return ["정기적인 상권·경기 모니터링"]
