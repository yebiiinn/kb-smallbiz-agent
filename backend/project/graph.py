"""LangGraph 오케스트레이터 — 팀원과 함께 확장."""

import json
import logging

from langgraph.graph import END, START, StateGraph
from openai import OpenAI

from project.agents.commercial import commercial_node
from project.agents.crisis import crisis_node
from project.agents.economic import economic_node
from project.agents.finance import finance_node
from project.agents.router import ALL_AGENTS, is_capital_planning_query, router_node
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


_PARTIAL_SYNTHESIZE_SYSTEM = """\
당신은 KB 소상공인 금융 지원 전문 컨설턴트입니다.
아래 분석 결과(활성화된 에이전트만)를 종합해 소상공인에게 실질적인 답변을 작성하세요.

규칙:
- 제공된 분석 항목만 자연스럽게 연결 (없는 항목은 언급하지 말 것)
- 지역·업종·사업 단계를 구체적으로 언급
- 2~4문장, 실용적이고 간결하게
- 이모지 1~2개로 가독성 높게
- 금융 추천이 있으면 오른쪽 패널 확인 안내
- 소진공 점포 수와 카카오 POI가 다르면 점포 수·업종 밀집도를 우선하고, "경쟁 없음" 등 모순 결론 금지
- "소상공인 여러분", "좋은 기회" 같은 홍보·강연체 금지, 질문에 맞게 답변
- 활성 에이전트에 finance가 없으면 금융·대출·패널 안내 금지
"""


def _build_synthesize_context(
    region: str,
    industry: str,
    stage: str,
    commercial: dict,
    economic: dict,
    finance: dict,
    crisis: dict,
    active_agents: list[str],
) -> dict:
    context: dict = {
        "지역": region,
        "업종": industry,
        "사업단계": stage,
        "활성에이전트": active_agents,
    }
    if "commercial" in active_agents:
        context["상권요약"] = commercial.get("summary", "")
        context["상권점수"] = commercial.get("score")
    if "economic" in active_agents:
        context["경기지표"] = economic.get("indicator", "")
        context["소비트렌드"] = economic.get("consumption_trend", "")
    if "crisis" in active_agents:
        context["위기등급"] = crisis.get("level", "normal")
        context["위기요약"] = crisis.get("summary", "")
        context["위기권고행동"] = (crisis.get("recommended_actions") or [])[:3]
    if "finance" in active_agents:
        recommendations = finance.get("recommendations", [])
        context["금융추천건수"] = len(recommendations)
        context["금융요약"] = finance.get("summary", "")
        if finance.get("target_loan_manwon"):
            context["목표대출만원"] = finance.get("target_loan_manwon")
    return context


def _llm_synthesize(
    region: str,
    industry: str,
    stage: str,
    commercial: dict,
    economic: dict,
    finance: dict,
    crisis: dict,
    active_agents: list[str] | None = None,
) -> str:
    """에이전트 결과를 LLM으로 종합해 자연어 컨설팅 답변을 생성한다."""
    active = active_agents or list(ALL_AGENTS)
    if not settings.openai_api_key:
        return _template_answer(
            region, industry, stage, commercial, economic, finance, crisis, active_agents=active
        )

    context_block = json.dumps(
        _build_synthesize_context(
            region, industry, stage, commercial, economic, finance, crisis, active
        ),
        ensure_ascii=False,
        indent=2,
    )
    system_prompt = (
        _SYNTHESIZE_SYSTEM if active == list(ALL_AGENTS) else _PARTIAL_SYNTHESIZE_SYSTEM
    )
    max_tokens = 400 if active == list(ALL_AGENTS) else 250

    try:
        client = OpenAI(api_key=settings.openai_api_key)
        resp = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"[분석 데이터]\n{context_block}"},
            ],
            max_tokens=max_tokens,
            temperature=0.5,
        )
        answer = (resp.choices[0].message.content or "").strip()
        if answer:
            return answer
    except Exception as exc:
        logger.warning("synthesize LLM 실패 (템플릿 fallback): %s", exc)

    return _template_answer(
        region, industry, stage, commercial, economic, finance, crisis, active_agents=active
    )


def _crisis_level_label(level: str) -> str:
    return {"normal": "양호", "warning": "주의", "critical": "위험"}.get(level, level)


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
        target = finance.get("target_loan_manwon")
        if target:
            intro = f"{region} {industry} ({stage}) 기준 **{target:,}만 원** 규모 금융상품을 분석했습니다."
        else:
            intro = f"{region} {industry} ({stage}) 기준으로 금융상품을 분석했습니다."
    elif active == ["commercial"]:
        analyzed = commercial.get("industry") or industry
        intro = f"{region} **{analyzed}** 상권을 분석했습니다."
    elif active == ["economic"]:
        intro = f"{industry} 업종 기준으로 경기·소비 환경을 분석했습니다."
    elif active == ["commercial", "economic", "crisis"]:
        score = crisis.get("score", 0)
        intro = (
            f"{region} {industry} ({stage}) **위기진단** 결과 "
            f"**{_crisis_level_label(crisis_level)}** ({score}점)입니다."
        )
    else:
        intro = f"{region or '해당 지역'} {industry or '업종'} ({stage}) 기준으로 분석했습니다."

    parts = [intro]

    if "commercial" in active and commercial.get("summary"):
        parts.append(_format_section("📊 상권", commercial.get("summary", "")))
    if "economic" in active and economic.get("indicator"):
        parts.append(_format_section("📈 경기", economic.get("indicator", "")))
    if "economic" in active and economic.get("consumption_trend"):
        parts.append(_format_section("🛒 소비", economic.get("consumption_trend", "")))
    if "crisis" in active:
        if crisis_level != "normal":
            parts.append(
                f"\n\n### ⚠️ 위기진단 ({_crisis_level_label(crisis_level)} · {crisis.get('score', 0)}점)"
                f"\n- {crisis.get('summary', '')}"
            )
            actions = (crisis.get("recommended_actions") or [])[:2]
            for action in actions:
                parts.append(f"\n- {action}")
        elif active == ["commercial", "economic", "crisis"]:
            parts.append(f"\n\n### ✅ 위기진단\n- {crisis.get('summary', '현재 특별한 위기 신호 없음')}")
    if recommendations:
        parts.append(f"\n\n💰 **추천 {len(recommendations)}건** — 오른쪽 패널을 확인해 주세요.")

    return "".join(parts)


def _format_won(amount: int) -> str:
    if amount >= 100_000_000:
        return f"약 {amount / 100_000_000:.1f}억 원"
    if amount >= 10_000:
        return f"약 {amount // 10_000:,}만 원"
    return f"{amount:,}원"


def _capital_planning_answer(
    region: str,
    industry: str,
    stage: str,
    commercial: dict,
    economic: dict,
    revenue: int | None = None,
) -> str:
    """창업·운영 초기 자금 규모 추정 답변."""
    per_store_amount = commercial.get("per_store_sales_amount")
    monthly_sales = commercial.get("monthly_sales") or commercial.get("total_monthly_sales", "")
    stage_ko = {"startup": "창업", "operation": "운영", "expansion": "확장"}.get(stage, stage)

    lines = [
        f"{region} {industry} ({stage_ko}) 기준으로 **필요 자금 규모**를 상권·경기 데이터로 추정했습니다.\n",
    ]

    if revenue is not None:
        lines.append(f"- **입력 월 매출** · **{revenue:,}만 원** (온보딩/대화 입력)")
        lines.append(f"- **운전자금(4개월)** · **약 {revenue * 4:,}만 원** 권장")

    if stage == "startup":
        lines.append("### 💡 초기 자금 구성 (참고)")
        lines.append("- **보증금·권리금** · 입지·평수에 따라 **3,000~1억 원+** (현장 확인 필요)")
        lines.append("- **인테리어·설비** · 업종·규모에 따라 **2,000~8,000만 원**")
        if per_store_amount and revenue is None:
            working = per_store_amount * 4
            lines.append(
                f"- **운전자금(3~6개월)** · 점포당 월 매출 {monthly_sales} 기준 **{_format_won(working)}** 권장"
            )
        elif revenue is None:
            lines.append("- **운전자금(3~6개월)** · 업종·매출에 따라 **1,000~5,000만 원**")
        lines.append("- **초기 합계(대략)** · **5,000만~2억 원** (규모·지역 편차 큼)")
    elif stage == "operation":
        lines.append("### 💡 운영 자금 참고")
        if per_store_amount:
            buffer = per_store_amount * 3
            lines.append(
                f"- **유동성 버퍼(2~3개월)** · 월 매출 {monthly_sales} 기준 **{_format_won(buffer)}**"
            )
        else:
            lines.append("- **유동성 버퍼** · 월 고정비·재료비 기준 **2~3개월치** 확보 권장")
        lines.append("- **임대료·인건비·재료비** · 매출 대비 **60~75%** 수준을 가정해 산출하세요")
    else:
        lines.append("### 💡 확장 투자 참고")
        lines.append("- **추가 점포·리모델링** · 기존 매장 대비 **1.2~2배** 초기 투자")
        if per_store_amount:
            lines.append(f"- **기존 점포 월 매출** · {monthly_sales} (상권 추정치)")

    lines.append(
        "\n\n상세 **상권·경기 분석**은 오른쪽 **시장 인사이트** 패널에서 확인해 주세요. "
        "예상 금액(만 원)을 알려주시면 **맞춤 금융상품**을 추천해 드릴게요."
    )
    return "\n".join(lines)


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

    insights: dict[str, str | dict] = {}
    if "commercial" in active_agents:
        insights["market_summary"] = commercial.get("summary", "상권 분석 결과 없음")
    if "economic" in active_agents:
        insights["economic_indicator"] = _format_bullets(
            economic.get("indicator", "경기지표 분석 결과 없음")
        )
        insights["consumption_trend"] = _format_bullets(
            economic.get("consumption_trend", "소비 트렌드 분석 결과 없음")
        )

    if crisis.get("summary"):
        insights["crisis"] = {
            "level": crisis.get("level", "normal"),
            "score": crisis.get("score", 0),
            "summary": crisis.get("summary", ""),
            "recommended_actions": (crisis.get("recommended_actions") or [])[:3],
            "growth_market_names": (crisis.get("growth_market_names") or [])[:3],
        }

    if commercial.get("is_sales_estimated") and "서울" not in (ctx.region or ""):
        insights["sales_data_note"] = (
            "추정매출은 서울시 공식 API 기준 참고치입니다. "
            "비서울 지역은 실제 수치와 차이가 있을 수 있으니 "
            "소진공 상권정보에서 해당 지역 데이터를 확인해 주세요."
        )

    recommendations = finance.get("recommendations", []) if "finance" in active_agents else []

    region_label = ctx.region or "해당 지역"
    industry_label = commercial.get("industry") or ctx.industry or "업종"
    stage_label = ctx.stage.value
    user_query = state.get("user_query", "")

    if is_capital_planning_query(user_query):
        final_answer = _capital_planning_answer(
            region_label,
            industry_label,
            stage_label,
            commercial,
            economic,
            revenue=ctx.revenue,
        )
    elif len(active_agents) >= 2:
        final_answer = _llm_synthesize(
            region=region_label,
            industry=industry_label,
            stage=stage_label,
            commercial=commercial,
            economic=economic,
            finance=finance,
            crisis=crisis,
            active_agents=active_agents,
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
    if is_capital_planning_query(user_query):
        follow_up = [
            "3,000만 원 규모로 맞춤 금융상품 추천해줘",
            "5,000만 원 규모 대출 한도 알려줘",
            "정책자금으로 가능한지 알려줘",
        ]
    elif active_agents == ["commercial"]:
        follow_up = [
            "이 지역 창업 초기 자금 규모 알려줘",
            "위기진단 해줘",
            "종합 분석해줘",
        ]
    elif not follow_up:
        follow_up = [
            "창업에 필요한 초기 자금 규모 알려줘",
            "대출 상환 기간은 어떻게 생각하고 계신가요?",
        ]

    return {
        "insights": insights,
        "recommendations": recommendations,
        "follow_up_questions": follow_up,
        "final_answer": final_answer,
        "active_agents": active_agents,
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


async def run_graph(message: str, context, *, user_query: str | None = None) -> dict:
    """그래프 실행 헬퍼."""
    initial: AgentState = {
        "messages": [],
        "context": context,
        "user_query": user_query or message,
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
