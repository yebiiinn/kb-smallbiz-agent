from fastapi import APIRouter, Query

from app.schemas.chat import BusinessStage
from app.schemas.market import MarketInsightResponse
from app.services.market_service import get_market_insights

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/insights", response_model=MarketInsightResponse)
async def market_insights(
    region: str = Query(default="서울 강남구"),
    industry: str = Query(default="카페"),
) -> MarketInsightResponse:
    return get_market_insights(region, industry)
