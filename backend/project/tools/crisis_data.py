"""위기진단용 수집 데이터 조회 — data/crisis/*.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from statistics import median

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "crisis"
SIGNGU_CODES_PATH = Path(__file__).resolve().parent.parent / "data" / "signgu_codes.json"

SIDO_ALIASES: dict[str, str] = {
    "서울": "서울",
    "서울특별시": "서울",
    "부산": "부산",
    "부산광역시": "부산",
    "대구": "대구",
    "대구광역시": "대구",
    "인천": "인천",
    "인천광역시": "인천",
    "광주": "광주",
    "광주광역시": "광주",
    "대전": "대전",
    "대전광역시": "대전",
    "울산": "울산",
    "울산광역시": "울산",
    "세종": "세종",
    "세종특별자치시": "세종",
    "세종시": "세종",
    "경기": "경기",
    "경기도": "경기",
    "강원": "강원",
    "강원도": "강원",
    "강원특별자치도": "강원",
    "충북": "충북",
    "충청북도": "충북",
    "충남": "충남",
    "충청남도": "충남",
    "전북": "전북",
    "전라북도": "전북",
    "전북특별자치도": "전북",
    "전남": "전남",
    "전라남도": "전남",
    "경북": "경북",
    "경상북도": "경북",
    "경남": "경남",
    "경상남도": "경남",
    "제주": "제주",
    "제주특별자치도": "제주",
    "제주도": "제주",
}


def _normalize_region(region: str) -> str:
    return " ".join(region.strip().split())


def _detect_sido_short(region: str) -> str | None:
    normalized = _normalize_region(region)
    matches = [(len(alias), short) for alias, short in SIDO_ALIASES.items() if alias in normalized]
    if not matches:
        return None
    return max(matches, key=lambda item: item[0])[1]


def _detect_signgu(region: str) -> str | None:
    normalized = _normalize_region(region)
    if "구" in normalized:
        token = normalized.split()[-1]
        if token.endswith("구"):
            return token
    if "군" in normalized:
        token = normalized.split()[-1]
        if token.endswith("군"):
            return token
    if "시" in normalized:
        parts = [part for part in normalized.split() if part.endswith("시")]
        if parts:
            return parts[-1]
    return None


def _region_matches_sido(region: str, sido_nm: str) -> bool:
    short = _detect_sido_short(region)
    if not short:
        return False
    return short in sido_nm.replace("특별", "").replace("광역", "").replace("자치", "")


def _region_matches_signgu(region: str, signgu_nm: str) -> bool:
    signgu = _detect_signgu(region)
    if not signgu or not signgu_nm:
        return True
    return signgu in signgu_nm or signgu_nm in signgu


def _sido_in_address(address: str, sido_short: str) -> bool:
    normalized = address.replace(" ", "")
    for alias, short in SIDO_ALIASES.items():
        if short == sido_short and alias.replace(" ", "") in normalized:
            return True
    return False


def _education_matches_region(address: str, region: str) -> bool:
    if not address:
        return False
    signgu = _detect_signgu(region)
    sido_short = _detect_sido_short(region)
    if signgu and signgu not in address:
        return False
    if sido_short and not _sido_in_address(address, sido_short):
        return False
    return bool(signgu or sido_short)


@lru_cache(maxsize=1)
def _load_signgu_codes() -> tuple[dict, ...]:
    with open(SIGNGU_CODES_PATH, encoding="utf-8") as file:
        return tuple(json.load(file))


def _resolve_signgu_code(region: str) -> str | None:
    signgu = _detect_signgu(region)
    if not signgu:
        return None
    sido_short = _detect_sido_short(region)
    for entry in _load_signgu_codes():
        if entry.get("sigungu") != signgu:
            continue
        sido = entry.get("sido", "")
        if sido_short:
            sido_key = sido.replace("특별", "").replace("광역", "").replace("자치", "")
            if sido_short not in sido_key:
                continue
        return str(entry.get("code", "")).strip() or None
    return None


def _signgu_code_matches(item_code: str, full_code: str) -> bool:
    item_code = str(item_code or "").strip()
    full_code = str(full_code or "").strip()
    if not item_code or not full_code:
        return False
    if item_code == full_code:
        return True
    if len(full_code) >= 4 and item_code == full_code[:4]:
        return True
    return full_code.startswith(item_code)


@lru_cache(maxsize=1)
def _national_median_market_area() -> float:
    areas = [
        float(item["area_m2"])
        for item in _load_items("growth_markets.json")
        if item.get("area_m2") is not None
    ]
    return float(median(areas)) if areas else 0.0


@lru_cache(maxsize=1)
def _load_items(filename: str) -> tuple[dict, ...]:
    path = DATA_DIR / filename
    with open(path, encoding="utf-8") as file:
        payload = json.load(file)
    return tuple(payload.get("items", []))


def analyze_regional_context(region: str) -> dict:
    """지역별 상권·교육·국토교통부 데이터 집계."""
    major_markets = [
        item
        for item in _load_items("major_markets.json")
        if _region_matches_sido(region, item.get("sido_nm", ""))
        and _region_matches_signgu(region, item.get("signgu_nm", ""))
    ]
    molit_markets = [
        item
        for item in _load_items("molit_major_markets.json")
        if _region_matches_sido(region, item.get("sido_nm", ""))
        and _region_matches_signgu(region, item.get("signgu_nm", ""))
    ]
    signgu_code = _resolve_signgu_code(region)
    growth_markets = [
        item
        for item in _load_items("growth_markets.json")
        if signgu_code
        and (
            _signgu_code_matches(item.get("signgu_cd", ""), signgu_code)
            or str(item.get("dong_cd", "")).startswith(signgu_code)
        )
    ]
    growth_areas = [
        float(item["area_m2"])
        for item in growth_markets
        if item.get("area_m2") is not None
    ]
    avg_growth_area = sum(growth_areas) / len(growth_areas) if growth_areas else None

    education = [
        item
        for item in _load_items("education_institutions.json")
        if _education_matches_region(item.get("address", ""), region)
    ]

    sido_short = _detect_sido_short(region)
    national_count = None
    for item in _load_items("national_market_status.json"):
        if sido_short and item.get("region") == sido_short:
            national_count = item.get("market_count")
            break

    growth_names = [item.get("zone_name", "") for item in growth_markets[:3]]
    sample_names = [item.get("trdar_nm") or item.get("zone_name", "") for item in major_markets[:3]]
    sample_names += [item.get("zone_name", "") for item in molit_markets[:2]]
    sample_names += growth_names

    return {
        "sido_short": sido_short,
        "signgu": _detect_signgu(region),
        "signgu_code": signgu_code,
        "major_market_count": len(major_markets),
        "molit_market_count": len(molit_markets),
        "growth_market_count": len(growth_markets),
        "avg_growth_market_area_m2": avg_growth_area,
        "national_median_market_area_m2": _national_median_market_area(),
        "national_market_count": national_count,
        "education_count": len(education),
        "education_institutions": education[:3],
        "growth_market_names": [name for name in growth_names if name],
        "sample_market_names": [name for name in dict.fromkeys(sample_names) if name][:5],
    }
