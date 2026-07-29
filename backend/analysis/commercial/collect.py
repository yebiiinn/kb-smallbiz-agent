"""소진공 공식 업종코드 · 서울시 추정매출 업종명 수집.

사용법 (backend/analysis/commercial/ 에서 실행):
    python collect.py              # 전체 수집
    python collect.py --step 1     # 소진공 공식 업종코드만
    python collect.py --step 2     # 서울시 업종명만
    python collect.py --step 3     # 소진공-서울 업종 crosswalk

출력 (backend/project/data/):
    industry_codes.json          — 소진공 공식 247개 업종
    seoul_industry_names.json    — 서울시 API 업종명 목록
    industry_crosswalk.json      — 소진공 ↔ 서울 업종 매핑

인증키는 backend/project/.env 에서 자동 로드됩니다.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
from pathlib import Path

import httpx
from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parents[2] / "project" / ".env"
load_dotenv(_ENV_PATH)

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "project" / "data"
SEOUL_SALES_KEY = os.getenv("SEOUL_SALES_API_KEY", "")

OFFICIAL_INDUSTRY_CSV_URL = (
    "https://www.data.go.kr/cmm/cmm/fileDownload.do"
    "?atchFileId=FILE_000000002719340&fileDetailSn=1&insertDataPrcus=N"
)
SEOUL_SERVICE_NAME = "VwsmSignguSelngW"
SEOUL_API_TEMPLATE = (
    "http://openapi.seoul.go.kr:8088/{key}/json/{service}/{start}/{end}/SIGNGU_CD/{signgu_code}"
)

# 소진공·서울 업종명 체계가 달라 자동 매칭이 안 되는 대표 케이스
MANUAL_SEOUL_OVERRIDES: dict[str, list[str]] = {
    "I21201": ["커피-음료"],  # 카페
    "I21001": ["한식음식점"],  # 한식 (대표)
    "I21002": ["중식음식점"],  # 중식 (대표)
    "I21003": ["양식음식점"],  # 양식 (대표)
    "I21004": ["일식음식점"],  # 일식 (대표)
    "I21005": ["패스트푸드점"],  # 패스트푸드 (대표)
}

SEOUL_SIGNGU_CODES: dict[str, str] = {
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


def _normalize_text(value: str) -> str:
    return re.sub(r"[\s\-_/·]", "", value.strip().lower())


def _tokenize(value: str) -> set[str]:
    parts = re.split(r"[\s\-_/·]+", value.strip())
    tokens = {_normalize_text(part) for part in parts if part.strip()}
    return {token for token in tokens if len(token) >= 2}


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    print(f"[saved] {path}")


def collect_official_industry_codes() -> list[dict]:
    """공공데이터포털 공식 CSV → industry_codes.json."""
    print("[step 1] 소진공 공식 업종코드 다운로드...")
    response = httpx.get(OFFICIAL_INDUSTRY_CSV_URL, timeout=60)
    response.raise_for_status()

    text = response.content.decode("cp949")
    reader = csv.DictReader(io.StringIO(text))
    records: list[dict] = []
    for row in reader:
        records.append(
            {
                "lcls_cd": row["대분류코드"].strip(),
                "lcls_nm": row["대분류명"].strip(),
                "mcls_cd": row["중분류코드"].strip(),
                "mcls_nm": row["중분류명"].strip(),
                "scls_cd": row["소분류코드"].strip(),
                "scls_nm": row["소분류명"].strip(),
            }
        )

    _write_json(OUTPUT_DIR / "industry_codes.json", records)
    print(f"  → {len(records)}개 업종 (공식 247개)")
    return records


def _fetch_seoul_rows(client: httpx.Client, signgu_code: str) -> list[dict]:
    if not SEOUL_SALES_KEY:
        raise RuntimeError("SEOUL_SALES_API_KEY가 .env에 없습니다.")

    url = SEOUL_API_TEMPLATE.format(
        key=SEOUL_SALES_KEY,
        service=SEOUL_SERVICE_NAME,
        start=1,
        end=1000,
        signgu_code=signgu_code,
    )
    response = client.get(url, timeout=20)
    response.raise_for_status()
    data = response.json()

    result = data.get("RESULT")
    if result and str(result.get("CODE", "")).startswith("ERROR"):
        raise RuntimeError(f"서울시 API 오류 ({signgu_code}): {result}")

    block = data.get(SEOUL_SERVICE_NAME) or {}
    rows = block.get("row", [])
    if isinstance(rows, dict):
        return [rows]
    return rows or []


def collect_seoul_industry_names() -> list[str]:
    """서울 25개 자치구 API → seoul_industry_names.json."""
    print("[step 2] 서울시 업종명 수집 (25개 자치구)...")
    names: set[str] = set()

    with httpx.Client(timeout=20) as client:
        for signgu_name, signgu_code in SEOUL_SIGNGU_CODES.items():
            rows = _fetch_seoul_rows(client, signgu_code)
            district_names = {
                str(row.get("SVC_INDUTY_CD_NM", "")).strip()
                for row in rows
                if row.get("SVC_INDUTY_CD_NM")
            }
            names.update(district_names)
            print(f"  {signgu_name}: {len(district_names)}개 업종")

    sorted_names = sorted(names)
    payload = {
        "source": "seoul_sales_api",
        "service": SEOUL_SERVICE_NAME,
        "district_count": len(SEOUL_SIGNGU_CODES),
        "industry_count": len(sorted_names),
        "names": sorted_names,
    }
    _write_json(OUTPUT_DIR / "seoul_industry_names.json", payload)
    print(f"  → 총 {len(sorted_names)}개 고유 업종명")
    return sorted_names


def _score_name_match(source: str, target: str) -> int:
    source_norm = _normalize_text(source)
    target_norm = _normalize_text(target)
    if not source_norm or not target_norm:
        return 0
    if source_norm == target_norm:
        return 100
    if source_norm in target_norm or target_norm in source_norm:
        return 80
    if target_norm == f"{source_norm}전문점" or target_norm.startswith(source_norm):
        return 75

    source_tokens = _tokenize(source)
    target_tokens = _tokenize(target)
    if not source_tokens or not target_tokens:
        return 0

    overlap = source_tokens & target_tokens
    if overlap:
        return 60 + min(20, len(overlap) * 5)
    return 0


def build_industry_crosswalk(
    industry_records: list[dict],
    seoul_names: list[str],
) -> list[dict]:
    """소진공 소분류명 ↔ 서울시 업종명 자동 매핑."""
    print("[step 3] 소진공-서울 업종 crosswalk 생성...")
    crosswalk: list[dict] = []

    for record in industry_records:
        candidates: list[tuple[int, str]] = []
        for seoul_name in seoul_names:
            score = max(
                _score_name_match(record["scls_nm"], seoul_name),
                _score_name_match(record["mcls_nm"], seoul_name),
                _score_name_match(record["lcls_nm"], seoul_name),
            )
            if score >= 60:
                candidates.append((score, seoul_name))

        for manual_name in MANUAL_SEOUL_OVERRIDES.get(record["scls_cd"], []):
            if manual_name in seoul_names:
                candidates.append((100, manual_name))

        candidates.sort(key=lambda item: (-item[0], item[1]))
        seen: set[str] = set()
        matched_names: list[str] = []
        for _, name in candidates:
            if name not in seen:
                seen.add(name)
                matched_names.append(name)
            if len(matched_names) >= 5:
                break

        crosswalk.append(
            {
                "scls_cd": record["scls_cd"],
                "scls_nm": record["scls_nm"],
                "mcls_nm": record["mcls_nm"],
                "lcls_nm": record["lcls_nm"],
                "seoul_names": matched_names,
                "search_terms": sorted(
                    {
                        record["scls_nm"],
                        record["mcls_nm"],
                        record["lcls_nm"],
                        *matched_names,
                    }
                ),
            }
        )

    matched_count = sum(1 for item in crosswalk if item["seoul_names"])
    payload = {
        "source": "generated_by_collect.py",
        "matched_count": matched_count,
        "total_count": len(crosswalk),
        "items": crosswalk,
    }
    _write_json(OUTPUT_DIR / "industry_crosswalk.json", payload)
    print(f"  → {matched_count}/{len(crosswalk)}개 소진공 업종에 서울 매칭")
    return crosswalk


def main() -> None:
    parser = argparse.ArgumentParser(description="상권 업종 데이터 수집")
    parser.add_argument("--step", type=int, choices=[1, 2, 3], help="특정 단계만 실행")
    args = parser.parse_args()

    industry_records: list[dict] | None = None
    seoul_names: list[str] | None = None

    if args.step in (None, 1):
        industry_records = collect_official_industry_codes()
    if args.step in (None, 2):
        seoul_names = collect_seoul_industry_names()
    if args.step in (None, 3):
        if industry_records is None:
            industry_records = json.loads((OUTPUT_DIR / "industry_codes.json").read_text(encoding="utf-8"))
        if seoul_names is None:
            seoul_payload = json.loads((OUTPUT_DIR / "seoul_industry_names.json").read_text(encoding="utf-8"))
            seoul_names = seoul_payload["names"]
        build_industry_crosswalk(industry_records, seoul_names)

    print("\n완료.")


if __name__ == "__main__":
    main()
