"""통계청 KOSIS API — 업종별 생산·소매 지수 수집.

검증된 통계표·항목 코드 목록은 project/data/indicator_mapping.json 참조.
필수 파라미터: orgId (누락 시 API 에러 발생).
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from project.config import settings

KOSIS_BASE = "https://kosis.kr/openapi"
KOSIS_PARAM_URL = f"{KOSIS_BASE}/Param/statisticsParameterData.do"

MOCK_PATH = Path(__file__).resolve().parent.parent / "data" / "mock" / "kosis.json"


def _load_mock(region: str, industry: str) -> dict:
    with open(MOCK_PATH, encoding="utf-8") as f:
        items = json.load(f)
    match = next(
        (item for item in items if industry in item["industry"]),
        items[0],
    )
    return {
        "summary": match["summary"].format(region=region, industry=industry),
        "growth_rate": match.get("growth_rate"),
        "source": "mock",
    }


def fetch_indicator_series(
    tbl_id: str,
    itm_id: str,
    obj_l1: str,
    org_id: str = "101",
    obj_l2: str = "",
    prd_se: str = "M",
    start: str = "202301",
    end: str = "202612",
) -> list[dict]:
    """KOSIS statisticsParameterData 로 단일 지표 시계열 수집.

    Returns
    -------
    list[dict]  [{"time": "202301", "value": 119.5}, ...]
    """
    if not settings.kosis_api_key:
        return []

    params: dict = {
        "method": "getList",
        "apiKey": settings.kosis_api_key,
        "orgId": org_id,
        "tblId": tbl_id,
        "itmId": itm_id,
        "objL1": obj_l1,
        "prdSe": prd_se,
        "startPrdDe": start,
        "endPrdDe": end,
        "format": "json",
        "jsonVD": "Y",
    }
    if obj_l2:
        params["objL2"] = obj_l2

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(KOSIS_PARAM_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        if isinstance(data, dict) and "err" in data:
            return []

        rows = data if isinstance(data, list) else []
        result: list[dict] = []
        for row in rows:
            t = row.get("PRD_DE", "")
            v = row.get("DT", "")
            try:
                result.append({"time": t, "value": float(v)})
            except (ValueError, TypeError):
                pass
        return result

    except (httpx.HTTPError, json.JSONDecodeError):
        return []


def fetch_consumption_trend(region: str, industry: str) -> dict:
    """지역·업종 소비 트렌드 조회 (KOSIS).

    economic_node 에서 호출하는 고수준 인터페이스.
    indicator_mapping.json 의 industry_keyword_map 으로 업종을 분류 후 호출.
    """
    if not settings.kosis_api_key:
        return _load_mock(region, industry)

    # 업종 키워드 → KOSIS 분류 매핑
    INDUSTRY_MAP = {
        "음식점주점": ("DT_1KC2020", "T2", "I56", "101"),
        "편의점":    ("DT_1K41013", "T2", "A5",  "101"),
        "전문소매점": ("DT_1K41013", "T2", "A7",  "101"),
        "교육서비스": ("DT_1KC2020", "T2", "P",   "101"),
        "개인서비스": ("DT_1KC2020", "T2", "S96", "101"),
    }

    # 업종 키워드 매칭
    keyword_map = {
        "음식": "음식점주점", "카페": "음식점주점", "주점": "음식점주점",
        "편의": "편의점", "소매": "편의점",
        "전문": "전문소매점", "마트": "전문소매점",
        "학원": "교육서비스", "교육": "교육서비스",
        "미용": "개인서비스", "세탁": "개인서비스", "수리": "개인서비스",
    }
    industry_key = next(
        (v for k, v in keyword_map.items() if k in industry),
        "음식점주점",
    )
    tbl_id, itm_id, obj_l1, org_id = INDUSTRY_MAP[industry_key]

    from datetime import datetime, timedelta
    end = datetime.today().strftime("%Y%m")
    start = (datetime.today() - timedelta(days=90)).strftime("%Y%m")

    series = fetch_indicator_series(tbl_id, itm_id, obj_l1, org_id,
                                    start=start, end=end)
    if not series:
        return _load_mock(region, industry)

    latest = series[-1]["value"]
    prev = series[-2]["value"] if len(series) >= 2 else latest
    growth = round((latest - prev) / prev * 100, 2) if prev else None

    return {
        "summary": (
            f"{region} {industry} 서비스업생산지수 {latest:.1f}"
            f" (전월 대비 {growth:+.1f}%)" if growth is not None else ""
        ),
        "growth_rate": growth,
        "latest_index": latest,
        "source": "kosis_api",
    }
