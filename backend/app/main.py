from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import agent, market, policy, recommend

app = FastAPI(
    title="소상공인 금융 지원 에이전트 API",
    description="KB AI Challenge — 상권·경기·정책자금·금융상품 종합 분석 API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agent.router, prefix="/api/v1")
app.include_router(market.router, prefix="/api/v1")
app.include_router(policy.router, prefix="/api/v1")
app.include_router(recommend.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
