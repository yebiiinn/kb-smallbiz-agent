"""카카오맵 API — 주변 POI·경쟁업체·입지 분석."""

import json

import httpx

from project.config import settings

# ↓ API 명세의 요청 URL/Endpoint 붙여넣기
API_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


def _load_mock(region: str, industry: str) -> dict:
    return {
        "poi_count": 42,
        "competition_level": "high",
        "summary": f"{region} {industry} 업종 주변 POI 밀집 (mock)",
        "nearby_places": [],
        "source": "mock",
    }


def search_nearby_competition(region: str, industry: str) -> dict:
    """키워드 검색으로 주변 경쟁업체·입지 정보 조회."""
    if not settings.kakao_rest_api_key:
        return _load_mock(region, industry)

    headers = {"Authorization": f"KakaoAK {settings.kakao_rest_api_key}"}
    query = f"{region} {industry}"

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                API_URL,
                headers=headers,
                params={"query": query, "size": 15},
            )
            resp.raise_for_status()
            data = resp.json()
            documents = data.get("documents", [])
            poi_count = len(documents)
            competition_level = "high" if poi_count >= 10 else "medium" if poi_count >= 5 else "low"

            return {
                "poi_count": poi_count,
                "competition_level": competition_level,
                "summary": f"{region} 인근 {industry} 검색 {poi_count}건",
                "nearby_places": [
                    {
                        "name": doc.get("place_name", ""),
                        "address": doc.get("road_address_name") or doc.get("address_name", ""),
                        "distance": doc.get("distance", ""),
                    }
                    for doc in documents[:5]
                ],
                "source": "kakao_map_api",
                "raw": data,
            }
    except (httpx.HTTPError, json.JSONDecodeError, KeyError):
        return _load_mock(region, industry)
