"""서울시 추정매출 API — 지역 상권 분석."""

import json
from pathlib import Path

import httpx

from project.config import settings

# ↓ API 명세 URL 붙여넣기. 인증키 자리는 {key} 로 두면 .env 키가 자동 삽입됨
API_URL_TEMPLATE = "http://openapi.seoul.go.kr:8088/{key}/json/tbSalesEst/1/5"

MOCK_PATH = Path(__file__).resolve().parent.parent / "data" / "mock" / "seoul_sales.json"


def _build_url() -> str:
    return API_URL_TEMPLATE.format(key=settings.seoul_sales_api_key)


def _load_mock(region: str, industry: str) -> dict:
    with open(MOCK_PATH, encoding="utf-8") as f:
        items = json.load(f)
    match = next(
        (item for item in items if region in item["region"] and industry in item["industry"]),
        items[0],
    )
    return {
        "monthly_sales": match["monthly_sales"],
        "sales_trend": match["sales_trend"],
        "summary": match["summary"],
        "source": "mock",
    }


def fetch_estimated_sales(region: str, industry: str) -> dict:
    """서울시 상권 추정매출 조회."""
    if not settings.seoul_sales_api_key:
        return _load_mock(region, industry)

    params = {
        "SIGNGU_NM": region,
        "INDS_LCLS_NM": industry,
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(_build_url(), params=params)
            resp.raise_for_status()
            data = resp.json()
            rows = data.get("tbSalesEst", {}).get("row", [])
            row = rows[0] if rows else {}
            return {
                "monthly_sales": row.get("MONTHLY_AVG_SALES", ""),
                "sales_trend": row.get("SALES_TREND", ""),
                "summary": f"{region} {industry} 추정매출 API 조회 완료",
                "source": "seoul_sales_api",
                "raw": data,
            }
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError):
        return _load_mock(region, industry)
