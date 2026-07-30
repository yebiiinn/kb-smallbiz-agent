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


# ---------------------------------------------------------------------------
# 업종별 폐업률(생존율) 추정
# ---------------------------------------------------------------------------
# 통계청 소상공인실태조사·서비스업생산지수 기반 업종별 1년 생존율 baseline
# 출처: 통계청 「소상공인실태조사」, 중소벤처기업부 소상공인 통계 (2022~2024 평균)
_BASELINE_SURVIVAL_1Y: dict[str, float] = {
    "음식점":   0.60,
    "한식":     0.60,
    "중식":     0.62,
    "일식":     0.63,
    "카페":     0.58,
    "커피":     0.58,
    "치킨":     0.55,
    "분식":     0.57,
    "편의점":   0.72,
    "소매":     0.68,
    "마트":     0.70,
    "슈퍼마켓": 0.70,
    "미용":     0.75,
    "헤어":     0.75,
    "세탁":     0.78,
    "학원":     0.65,
    "교육":     0.65,
    "헬스장":   0.62,
    "PC방":     0.52,
    "노래방":   0.50,
    "기타":     0.65,
}


def _match_survival(industry: str) -> tuple[float, str]:
    """업종 키워드로 1년 생존율 baseline을 반환한다."""
    for key, rate in _BASELINE_SURVIVAL_1Y.items():
        if key in industry:
            return rate, key
    return _BASELINE_SURVIVAL_1Y["기타"], "기타"


def _survival_to_risk(survival: float) -> str:
    if survival < 0.55:
        return "high"
    if survival < 0.65:
        return "medium"
    return "low"


def fetch_closure_rate(industry: str) -> dict:
    """업종별 폐업률(1년 생존율) 추정.

    KOSIS 서비스업생산지수 증감률로 동적 보정 시도 후,
    API 미사용 환경에서는 통계청 baseline을 그대로 반환한다.

    Returns
    -------
    dict
        survival_1y  : 1년 생존율 (0~1, 예: 0.58 → 58%)
        closure_risk : "high" | "medium" | "low"
        industry_key : 매칭된 업종 키
        source       : "kosis_adjusted" | "baseline"
    """
    baseline, matched_key = _match_survival(industry)

    # KOSIS 키가 있으면 서비스업생산지수 최근 증감률로 보정
    if settings.kosis_api_key:
        INDUSTRY_MAP_KOSIS = {
            "음식점주점": ("DT_1KC2020", "T2", "I56", "101"),
            "편의점":    ("DT_1K41013", "T2", "A5",  "101"),
            "개인서비스": ("DT_1KC2020", "T2", "S96", "101"),
            "교육서비스": ("DT_1KC2020", "T2", "P",   "101"),
        }
        keyword_map_kosis = {
            "음식": "음식점주점", "카페": "음식점주점", "치킨": "음식점주점",
            "편의": "편의점",
            "미용": "개인서비스", "세탁": "개인서비스", "헬스": "개인서비스",
            "학원": "교육서비스", "교육": "교육서비스",
        }
        industry_key_kosis = next(
            (v for k, v in keyword_map_kosis.items() if k in industry),
            "음식점주점",
        )
        tbl_id, itm_id, obj_l1, org_id = INDUSTRY_MAP_KOSIS[industry_key_kosis]

        from datetime import datetime, timedelta
        end = datetime.today().strftime("%Y%m")
        start = (datetime.today() - timedelta(days=60)).strftime("%Y%m")

        try:
            series = fetch_indicator_series(tbl_id, itm_id, obj_l1, org_id,
                                            start=start, end=end)
            if len(series) >= 2:
                latest = series[-1]["value"]
                prev = series[-2]["value"]
                growth_rate = (latest - prev) / prev if prev else 0.0
                # 업황 개선 시 생존율 +3%p, 악화 시 -3%p 보정 (보수적)
                adjustment = max(-0.05, min(0.05, growth_rate * 0.3))
                adjusted = round(baseline + adjustment, 3)
                return {
                    "survival_1y":  adjusted,
                    "closure_risk": _survival_to_risk(adjusted),
                    "industry_key": matched_key,
                    "source":       "kosis_adjusted",
                    "growth_rate":  round(growth_rate * 100, 2),
                }
        except Exception:
            pass

    return {
        "survival_1y":  baseline,
        "closure_risk": _survival_to_risk(baseline),
        "industry_key": matched_key,
        "source":       "baseline",
    }


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
