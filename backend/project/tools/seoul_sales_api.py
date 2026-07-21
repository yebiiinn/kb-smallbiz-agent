"""서울시 추정매출 API — 지역 상권 분석."""

import json
from pathlib import Path

import httpx

from project.config import settings

# 서울시 상권분석서비스(추정매출-자치구) Open API 명세
# http://openapi.seoul.go.kr:8088/(인증키)/json/VwsmSignguSelngW/1/5/SIGNGU_CD/11680
SERVICE_NAME = "VwsmSignguSelngW"
API_URL_TEMPLATE = (
    "http://openapi.seoul.go.kr:8088/{key}/json/{service}/{start}/{end}/SIGNGU_CD/{signgu_code}"
)

MOCK_PATH = Path(__file__).resolve().parent.parent / "data" / "mock" / "seoul_sales.json"

SIGNGU_CODES: dict[str, str] = {
    "종로구": "11110",
    "중구": "11140",
    "용산구": "11170",
    "성동구": "11200",
    "광진구": "11215",
    "동대문구": "11230",
    "중랑구": "11260",
    "성북구": "11290",
    "강북구": "11305",
    "도봉구": "11320",
    "노원구": "11350",
    "은평구": "11380",
    "서대문구": "11410",
    "마포구": "11440",
    "양천구": "11470",
    "강서구": "11500",
    "구로구": "11530",
    "금천구": "11545",
    "영등포구": "11560",
    "동작구": "11590",
    "관악구": "11620",
    "서초구": "11650",
    "강남구": "11680",
    "송파구": "11710",
    "강동구": "11740",
}

INDUSTRY_MATCHERS: dict[str, list[str]] = {
    "카페": ["커피-음료", "카페", "커피", "다방"],
    "음식점": ["한식음식점", "중식음식점", "양식음식점", "음식", "식당", "분식"],
    "소매": ["소매", "편의점", "슈퍼", "마트", "의류", "화장품"],
}


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


def _resolve_signgu_code(region: str) -> str | None:
    for name, code in SIGNGU_CODES.items():
        if name in region:
            return code
    return None


def _parse_signgu_name(region: str) -> str:
    if "구" in region:
        idx = region.find("구")
        return region[: idx + 1].split()[-1]
    return region.strip()


def _industry_keywords(industry: str) -> list[str]:
    if industry in INDUSTRY_MATCHERS:
        return INDUSTRY_MATCHERS[industry]
    return [industry]


def _matches_industry(industry_name: str, industry: str) -> bool:
    keywords = _industry_keywords(industry)
    return any(keyword in industry_name for keyword in keywords)


def _build_url(signgu_code: str, start: int = 1, end: int = 1000) -> str:
    return API_URL_TEMPLATE.format(
        key=settings.seoul_sales_api_key,
        service=SERVICE_NAME,
        start=start,
        end=end,
        signgu_code=signgu_code,
    )


def _normalize_rows(data: dict) -> list[dict]:
    block = data.get(SERVICE_NAME) or {}
    rows = block.get("row", [])
    if isinstance(rows, dict):
        return [rows]
    return rows or []


def _parse_amount(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).replace(",", "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _format_amount(amount: int | None) -> str:
    if amount is None:
        return ""
    if amount >= 100_000_000:
        return f"약 {amount / 100_000_000:.1f}억 원"
    if amount >= 10_000:
        return f"약 {amount // 10_000:,}만 원"
    return f"{amount:,}원"


def _fetch_rows(signgu_code: str) -> tuple[list[dict], dict | None]:
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(_build_url(signgu_code))
        resp.raise_for_status()
        data = resp.json()

    result = data.get("RESULT")
    if result and result.get("CODE", "").startswith("ERROR"):
        return [], result

    return _normalize_rows(data), None


def _pick_industry_rows(rows: list[dict], industry: str, signgu_code: str) -> list[dict]:
    matched = [
        row
        for row in rows
        if str(row.get("SIGNGU_CD", "")) == str(signgu_code)
        and _matches_industry(str(row.get("SVC_INDUTY_CD_NM", "")), industry)
    ]
    return sorted(matched, key=lambda row: str(row.get("STDR_YYQU_CD", "")), reverse=True)


def _format_quarter(code: str) -> str:
    if len(code) >= 5 and code[:4].isdigit():
        year = code[:4]
        quarter = code[4]
        return f"{year}년 {quarter}분기"
    return code


def _calc_trend(current: int | None, previous: int | None) -> str:
    if current is None or previous is None or previous == 0:
        return "전분기 대비 데이터 확인 필요"
    change = (current - previous) / previous * 100
    sign = "+" if change >= 0 else ""
    return f"전분기 대비 {sign}{change:.1f}%"


def fetch_estimated_sales(region: str, industry: str) -> dict:
    """서울시 상권 추정매출 조회."""
    if not settings.seoul_sales_api_key:
        return _load_mock(region, industry)

    if "서울" not in region:
        return _load_mock(region, industry)

    signgu_code = _resolve_signgu_code(region)
    if not signgu_code:
        return _load_mock(region, industry)

    try:
        rows, error = _fetch_rows(signgu_code)
        if error or not rows:
            mock = _load_mock(region, industry)
            if error:
                mock["api_error"] = error
            return mock

        matched_rows = _pick_industry_rows(rows, industry, signgu_code)
        if not matched_rows:
            return _load_mock(region, industry)

        latest_row = matched_rows[0]
        previous_row = matched_rows[1] if len(matched_rows) > 1 else None

        latest_amount = _parse_amount(latest_row.get("THSMON_SELNG_AMT"))
        previous_amount = (
            _parse_amount(previous_row.get("THSMON_SELNG_AMT")) if previous_row else None
        )

        monthly_sales = _format_amount(latest_amount)
        sales_trend = _calc_trend(latest_amount, previous_amount)
        quarter_label = _format_quarter(str(latest_row.get("STDR_YYQU_CD", "")))
        industry_name = latest_row.get("SVC_INDUTY_CD_NM", industry)
        signgu_name = _parse_signgu_name(region)

        summary = (
            f"{signgu_name} {industry_name} 업종 {quarter_label} "
            f"월 추정매출 {monthly_sales or '집계 중'}. {sales_trend}."
        )

        return {
            "monthly_sales": monthly_sales,
            "sales_trend": sales_trend,
            "summary": summary,
            "quarter": quarter_label,
            "industry_name": industry_name,
            "source": "seoul_sales_api",
            "raw": latest_row,
        }
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return _load_mock(region, industry)
