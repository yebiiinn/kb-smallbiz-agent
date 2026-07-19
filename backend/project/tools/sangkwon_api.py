"""소진공 상권 정보 API — 지역 상권 분석."""

import json
from pathlib import Path

import httpx

from project.config import settings

# 소상공인시장진흥공단 상가(상권)정보 API - 행정동 단위 상가업소 조회
# 전체 엔드포인트 목록: storeListInAdmiDong / storeListInRadius / storeListInBuilding 등
API_URL = "https://apis.data.go.kr/B553077/api/open/sdsc2/storeListInAdmiDong"

MOCK_PATH = Path(__file__).resolve().parent.parent / "data" / "mock" / "market.json"


def _load_mock(region: str, industry: str) -> dict:
    with open(MOCK_PATH, encoding="utf-8") as f:
        items = json.load(f)
    match = next(
        (item for item in items if region in item["region"] and industry in item["industry"]),
        items[0],
    )
    return {
        "summary": match["market_summary"],
        "score": match["score"],
        "foot_traffic": "mock 데이터",
        "competition": f"{industry} 업종 경쟁 밀집도 참고",
        "source": "mock",
    }


def fetch_commercial_district(region: str, industry: str) -> dict:
    """지역·업종 기준 상권 정보 조회."""
    if not settings.sangkwon_api_key:
        return _load_mock(region, industry)

    params = {
        "serviceKey": settings.sangkwon_api_key,
        "region": region,
        "industry": industry,
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(API_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            return {
                "summary": data.get("summary", ""),
                "score": data.get("score", 0),
                "foot_traffic": data.get("footTraffic", ""),
                "competition": data.get("competition", ""),
                "source": "sangkwon_api",
                "raw": data,
            }
    except (httpx.HTTPError, json.JSONDecodeError):
        return _load_mock(region, industry)
