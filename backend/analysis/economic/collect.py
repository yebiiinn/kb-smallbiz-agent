"""
ECOS(한국은행) · KOSIS(통계청) 경기지표 시계열 수집 및 상관관계 분석
KB Future Finance AI Challenge — 경기지표·소비트렌드 분석 에이전트 사전 데이터 분석

사용법 (backend/analysis/economic/ 에서 실행):
    python collect.py           # 1단계 탐색만 실행
    python collect.py --step 2  # 2단계
    python collect.py --step 3  # 3단계
    python collect.py --step 4  # 4단계

출력:
    data/merged_indicators.csv   — 36개월 × 18개 지표 병합 데이터
    data/correlation_summary.csv — |r| ≥ 0.4 유의미한 상관 조합

인증키는 backend/project/.env 에서 자동 로드됩니다.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pandas as pd
from dotenv import load_dotenv

# ── 환경변수 로드 (.env 위치: backend/project/.env) ──────────────────────────
_ENV_PATH = Path(__file__).resolve().parent.parent / "project" / ".env"
load_dotenv(_ENV_PATH)

ECOS_KEY = os.getenv("ECOS_API_KEY", "")
KOSIS_KEY = os.getenv("KOSIS_API_KEY", "")

if not ECOS_KEY:
    print("[WARNING] ECOS_API_KEY가 .env에 없습니다.")
if not KOSIS_KEY:
    print("[WARNING] KOSIS_API_KEY가 .env에 없습니다.")

# ── ECOS API 엔드포인트 ───────────────────────────────────────────────────────
ECOS_BASE = "https://ecos.bok.or.kr/api"

# ── KOSIS API 엔드포인트 ──────────────────────────────────────────────────────
KOSIS_BASE = "https://kosis.kr/openapi"

# ── 타깃 코드 딕셔너리 (1단계 탐색으로 확정된 코드) ─────────────────────────
# ECOS: {label: {"stat_code": ..., "item_code": ..., "item_code2": ..., "cycle": "M"}}
ECOS_TARGETS: dict[str, dict] = {
    # ── 통화·금리 ────────────────────────────────────────────────────────────
    "기준금리": {
        "stat_code": "722Y001", "item_code": "0101000", "item_code2": "", "cycle": "M",
    },
    # ── 물가 ─────────────────────────────────────────────────────────────────
    "소비자물가지수": {
        "stat_code": "901Y009", "item_code": "0", "item_code2": "", "cycle": "M",
    },
    "생산자물가지수": {           # 소상공인 원가(식자재·원자재) 변동 파악
        "stat_code": "404Y014", "item_code": "*AA", "item_code2": "", "cycle": "M",
    },
    # ── 환율 ─────────────────────────────────────────────────────────────────
    "원달러환율": {               # 수입 식자재·원자재 가격에 직접 영향
        "stat_code": "731Y004", "item_code": "0000001", "item_code2": "", "cycle": "M",
    },
    # ── 소비자 심리 (CSI) ────────────────────────────────────────────────────
    "현재경기판단CSI": {
        "stat_code": "511Y002", "item_code": "FMAB", "item_code2": "99988", "cycle": "M",
    },
    "향후경기전망CSI": {
        "stat_code": "511Y002", "item_code": "FMBB", "item_code2": "99988", "cycle": "M",
    },
    "외식비지출전망CSI": {        # 음식점·주점 업종 직접 선행지표
        "stat_code": "511Y002", "item_code": "FMCCC", "item_code2": "99988", "cycle": "M",
    },
    "여행비지출전망CSI": {        # 숙박·여행 업종 선행지표
        "stat_code": "511Y002", "item_code": "FMCCD", "item_code2": "99988", "cycle": "M",
    },
    # ── 기업경기 (BSI) ───────────────────────────────────────────────────────
    "BSI_서비스업전망": {         # 서비스업 소속 소상공인 경기 체감
        "stat_code": "512Y014", "item_code": "Y9950", "item_code2": "BA", "cycle": "M",
    },
    "BSI_중소기업전망": {         # 중소·소상공인 자금 수요 예측
        "stat_code": "512Y014", "item_code": "X6000", "item_code2": "BA", "cycle": "M",
    },
}

# KOSIS: {label: {"tbl_id": ..., "org_id": ..., "itm_id": ..., "obj_l1": ...}}
KOSIS_TARGETS: dict[str, dict] = {
    # ── 소매 판매 (업태별 불변지수) ─────────────────────────────────────────
    "소매판매_편의점": {
        "tbl_id": "DT_1K41013", "org_id": "101",
        "itm_id": "T2", "obj_l1": "A5", "prd_se": "M",
    },
    "소매판매_전문소매점": {
        "tbl_id": "DT_1K41013", "org_id": "101",
        "itm_id": "T2", "obj_l1": "A7", "prd_se": "M",
    },
    "소매판매_무점포소매": {
        "tbl_id": "DT_1K41013", "org_id": "101",
        "itm_id": "T2", "obj_l1": "A8", "prd_se": "M",
    },
    # ── 서비스업 생산 (산업별 불변지수) ─────────────────────────────────────
    "서비스업생산_음식점주점": {
        "tbl_id": "DT_1KC2020", "org_id": "101",
        "itm_id": "T2", "obj_l1": "I56", "prd_se": "M",
    },
    "서비스업생산_교육서비스": {
        "tbl_id": "DT_1KC2020", "org_id": "101",
        "itm_id": "T2", "obj_l1": "P", "prd_se": "M",
    },
    "서비스업생산_개인서비스": {
        "tbl_id": "DT_1KC2020", "org_id": "101",
        "itm_id": "T2", "obj_l1": "S96", "prd_se": "M",
    },
    "서비스업생산_총지수": {
        "tbl_id": "DT_1KC2020", "org_id": "101",
        "itm_id": "T2", "obj_l1": "T", "prd_se": "M",
    },
    # ── 고용 ─────────────────────────────────────────────────────────────────
    "실업률": {                   # 소비 여력·경기 압박 동행 지표
        "tbl_id": "DT_1DA7001S", "org_id": "101",
        "itm_id": "T80", "obj_l1": "0", "prd_se": "M",
    },
}

# ── 기간 설정 ─────────────────────────────────────────────────────────────────
END_DATE = datetime.today()
START_DATE = END_DATE - timedelta(days=3 * 365)   # 최근 3년
START_STR = START_DATE.strftime("%Y%m")
END_STR = END_DATE.strftime("%Y%m")

print(f"[설정] 수집 기간: {START_STR} ~ {END_STR}")

# =============================================================================
# 1단계: 통계표코드 탐색 함수
# =============================================================================


def find_ecos_table(keyword: str, max_rows: int = 100) -> pd.DataFrame:
    """ECOS StatisticTableList 에서 키워드로 통계표 검색.

    ECOS API 형식: /StatisticTableList/{key}/{fmt}/{lang}/{start}/{end}/Y/{keyword}

    Returns
    -------
    pd.DataFrame  columns: [STAT_CODE, STAT_NAME, CYCLE, ORG_NAME, ...]
    """
    import urllib.parse
    encoded_keyword = urllib.parse.quote(keyword)
    url = (
        f"{ECOS_BASE}/StatisticTableList"
        f"/{ECOS_KEY}/json/kr/1/{max_rows}/Y/{encoded_keyword}"
    )
    print(f"\n[ECOS 탐색] 키워드: '{keyword}'")
    print(f"  URL: {url}")
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()

        if "RESULT" in data and "CODE" in data["RESULT"]:
            err = data["RESULT"]
            print(f"  [API 에러] {err['CODE']}: {err['MESSAGE']}")
            return pd.DataFrame()

        rows = data.get("StatisticTableList", {}).get("row", [])
        if not rows:
            print(f"  → 결과 없음 (응답 키: {list(data.keys())})")
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        print(f"  → {len(df)}개 통계표 발견")
        display_cols = [c for c in ["STAT_CODE", "STAT_NAME", "CYCLE", "ORG_NAME"] if c in df.columns]
        pd.set_option("display.max_colwidth", 40)
        print(df[display_cols].to_string(index=False))
        return df

    except httpx.HTTPError as e:
        print(f"  [HTTP 에러] {e}")
        return pd.DataFrame()
    except Exception as e:
        print(f"  [에러] {e}")
        return pd.DataFrame()


def find_ecos_items(stat_code: str) -> pd.DataFrame:
    """ECOS StatisticItemList — 특정 통계표의 항목코드 조회.

    Returns
    -------
    pd.DataFrame  columns: [ITEM_CODE, ITEM_NAME, ...]
    """
    url = f"{ECOS_BASE}/StatisticItemList/{ECOS_KEY}/json/kr/1/500/{stat_code}"
    print(f"\n[ECOS 항목조회] stat_code={stat_code}")
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()

        rows = data.get("StatisticItemList", {}).get("row", [])
        if not rows:
            print(f"  → 항목 없음 (응답: {list(data.keys())})")
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        display_cols = [c for c in ["ITEM_CODE", "ITEM_NAME", "ITEM_NAME2", "ITEM_NAME3"] if c in df.columns]
        print(df[display_cols].to_string(index=False))
        return df

    except Exception as e:
        print(f"  [에러] {e}")
        return pd.DataFrame()


def find_kosis_table(keyword: str, max_rows: int = 100) -> pd.DataFrame:
    """KOSIS statisticsSearch 에서 키워드로 통계표 검색.

    Returns
    -------
    pd.DataFrame  columns: [tblId, tblNm, statsNm, ...]
    """
    url = f"{KOSIS_BASE}/statisticsSearch.do"
    params = {
        "method": "getList",
        "apiKey": KOSIS_KEY,
        "searchNm": keyword,
        "format": "json",
        "jsonVD": "Y",
        "startPage": 1,
        "resultCnt": max_rows,
        "vwCd": "MT_ZTITLE",
    }
    print(f"\n[KOSIS 탐색] 키워드: '{keyword}'")
    print(f"  URL: {url}")
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            rows = data.get("result", data.get("row", []))
        else:
            rows = []

        if not rows:
            print(f"  → 결과 없음 (응답 타입: {type(data)}, 내용: {str(data)[:200]})")
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        print(f"  → {len(df)}개 통계표 발견")
        # KOSIS 응답 컬럼은 대문자 형태: TBL_ID, TBL_NM, STAT_NM, ORG_NM 등
        display_cols = [
            c for c in ["TBL_ID", "TBL_NM", "STAT_NM", "ORG_NM", "STRT_PRD_DE", "END_PRD_DE"]
            if c in df.columns
        ]
        pd.set_option("display.max_colwidth", 40)
        print(df[display_cols].head(20).to_string(index=False))
        return df

    except httpx.HTTPError as e:
        print(f"  [HTTP 에러] {e}")
        return pd.DataFrame()
    except Exception as e:
        print(f"  [에러] {type(e).__name__}: {e}")
        return pd.DataFrame()


def find_kosis_items(tbl_id: str) -> pd.DataFrame:
    """KOSIS statisticsItemList — 특정 통계표의 분류/항목 조회."""
    url = f"{KOSIS_BASE}/Param/statisticsParamList.do"
    params = {
        "method": "getList",
        "apiKey": KOSIS_KEY,
        "tblId": tbl_id,
        "format": "json",
        "jsonVD": "Y",
    }
    print(f"\n[KOSIS 항목조회] tblId={tbl_id}")
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            rows = data.get("row", data.get("result", []))
            df = pd.DataFrame(rows)
        else:
            df = pd.DataFrame()

        if df.empty:
            print(f"  → 항목 없음 (응답: {str(data)[:300]})")
        else:
            print(df.to_string(index=False))
        return df

    except Exception as e:
        print(f"  [에러] {type(e).__name__}: {e}")
        return pd.DataFrame()


# =============================================================================
# 2단계: 데이터 수집 함수
# =============================================================================


def collect_ecos_series(
    label: str,
    stat_code: str,
    item_code: str,
    item_code2: str = "",
    cycle: str = "M",
    start: str = START_STR,
    end: str = END_STR,
) -> pd.Series:
    """ECOS StatisticSearch 로 단일 시계열 수집.

    item_code2 가 있으면 URL 끝에 추가 (CSI 전국 집계 등 세부 분류 지정 시 사용).

    Returns
    -------
    pd.Series  index=기간(str), name=label
    """
    extra = f"/{item_code2}" if item_code2 else ""
    url = (
        f"{ECOS_BASE}/StatisticSearch"
        f"/{ECOS_KEY}/json/kr/1/10000"
        f"/{stat_code}/{cycle}/{start}/{end}"
        f"/{item_code}{extra}"
    )
    print(f"  [ECOS] {label}")
    print(f"         {url}")
    try:
        with httpx.Client(timeout=20) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()

        if "RESULT" in data and "CODE" in data["RESULT"]:
            err = data["RESULT"]
            print(f"    [API 에러] {err['CODE']}: {err['MESSAGE']}")
            return pd.Series(name=label)

        rows = data.get("StatisticSearch", {}).get("row", [])
        if not rows:
            print(f"    → 데이터 없음 (응답 키: {list(data.keys())})")
            return pd.Series(name=label)

        df = pd.DataFrame(rows)
        # TIME 기준으로 중복 있으면 첫 번째 값 사용 (세부 분류 미지정 시 여러 행 반환 방지)
        df = df.drop_duplicates(subset="TIME", keep="first")
        print(f"    → {len(df)}행 수집  컬럼: {list(df.columns)}")
        series = pd.to_numeric(df["DATA_VALUE"], errors="coerce")
        series.index = df["TIME"].values
        series.name = label
        return series

    except Exception as e:
        print(f"    [에러] {type(e).__name__}: {e}")
        return pd.Series(name=label)


def collect_kosis_series(
    label: str,
    tbl_id: str,
    itm_id: str,
    obj_l1: str,
    org_id: str = "101",
    obj_l2: str = "",
    start: str = START_STR,
    end: str = END_STR,
    prd_se: str = "M",
) -> pd.Series:
    """KOSIS statisticsParameterData 로 단일 시계열 수집.

    orgId 는 필수 파라미터임 (누락 시 API 에러 발생).

    Returns
    -------
    pd.Series  index=기간(str), name=label
    """
    url = f"{KOSIS_BASE}/Param/statisticsParameterData.do"
    params: dict = {
        "method": "getList",
        "apiKey": KOSIS_KEY,
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

    print(f"  [KOSIS] {label}  tblId={tbl_id} itmId={itm_id} objL1={obj_l1}")
    try:
        with httpx.Client(timeout=20) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        if isinstance(data, dict) and "err" in data:
            print(f"    [API 에러] {data}")
            return pd.Series(name=label)

        rows = data if isinstance(data, list) else data.get("row", data.get("result", []))

        if not rows:
            print(f"    → 데이터 없음 (응답: {str(data)[:200]})")
            return pd.Series(name=label)

        df = pd.DataFrame(rows)
        print(f"    → {len(df)}행 수집  컬럼: {list(df.columns)}")

        # KOSIS 실제 컬럼명: PRD_DE (기간), DT (값)
        date_col = next((c for c in ["PRD_DE", "prdDe", "TIME"] if c in df.columns), None)
        val_col = next((c for c in ["DT", "DATA_VALUE", "dataValue"] if c in df.columns), None)

        if not date_col or not val_col:
            print(f"    [주의] 기간/값 컬럼 미발견. 전체 컬럼: {list(df.columns)}")
            print(df.head(3).to_string())
            return pd.Series(name=label)

        series = pd.to_numeric(df[val_col], errors="coerce")
        series.index = df[date_col].values
        series.name = label
        return series

    except Exception as e:
        print(f"    [에러] {type(e).__name__}: {e}")
        return pd.Series(name=label)


# =============================================================================
# 3단계: 전체 수집 및 병합
# =============================================================================


def collect_all() -> pd.DataFrame:
    """ECOS_TARGETS, KOSIS_TARGETS 의 모든 시계열을 날짜 기준으로 병합."""
    print("\n" + "=" * 60)
    print("3단계: 전체 데이터 수집 및 병합")
    print("=" * 60)

    if not ECOS_TARGETS and not KOSIS_TARGETS:
        print("[ERROR] ECOS_TARGETS, KOSIS_TARGETS 가 모두 비어있습니다.")
        print("        2단계 설정을 먼저 완료하세요.")
        return pd.DataFrame()

    all_series: list[pd.Series] = []

    print("\n[ECOS 수집]")
    for label, cfg in ECOS_TARGETS.items():
        s = collect_ecos_series(
            label=label,
            stat_code=cfg["stat_code"],
            item_code=cfg["item_code"],
            item_code2=cfg.get("item_code2", ""),
            cycle=cfg.get("cycle", "M"),
        )
        if not s.empty:
            all_series.append(s)

    print("\n[KOSIS 수집]")
    for label, cfg in KOSIS_TARGETS.items():
        s = collect_kosis_series(
            label=label,
            tbl_id=cfg["tbl_id"],
            itm_id=cfg["itm_id"],
            obj_l1=cfg["obj_l1"],
            org_id=cfg.get("org_id", "101"),
            obj_l2=cfg.get("obj_l2", ""),
            prd_se=cfg.get("prd_se", "M"),
        )
        if not s.empty:
            all_series.append(s)

    if not all_series:
        print("[ERROR] 수집된 시계열이 없습니다.")
        return pd.DataFrame()

    merged = pd.DataFrame({s.name: s for s in all_series})
    merged.index.name = "기간"
    merged = merged.sort_index()

    print("\n[병합 결과]")
    print(f"  행 수: {len(merged)}, 열 수: {len(merged.columns)}")
    print(f"  기간: {merged.index.min()} ~ {merged.index.max()}")
    print("\n[결측치 현황]")
    print(merged.isnull().sum().rename("결측치수").to_frame().T.to_string())
    print("\n[첫 5행]")
    print(merged.head())

    # CSV 저장
    out_path = Path(__file__).resolve().parent / "data" / "merged_indicators.csv"
    merged.to_csv(out_path, encoding="utf-8-sig")
    print(f"\n  → 저장 완료: {out_path}")

    return merged


# =============================================================================
# 4단계: 상관관계 분석
# =============================================================================


def correlation_report(df: pd.DataFrame, threshold: float = 0.4) -> pd.DataFrame:
    """Pearson 상관계수 매트릭스를 계산하고, 절댓값 ≥ threshold 인 조합을 요약."""
    print("\n" + "=" * 60)
    print("4단계: 상관관계 분석")
    print("=" * 60)

    if df.empty:
        print("[ERROR] 입력 데이터프레임이 비어있습니다.")
        return pd.DataFrame()

    corr = df.corr(method="pearson", numeric_only=True)

    print("\n[상관계수 매트릭스]")
    print(corr.round(3).to_string())

    # 절댓값 threshold 이상인 조합 추출 (대각선 · 중복 제거)
    pairs = []
    cols = corr.columns.tolist()
    for i, c1 in enumerate(cols):
        for j, c2 in enumerate(cols):
            if j <= i:
                continue
            val = corr.loc[c1, c2]
            if abs(val) >= threshold:
                pairs.append({"지표A": c1, "지표B": c2, "상관계수": round(val, 4)})

    if not pairs:
        print(f"\n  → |상관계수| ≥ {threshold} 인 조합 없음")
        return corr

    summary = pd.DataFrame(pairs).sort_values("상관계수", key=abs, ascending=False)
    print(f"\n[|상관계수| ≥ {threshold} 인 조합]")
    print(summary.to_string(index=False))

    print("\n[해석 요약]")
    for _, row in summary.iterrows():
        direction = "양의" if row["상관계수"] > 0 else "음의"
        strength = (
            "매우 강한" if abs(row["상관계수"]) >= 0.7
            else "중간 수준의" if abs(row["상관계수"]) >= 0.5
            else "약한"
        )
        print(
            f"  · {row['지표A']} ↔ {row['지표B']}: "
            f"{strength} {direction} 상관관계 ({row['상관계수']:+.3f})"
        )

    out_path = Path(__file__).resolve().parent / "data" / "correlation_summary.csv"
    summary.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\n  → 요약 저장: {out_path}")
    return corr


# =============================================================================
# 1단계 실행: 통계표코드 탐색
# =============================================================================


def run_step1() -> None:
    print("\n" + "=" * 60)
    print("1단계: 통계표코드 탐색")
    print("=" * 60)

    # ── ECOS 탐색 ─────────────────────────────────────────────────────────
    print("\n▶ ECOS: 기준금리")
    find_ecos_table("기준금리")

    print("\n▶ ECOS: 소비자물가지수")
    find_ecos_table("소비자물가지수")

    print("\n▶ ECOS: 소비자동향지수")
    find_ecos_table("소비자동향지수")

    # ── KOSIS 탐색 ────────────────────────────────────────────────────────
    print("\n▶ KOSIS: 소매판매액지수")
    find_kosis_table("소매판매액지수")

    print("\n▶ KOSIS: 서비스업생산지수")
    find_kosis_table("서비스업생산지수")

    print("\n" + "=" * 60)
    print("1단계 완료. 위 결과에서 사용할 코드를 확인하세요.")
    print("다음: python economic_indicator_analysis.py --step 2")
    print("=" * 60)


# =============================================================================
# 2단계 실행: 코드 확정 후 수집 검증
# =============================================================================


def run_step2() -> None:
    print("\n" + "=" * 60)
    print("2단계: 코드 확정 및 수집 함수 검증")
    print("=" * 60)

    if not ECOS_TARGETS:
        print("[INFO] ECOS_TARGETS 가 비어있습니다.")
        print("       1단계 결과를 보고 이 파일의 ECOS_TARGETS / KOSIS_TARGETS 를 채워주세요.")
        return
    if not KOSIS_TARGETS:
        print("[INFO] KOSIS_TARGETS 가 비어있습니다.")
        print("       1단계 결과를 보고 이 파일의 KOSIS_TARGETS 를 채워주세요.")
        return

    print("\n[ECOS 검증 — 최근 3개월 샘플]")
    sample_end = END_STR
    sample_start = (datetime.today() - timedelta(days=90)).strftime("%Y%m")
    for label, cfg in ECOS_TARGETS.items():
        collect_ecos_series(
            label, cfg["stat_code"], cfg["item_code"],
            cfg.get("item_code2", ""), cfg.get("cycle", "M"),
            sample_start, sample_end,
        )

    print("\n[KOSIS 검증 — 최근 3개월 샘플]")
    for label, cfg in KOSIS_TARGETS.items():
        collect_kosis_series(
            label, cfg["tbl_id"], cfg["itm_id"], cfg["obj_l1"],
            cfg.get("org_id", "101"), cfg.get("obj_l2", ""),
            sample_start, sample_end,
        )

    print("\n2단계 완료. 결과 확인 후 collect_all() 로 진행하세요.")


# =============================================================================
# 진입점
# =============================================================================


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="경기지표 수집·분석 스크립트")
    parser.add_argument("--step", type=int, default=1, choices=[1, 2, 3, 4],
                        help="실행할 단계 (1~4, 기본값=1)")
    args = parser.parse_args()

    if args.step == 1:
        run_step1()
    elif args.step == 2:
        run_step2()
    elif args.step == 3:
        df = collect_all()
    elif args.step == 4:
        csv_path = Path(__file__).resolve().parent / "data" / "merged_indicators.csv"
        if not csv_path.exists():
            print("[ERROR] data/merged_indicators.csv 가 없습니다. 3단계를 먼저 실행하세요.")
            sys.exit(1)
        df = pd.read_csv(csv_path, index_col="기간", encoding="utf-8-sig")
        correlation_report(df)
