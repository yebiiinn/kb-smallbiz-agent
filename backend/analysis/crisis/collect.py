"""위기진단 에이전트용 공공데이터 수집·전처리.

사용법 (backend/analysis/crisis/ 에서 실행):
    python collect.py              # 다운로드 + JSON 변환
    python collect.py --step 1     # 다운로드만
    python collect.py --step 2     # raw → JSON 변환만

출력:
    backend/project/data/crisis/raw/          — 원본(CSV/ZIP/SHP, gitignore)
    backend/project/data/crisis/*.json        — 에이전트용 정제 데이터

데이터 출처:
    - 교육기관 현황 (3060084)
    - 주요상권현황 CSV (15090955, 표준데이터 15029180 대응)
    - 성장상권 SHP (15151047)
    - 전국 상권 현황 (15143727)
    - 소상공인365 / 상권 API → sangkwon storeZoneOne (선택, API 키 필요)
    - 국토교통부 주요상권 (15028102) → VWorld API (VWORLD_API_KEY 필요, 미설정 시 스킵)

인증키: backend/project/.env
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import time
import zipfile
from pathlib import Path

import httpx
from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parents[2] / "project" / ".env"
load_dotenv(_ENV_PATH)

RAW_DIR = Path(__file__).resolve().parents[2] / "project" / "data" / "crisis" / "raw"
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "project" / "data" / "crisis"

SANGKWON_KEY = os.getenv("SANGKWON_API_KEY", "")
VWORLD_KEY = os.getenv("VWORLD_API_KEY", "")
VWORLD_DOMAIN = os.getenv("VWORLD_DOMAIN", "localhost")

DOWNLOADS: dict[str, str] = {
    "education_institutions.csv": (
        "https://www.data.go.kr/cmm/cmm/fileDownload.do"
        "?atchFileId=FILE_000000002588869&fileDetailSn=1&insertDataPrcus=N"
    ),
    "major_markets.csv": (
        "https://www.data.go.kr/cmm/cmm/fileDownload.do"
        "?atchFileId=FILE_000000003211293&fileDetailSn=1&insertDataPrcus=N"
    ),
    "growth_markets.zip": (
        "https://www.data.go.kr/cmm/cmm/fileDownload.do"
        "?atchFileId=FILE_000000003517258&fileDetailSn=1&insertDataPrcus=N"
    ),
    "national_market_status.csv": (
        "https://www.data.go.kr/cmm/cmm/fileDownload.do"
        "?atchFileId=FILE_000000003151548&fileDetailSn=1&insertDataPrcus=N"
    ),
}

GROWTH_SHP_EXTRACT: dict[str, str] = {
    ".dbf": "growth_markets.dbf",
    ".shp": "growth_markets.shp",
    ".shx": "growth_markets.shx",
    ".cpg": "growth_markets.cpg",
}


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    print(f"[saved] {path}")


def download_raw_files() -> None:
    print("[step 1] 공공데이터포털 파일 다운로드...")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=120.0) as client:
        for filename, url in DOWNLOADS.items():
            target = RAW_DIR / filename
            print(f"  → {filename}")
            response = client.get(url)
            response.raise_for_status()
            target.write_bytes(response.content)
            print(f"     {target.stat().st_size:,} bytes")


def _extract_growth_shp() -> Path:
    extract_dir = RAW_DIR / "growth_markets_shp"
    extract_dir.mkdir(parents=True, exist_ok=True)
    zip_path = RAW_DIR / "growth_markets.zip"
    if not zip_path.exists():
        raise FileNotFoundError(f"없음: {zip_path}")

    with zipfile.ZipFile(zip_path) as archive:
        for name in archive.namelist():
            suffix = Path(name).suffix.lower()
            if suffix not in GROWTH_SHP_EXTRACT:
                continue
            target = extract_dir / GROWTH_SHP_EXTRACT[suffix]
            with archive.open(name) as src, open(target, "wb") as dst:
                dst.write(src.read())
    return extract_dir / "growth_markets.dbf"


def _read_dbf_records(dbf_path: Path) -> list[dict]:
    from dbfread import DBF

    records: list[dict] = []
    for record in DBF(str(dbf_path), encoding="utf-8"):
        cleaned: dict = {}
        for key, value in record.items():
            if isinstance(value, str):
                cleaned[key.strip()] = value.strip()
            else:
                cleaned[key.strip()] = value
        records.append(cleaned)
    return records


def process_education_institutions() -> None:
    path = RAW_DIR / "education_institutions.csv"
    rows: list[dict] = []
    with open(path, encoding="cp949") as file:
        reader = csv.DictReader(file)
        for row in reader:
            rows.append(
                {
                    "year": row.get("공고연도", "").strip(),
                    "name": row.get("상호", "").strip(),
                    "address": row.get("소재지", "").strip(),
                    "course": row.get("교육과정", "").strip(),
                }
            )
    _write_json(
        OUTPUT_DIR / "education_institutions.json",
        {
            "source": "data.go.kr/3060084",
            "count": len(rows),
            "items": rows,
        },
    )


def process_major_markets() -> None:
    csv.field_size_limit(sys.maxsize)
    path = RAW_DIR / "major_markets.csv"
    text = path.read_bytes().decode("cp949")
    reader = csv.DictReader(io.StringIO(text))
    items: list[dict] = []
    for row in reader:
        coord_text = row.get("상권좌표", "")
        centroid = _centroid_from_polygon(coord_text)
        items.append(
            {
                "trdar_cd": row.get("상권번호", "").strip(),
                "trdar_nm": row.get("상권명", "").strip(),
                "type": row.get("유형구분", "").strip(),
                "signgu_cd": row.get("시군구코드", "").strip(),
                "signgu_nm": row.get("시군구명", "").strip(),
                "sido_nm": row.get("시도명", "").strip(),
                "coord_count": int(row.get("상권좌표수") or 0),
                "centroid": centroid,
                "base_date": row.get("데이터기준일자", "").strip(),
            }
        )
    _write_json(
        OUTPUT_DIR / "major_markets.json",
        {
            "source": "data.go.kr/15090955",
            "standard_data": "data.go.kr/15029180",
            "count": len(items),
            "items": items,
        },
    )


def _centroid_from_polygon(coord_text: str) -> dict[str, float] | None:
    if not coord_text:
        return None
    points: list[tuple[float, float]] = []
    for chunk in coord_text.split("|"):
        chunk = chunk.strip().lstrip("(").rstrip(")")
        if "," not in chunk:
            continue
        lon_str, lat_str = chunk.split(",", 1)
        try:
            points.append((float(lon_str), float(lat_str)))
        except ValueError:
            continue
    if not points:
        return None
    lon_avg = sum(point[0] for point in points) / len(points)
    lat_avg = sum(point[1] for point in points) / len(points)
    return {"lon": round(lon_avg, 7), "lat": round(lat_avg, 7)}


def process_growth_markets() -> None:
    dbf_path = _extract_growth_shp()
    records = _read_dbf_records(dbf_path)
    items: list[dict] = []
    for row in records:
        items.append(
            {
                "base_ym": str(row.get("CRTR_YM", "")).strip(),
                "zone_no": str(row.get("MJR_BZZNNO", "")).strip(),
                "zone_name": str(row.get("MJR_BIZON_", "")).strip(),
                "market_type": str(row.get("MRKT_SE_NM", "")).strip(),
                "market_cd": str(row.get("MRKT_CD", "")).strip(),
                "center_x": row.get("CENTER_X_C"),
                "center_y": row.get("CENTER_Y_C"),
                "area_m2": row.get("ARA"),
                "signgu_cd": str(row.get("SGG_CD", "")).strip(),
                "dong_cd": str(row.get("DONG_CD", "")).strip(),
            }
        )
    _write_json(
        OUTPUT_DIR / "growth_markets.json",
        {
            "source": "data.go.kr/15151047",
            "note": "공공데이터 SHP는 경계·중심좌표 위주(성장지수 등은 sbiz365 포털 별도)",
            "count": len(items),
            "items": items,
        },
    )


def process_national_market_status() -> None:
    path = RAW_DIR / "national_market_status.csv"
    text = path.read_bytes().decode("cp949")
    rows = list(csv.reader(io.StringIO(text)))
    header = rows[0]
    year_label = header[1] if len(header) > 1 else ""
    items = [
        {"region": row[0].strip(), "market_count": int(row[1])}
        for row in rows[1:]
        if len(row) >= 2 and row[0].strip()
    ]
    _write_json(
        OUTPUT_DIR / "national_market_status.json",
        {
            "source": "data.go.kr/15143727",
            "year": year_label,
            "count": len(items),
            "items": items,
        },
    )


def fetch_sbiz_zone_samples(limit: int = 10) -> None:
    """소상공인365(표준데이터) API — 주요상권 상세 샘플 캐시."""
    if not SANGKWON_KEY:
        print("[skip] SANGKWON_API_KEY 없음 → storeZoneOne 샘플 생략")
        return

    markets_path = OUTPUT_DIR / "major_markets.json"
    if not markets_path.exists():
        print("[skip] major_markets.json 없음")
        return

    markets = json.loads(markets_path.read_text(encoding="utf-8"))["items"][:limit]
    samples: list[dict] = []
    with httpx.Client(timeout=20.0) as client:
        for index, market in enumerate(markets):
            if index > 0:
                time.sleep(0.3)
            trdar_cd = market["trdar_cd"]
            try:
                response = client.get(
                    "http://apis.data.go.kr/B553077/api/open/sdsc2/storeZoneOne",
                    params={
                        "serviceKey": SANGKWON_KEY,
                        "type": "json",
                        "pageNo": 1,
                        "numOfRows": 1,
                        "key": trdar_cd,
                        "divId": "trdArCd",
                    },
                )
                if response.status_code == 429:
                    print(f"[warn] storeZoneOne rate limit — {len(samples)}건만 저장")
                    break
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPError:
                continue

            header = data.get("header", {})
            if header.get("resultCode") not in ("00", "0"):
                continue
            body_items = data.get("body", {}).get("items") or []
            if not body_items:
                continue
            item = body_items[0] if isinstance(body_items, list) else body_items
            samples.append(
                {
                    "trdar_cd": item.get("trarNo") or trdar_cd,
                    "trdar_nm": item.get("mainTrarNm") or market["trdar_nm"],
                    "signgu_cd": item.get("signguCd", market["signgu_cd"]),
                    "signgu_nm": item.get("signguNm", market["signgu_nm"]),
                    "area_m2": item.get("trarArea"),
                    "coord_count": item.get("coordNum"),
                    "base_date": item.get("stdrDt"),
                }
            )
    _write_json(
        OUTPUT_DIR / "sbiz_zone_samples.json",
        {
            "source": "sbiz365 / apis.data.go.kr/B553077/storeZoneOne",
            "sample_limit": limit,
            "count": len(samples),
            "items": samples,
        },
    )


def fetch_molit_major_markets() -> None:
    """국토교통부 주요상권 — VWorld 2D Data API (LT_C_DGMAINBIZ)."""
    if not VWORLD_KEY:
        print("[skip] VWORLD_API_KEY 없음 → 국토교통부 주요상권 API 생략")
        print("       발급: https://www.vworld.kr → 오픈API → 인증키 발급")
        print("       가이드: https://www.vworld.kr/dev/v4dv_2ddataguide2_s002.do?svcIde=dgmainbiz")
        return

    url = "https://api.vworld.kr/req/data"
    page = 1
    page_size = 1000
    all_items: list[dict] = []
    total = None
    geom_filter = "BOX(124.0,33.0,132.0,39.0)"  # 대한민국 전역 (EPSG:4326)

    with httpx.Client(timeout=60.0) as client:
        while True:
            params = {
                "service": "data",
                "version": "2.0",
                "request": "GetFeature",
                "data": "LT_C_DGMAINBIZ",
                "key": VWORLD_KEY,
                "domain": VWORLD_DOMAIN,
                "size": page_size,
                "page": page,
                "geometry": "false",
                "attribute": "true",
                "format": "json",
                "crs": "EPSG:4326",
                "geomFilter": geom_filter,
            }
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()

            response_block = payload.get("response", {})
            if response_block.get("status") == "ERROR":
                error = response_block.get("error", {})
                raise RuntimeError(
                    f"VWorld API 오류 ({error.get('code')}): {error.get('text')}"
                )

            if total is None:
                total = int(response_block.get("record", {}).get("total") or 0)

            feature_collection = response_block.get("result", {}).get("featureCollection", {})
            features = feature_collection.get("features") or []

            for feature in features:
                props = feature.get("properties") or {}
                all_items.append(
                    {
                        "zone_no": str(props.get("no", "")).strip(),
                        "zone_name": str(props.get("nm", "")).strip(),
                        "zone_full_name": str(props.get("fullnm", "")).strip(),
                        "sido_nm": str(props.get("sido", "")).strip(),
                        "signgu_nm": str(props.get("sigg", "")).strip(),
                    }
                )

            print(f"  VWorld page {page}: {len(features)}건 (누적 {len(all_items)}/{total or '?'})")
            if not features or (total and len(all_items) >= total):
                break
            page += 1

    _write_json(
        OUTPUT_DIR / "molit_major_markets.json",
        {
            "source": "data.go.kr/15028102",
            "api": "vworld.kr/req/data",
            "layer": "LT_C_DGMAINBIZ",
            "count": len(all_items),
            "items": all_items,
        },
    )


def process_all() -> None:
    print("[step 2] raw → JSON 변환...")
    process_education_institutions()
    process_major_markets()
    process_growth_markets()
    process_national_market_status()
    fetch_sbiz_zone_samples()
    fetch_molit_major_markets()
    print("\n완료.")


def main() -> None:
    parser = argparse.ArgumentParser(description="위기진단 데이터 수집")
    parser.add_argument("--step", type=int, choices=[1, 2], help="1=다운로드, 2=변환")
    args = parser.parse_args()

    if args.step in (None, 1):
        download_raw_files()
    if args.step in (None, 2):
        process_all()


if __name__ == "__main__":
    main()
