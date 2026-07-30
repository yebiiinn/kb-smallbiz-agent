"""소진공 상권 정보 API — 지역 상권 분석."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import httpx

from project.config import settings

# storeListInAdmiDong 은 존재하지 않음 → storeListInDong + signguCd 사용
API_URL = "http://apis.data.go.kr/B553077/api/open/sdsc2/storeListInDong"

MOCK_PATH = Path(__file__).resolve().parent.parent / "data" / "mock" / "market.json"
SIGNGU_CODES_PATH = Path(__file__).resolve().parent.parent / "data" / "signgu_codes.json"
INDUSTRY_CODES_PATH = Path(__file__).resolve().parent.parent / "data" / "industry_codes.json"

# 자주 쓰는 입력어 → 소진공 상권업종분류 코드
INDUSTRY_ALIASES: dict[str, dict[str, str | tuple[str, ...]]] = {
    "카페": {"label": "카페", "scls_cds": ("I21201",)},
    "커피": {"label": "카페", "scls_cds": ("I21201",)},
    "음식점": {"label": "음식", "lcls_cd": "I2"},
    "음식": {"label": "음식", "lcls_cd": "I2"},
    "소매": {"label": "소매", "lcls_cd": "G2"},
    "편의점": {"label": "편의점", "scls_cds": ("G20405",)},
    "헬스장": {"label": "헬스장", "scls_cds": ("R10307",)},
    "헬스": {"label": "헬스장", "scls_cds": ("R10307",)},
}


@dataclass(frozen=True)
class IndustryFilter:
    label: str
    lcls_cd: str | None = None
    mcls_cd: str | None = None
    scls_cds: tuple[str, ...] = ()

    def to_query_params(self) -> list[dict[str, str]]:
        if self.scls_cds:
            return [{"indsSclsCd": code} for code in self.scls_cds]
        if self.mcls_cd:
            return [{"indsMclsCd": self.mcls_cd}]
        if self.lcls_cd:
            return [{"indsLclsCd": self.lcls_cd}]
        return []

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "lcls_cd": self.lcls_cd,
            "mcls_cd": self.mcls_cd,
            "scls_cds": list(self.scls_cds),
        }

SIDO_ALIASES: dict[str, str] = {
    "서울": "서울특별시",
    "서울특별시": "서울특별시",
    "부산": "부산광역시",
    "부산광역시": "부산광역시",
    "대구": "대구광역시",
    "대구광역시": "대구광역시",
    "인천": "인천광역시",
    "인천광역시": "인천광역시",
    "광주": "광주광역시",
    "광주광역시": "광주광역시",
    "대전": "대전광역시",
    "대전광역시": "대전광역시",
    "울산": "울산광역시",
    "울산광역시": "울산광역시",
    "세종": "세종특별자치시",
    "세종시": "세종특별자치시",
    "세종특별자치시": "세종특별자치시",
    "경기": "경기도",
    "경기도": "경기도",
    "강원": "강원특별자치도",
    "강원도": "강원특별자치도",
    "강원특별자치도": "강원특별자치도",
    "충북": "충청북도",
    "충청북도": "충청북도",
    "충남": "충청남도",
    "충청남도": "충청남도",
    "전북": "전북특별자치도",
    "전라북도": "전북특별자치도",
    "전북특별자치도": "전북특별자치도",
    "전남": "전라남도",
    "전라남도": "전라남도",
    "경북": "경상북도",
    "경상북도": "경상북도",
    "경남": "경상남도",
    "경상남도": "경상남도",
    "제주": "제주특별자치도",
    "제주도": "제주특별자치도",
    "제주특별자치도": "제주특별자치도",
}


@lru_cache(maxsize=1)
def _load_signgu_records() -> tuple[dict[str, dict], dict[str, list[dict]]]:
    with open(SIGNGU_CODES_PATH, encoding="utf-8") as file:
        records: list[dict] = json.load(file)
    by_sido: dict[str, list[dict]] = {}
    for record in records:
        by_sido.setdefault(record["sido"], []).append(record)
    return {record["code"]: record for record in records}, by_sido


def _normalize_region(region: str) -> str:
    return " ".join(region.strip().split())


def _detect_sido(region: str) -> str | None:
    normalized = _normalize_region(region)
    matches = [(len(alias), sido) for alias, sido in SIDO_ALIASES.items() if alias in normalized]
    if not matches:
        return None
    return max(matches, key=lambda item: item[0])[1]


def _is_sido_only_query(region: str, sido: str | None) -> bool:
    if not sido:
        return False
    normalized = _normalize_region(region)
    aliases = sorted({alias for alias, name in SIDO_ALIASES.items() if name == sido}, key=len, reverse=True)
    return any(normalized == alias for alias in aliases)


def _city_children(records: list[dict], city_name: str) -> list[dict]:
    children = [
        record
        for record in records
        if record["sigungu"].startswith(city_name) and record["sigungu"] != city_name
    ]
    return children or [record for record in records if record["sigungu"] == city_name]


def _match_signgu_records(region: str, records: list[dict]) -> list[dict]:
    normalized = _normalize_region(region)
    if not records:
        return []

    direct = [record for record in records if record["sigungu"] in normalized]
    if direct:
        if len({record["sido"] for record in direct}) > 1:
            return []
        longest = max(len(record["sigungu"]) for record in direct)
        longest_matches = [record for record in direct if len(record["sigungu"]) == longest]
        if len(longest_matches) == 1:
            record = longest_matches[0]
            if record["sigungu"].endswith("시"):
                children = _city_children(records, record["sigungu"])
                if len(children) > 1:
                    return children
        return longest_matches

    city_names = sorted(
        {record["sigungu"] for record in records if record["sigungu"].endswith("시")},
        key=len,
        reverse=True,
    )
    for city_name in city_names:
        if city_name in normalized:
            return _city_children(records, city_name)
    return []


def _resolve_signgu_codes(region: str) -> list[str]:
    _, by_sido = _load_signgu_records()
    normalized = _normalize_region(region)
    if not normalized:
        return []

    sido = _detect_sido(normalized)
    if sido and _is_sido_only_query(normalized, sido):
        return [record["code"] for record in by_sido.get(sido, [])]

    if sido:
        matched = _match_signgu_records(normalized, by_sido.get(sido, []))
        if matched:
            return [record["code"] for record in matched]

    all_records = [record for records in by_sido.values() for record in records]
    matched = _match_signgu_records(normalized, all_records)
    if matched and len({record["sido"] for record in matched}) == 1:
        return [record["code"] for record in matched]
    return []


def _load_mock(region: str, industry: str) -> dict:
    with open(MOCK_PATH, encoding="utf-8") as file:
        items = json.load(file)
    match = next(
        (item for item in items if region in item["region"] and industry in item["industry"]),
        None,
    )
    if match is None:
        match = next((item for item in items if region in item["region"]), None)
    if match is None:
        return {
            "summary": f"{region} {industry} 상권 정보는 API 조회에 실패했습니다.",
            "score": 50,
            "foot_traffic": "mock 데이터",
            "competition": f"{industry} 업종 경쟁 밀집도 참고",
            "source": "mock",
        }
    return {
        "summary": match["market_summary"],
        "score": match["score"],
        "foot_traffic": "mock 데이터",
        "competition": f"{industry} 업종 경쟁 밀집도 참고",
        "source": "mock",
    }


@lru_cache(maxsize=1)
def _load_industry_codes() -> list[dict]:
    with open(INDUSTRY_CODES_PATH, encoding="utf-8") as file:
        return json.load(file)


def _normalize_industry_name(name: str) -> str:
    return "".join(name.strip().split())


def _industry_filter_from_spec(spec: dict[str, str | tuple[str, ...]]) -> IndustryFilter:
    return IndustryFilter(
        label=str(spec["label"]),
        lcls_cd=str(spec["lcls_cd"]) if spec.get("lcls_cd") else None,
        mcls_cd=str(spec["mcls_cd"]) if spec.get("mcls_cd") else None,
        scls_cds=tuple(spec.get("scls_cds") or ()),
    )


def _resolve_industry_filter(industry: str) -> IndustryFilter | None:
    normalized = _normalize_industry_name(industry)
    if not normalized:
        return None

    alias = INDUSTRY_ALIASES.get(industry.strip()) or INDUSTRY_ALIASES.get(normalized)
    if alias:
        return _industry_filter_from_spec(alias)

    records = _load_industry_codes()

    exact_scls = [record for record in records if _normalize_industry_name(record["scls_nm"]) == normalized]
    if len(exact_scls) == 1:
        record = exact_scls[0]
        return IndustryFilter(label=record["scls_nm"], scls_cds=(record["scls_cd"],))

    exact_mcls = [record for record in records if _normalize_industry_name(record["mcls_nm"]) == normalized]
    if exact_mcls:
        record = exact_mcls[0]
        return IndustryFilter(label=record["mcls_nm"].strip(), mcls_cd=record["mcls_cd"])

    exact_lcls = [record for record in records if _normalize_industry_name(record["lcls_nm"]) == normalized]
    if exact_lcls:
        record = exact_lcls[0]
        return IndustryFilter(label=record["lcls_nm"], lcls_cd=record["lcls_cd"])

    partial_scls = [record for record in records if normalized in _normalize_industry_name(record["scls_nm"])]
    if partial_scls:
        mcls_codes = {record["mcls_cd"] for record in partial_scls}
        if len(mcls_codes) == 1:
            record = partial_scls[0]
            mcls_name = record["mcls_nm"].strip()
            if normalized in _normalize_industry_name(mcls_name):
                return IndustryFilter(label=mcls_name, mcls_cd=record["mcls_cd"])
        return IndustryFilter(
            label=industry.strip(),
            scls_cds=tuple(sorted({record["scls_cd"] for record in partial_scls})),
        )

    partial_mcls = [record for record in records if normalized in _normalize_industry_name(record["mcls_nm"])]
    if partial_mcls:
        mcls_codes = {record["mcls_cd"] for record in partial_mcls}
        if len(mcls_codes) == 1:
            record = partial_mcls[0]
            return IndustryFilter(label=record["mcls_nm"].strip(), mcls_cd=record["mcls_cd"])

    partial_lcls = [record for record in records if normalized in _normalize_industry_name(record["lcls_nm"])]
    if partial_lcls:
        lcls_codes = {record["lcls_cd"] for record in partial_lcls}
        if len(lcls_codes) == 1:
            record = partial_lcls[0]
            return IndustryFilter(label=record["lcls_nm"], lcls_cd=record["lcls_cd"])

    if len(normalized) in (2, 4, 6) and normalized[0].isalpha():
        if len(normalized) == 6:
            record = next((item for item in records if item["scls_cd"] == normalized), None)
            if record:
                return IndustryFilter(label=record["scls_nm"], scls_cds=(record["scls_cd"],))
        if len(normalized) == 4:
            record = next((item for item in records if item["mcls_cd"] == normalized), None)
            if record:
                return IndustryFilter(label=record["mcls_nm"].strip(), mcls_cd=record["mcls_cd"])
        if len(normalized) == 2:
            record = next((item for item in records if item["lcls_cd"] == normalized), None)
            if record:
                return IndustryFilter(label=record["lcls_nm"], lcls_cd=record["lcls_cd"])

    return None


def _industry_ratio(industry_count: int, total_count: int) -> float:
    if total_count <= 0:
        return 0.0
    return industry_count / total_count


def _assess_competition(ratio: float) -> tuple[str, str]:
    """업종 점포 비율 기준 경쟁 밀집도 (level_code, competition_text)."""
    if ratio >= 0.05:
        return "high", "해당 업종 점포 비중이 높아 경쟁 밀집도가 높은 편입니다."
    if ratio >= 0.015:
        return "medium", "경쟁 밀집도는 보통 수준입니다."
    return "low", "해당 업종 점포 비중이 낮아 경쟁 밀집도가 상대적으로 낮은 편입니다."


def _compute_score(industry_count: int, total_count: int) -> int:
    ratio = _industry_ratio(industry_count, total_count)
    if total_count <= 0:
        return 50
    if ratio >= 0.05:
        return 55
    if ratio >= 0.03:
        return 65
    if ratio >= 0.015:
        return 72
    return 80


def _fetch_total_count(client: httpx.Client, signgu_code: str, extra_params: dict[str, str] | None = None) -> int | None:
    params = {
        "serviceKey": settings.sangkwon_api_key,
        "type": "json",
        "pageNo": 1,
        "numOfRows": 1,
        "divId": "signguCd",
        "key": signgu_code,
    }
    if extra_params:
        params.update(extra_params)

    resp = client.get(API_URL, params=params)
    resp.raise_for_status()
    data = resp.json()

    header = data.get("header", {})
    result_code = header.get("resultCode")
    if result_code not in (None, "00", "0"):
        if result_code == "03":
            return 0
        return None

    return int(data.get("body", {}).get("totalCount") or 0)


def _fetch_store_stats_for_code(
    client: httpx.Client,
    signgu_code: str,
    industry_filter: IndustryFilter,
) -> dict | None:
    total_count = _fetch_total_count(client, signgu_code)
    if total_count is None:
        return None

    industry_count = 0
    for query_params in industry_filter.to_query_params():
        count = _fetch_total_count(client, signgu_code, query_params)
        if count is None:
            return None
        industry_count += count

    return {
        "total_count": total_count,
        "industry_count": industry_count,
    }


def _fetch_store_stats(signgu_codes: list[str], industry_filter: IndustryFilter) -> dict | None:
    totals = {"total_count": 0, "industry_count": 0}
    successful_codes = 0

    with httpx.Client(timeout=20.0) as client:
        for signgu_code in signgu_codes:
            stats = _fetch_store_stats_for_code(client, signgu_code, industry_filter)
            if not stats:
                continue
            successful_codes += 1
            totals["total_count"] += stats["total_count"]
            totals["industry_count"] += stats["industry_count"]

    if successful_codes == 0:
        return None
    return totals


def fetch_commercial_district(region: str, industry: str) -> dict:
    """지역·업종 기준 상권 정보 조회."""
    if not settings.sangkwon_api_key:
        return _load_mock(region, industry)

    signgu_codes = _resolve_signgu_codes(region)
    if not signgu_codes:
        return _load_mock(region, industry)

    industry_filter = _resolve_industry_filter(industry)
    if not industry_filter:
        return _load_mock(region, industry)

    try:
        stats = _fetch_store_stats(signgu_codes, industry_filter)
        if not stats:
            return _load_mock(region, industry)

        industry_count = stats["industry_count"]
        total_count = stats["total_count"]
        industry_label = industry_filter.label
        ratio = _industry_ratio(industry_count, total_count)
        ratio_pct = ratio * 100
        score = _compute_score(industry_count, total_count)
        competition_level, competition_text = _assess_competition(ratio)
        summary = (
            f"{region} {industry_label} 업종 상가업소는 {industry_count:,}개"
            f"(전체 {total_count:,}개 중 {ratio_pct:.1f}%, 소진공 상권업종분류 기준)입니다. "
            f"{competition_text}"
        )

        return {
            "summary": summary,
            "score": score,
            "foot_traffic": f"상가업소 {total_count:,}개 기준 활성 상권",
            "competition": (
                f"{industry_label} 업종 {industry_count:,}개, "
                f"전체 대비 {ratio_pct:.1f}%. {competition_text}"
            ),
            "competition_text": competition_text,
            "store_count": industry_count,
            "total_store_count": total_count,
            "competition_ratio": round(ratio, 4),
            "competition_level": competition_level,
            "industry_classification": industry_filter.as_dict(),
            "source": "sangkwon_api",
        }
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError, ValueError, OSError):
        return _load_mock(region, industry)
