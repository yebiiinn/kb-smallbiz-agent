from fastapi import APIRouter, Query

from app.schemas.chat import BusinessStage
from app.schemas.market import PolicyFundsResponse
from app.services.market_service import get_policy_funds

router = APIRouter(prefix="/policy", tags=["policy"])


@router.get("/funds", response_model=PolicyFundsResponse)
async def policy_funds(
    stage: BusinessStage | None = Query(default=None),
    region: str = Query(default=""),
) -> PolicyFundsResponse:
    return get_policy_funds(stage, region)
