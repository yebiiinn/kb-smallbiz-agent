from fastapi import APIRouter

from app.schemas.market import ProductRecommendRequest, ProductRecommendResponse
from app.services.market_service import get_product_recommendations

router = APIRouter(prefix="/recommend", tags=["recommend"])


@router.post("/products", response_model=ProductRecommendResponse)
async def recommend_products(
    request: ProductRecommendRequest,
) -> ProductRecommendResponse:
    items = get_product_recommendations(
        request.region,
        request.industry,
        request.stage,
        request.purpose,
    )
    return ProductRecommendResponse(items=items)
