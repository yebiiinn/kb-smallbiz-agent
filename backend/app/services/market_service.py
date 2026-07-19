import json
from pathlib import Path

from app.schemas.chat import BusinessStage, RecommendationItem
from app.schemas.market import MarketInsightResponse, PolicyFundItem, PolicyFundsResponse

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "mock"


def _load_json(filename: str) -> list[dict]:
    with open(DATA_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


def get_market_insights(region: str, industry: str) -> MarketInsightResponse:
    items = _load_json("market.json")
    match = next(
        (
            item
            for item in items
            if region in item["region"] and industry in item["industry"]
        ),
        items[0],
    )
    return MarketInsightResponse(
        region=region or match["region"],
        industry=industry or match["industry"],
        market_summary=match["market_summary"],
        economic_indicator=match["economic_indicator"],
        consumption_trend=match["consumption_trend"],
        score=match["score"],
    )


def get_policy_funds(stage: BusinessStage | None = None, region: str = "") -> PolicyFundsResponse:
    items = _load_json("policy_funds.json")
    if stage:
        items = [item for item in items if item["stage"] == stage.value]
    return PolicyFundsResponse(
        items=[PolicyFundItem(**item) for item in items]
    )


def get_product_recommendations(
    region: str,
    industry: str,
    stage: BusinessStage,
    purpose: str = "",
) -> list[RecommendationItem]:
    products = _load_json("products.json")
    stage_label = {"startup": "창업", "operation": "운영", "expansion": "확장"}[stage.value]

    return [
        RecommendationItem(
            type=item["type"],
            name=item["name"],
            reason=f"{region or '해당 지역'} {industry or '업종'} {stage_label} 단계 — {item['reason']}",
            link=item.get("link", ""),
        )
        for item in products[:3]
    ]
