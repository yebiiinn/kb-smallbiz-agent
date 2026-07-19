"""한국은행 ECOS API — 경기지표 시계열 수집.

검증된 통계표·항목 코드 목록은 project/data/indicator_mapping.json 참조.
"""

from __future__ import annotations

import httpx

from project.config import settings

ECOS_BASE = "https://ecos.bok.or.kr/api"


def _ecos_url(
    stat_code: str,
    item_code: str,
    item_code2: str = "",
    cycle: str = "M",
    start: str = "202301",
    end: str = "202612",
    rows: int = 200,
) -> str:
    extra = f"/{item_code2}" if item_code2 else ""
    return (
        f"{ECOS_BASE}/StatisticSearch"
        f"/{settings.ecos_api_key}/json/kr/1/{rows}"
        f"/{stat_code}/{cycle}/{start}/{end}/{item_code}{extra}"
    )


def fetch_indicator_series(
    stat_code: str,
    item_code: str,
    item_code2: str = "",
    cycle: str = "M",
    start: str = "202301",
    end: str = "202612",
) -> list[dict]:
    """ECOS StatisticSearch 로 단일 지표 시계열 수집.

    Returns
    -------
    list[dict]  [{"time": "202301", "value": 3.5}, ...]
    """
    if not settings.ecos_api_key:
        return []

    url = _ecos_url(stat_code, item_code, item_code2, cycle, start, end)
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()

        if "RESULT" in data and "CODE" in data.get("RESULT", {}):
            return []

        rows = data.get("StatisticSearch", {}).get("row", [])
        seen: set[str] = set()
        result: list[dict] = []
        for row in rows:
            t = row.get("TIME", "")
            if t not in seen:
                seen.add(t)
                try:
                    result.append({"time": t, "value": float(row["DATA_VALUE"])})
                except (ValueError, KeyError):
                    pass
        return result

    except httpx.HTTPError:
        return []


def fetch_economic_indicators() -> dict:
    """소비자심리·기준금리 등 주요 지표 최신값 조회.

    economic_node 에서 호출하는 고수준 인터페이스.
    실제 API 키가 없으면 mock 반환.
    """
    if not settings.ecos_api_key:
        return {
            "summary": "소비자심리지수 98.2 (전월 대비 -1.2), 내수 회복세 둔화",
            "consumer_sentiment": 98.2,
            "base_rate": 2.5,
            "cpi": None,
            "source": "mock",
        }

    try:
        # 최신 3개월만 빠르게 조회
        from datetime import datetime, timedelta
        end = datetime.today().strftime("%Y%m")
        start = (datetime.today() - timedelta(days=90)).strftime("%Y%m")

        csi = fetch_indicator_series("511Y002", "FMAB", "99988", "M", start, end)
        rate = fetch_indicator_series("722Y001", "0101000", "", "M", start, end)
        cpi = fetch_indicator_series("901Y009", "0", "", "M", start, end)

        latest_csi = csi[-1]["value"] if csi else None
        latest_rate = rate[-1]["value"] if rate else None
        latest_cpi = cpi[-1]["value"] if cpi else None

        summary_parts = []
        if latest_csi is not None:
            summary_parts.append(f"현재경기판단CSI {latest_csi:.0f}")
        if latest_rate is not None:
            summary_parts.append(f"기준금리 {latest_rate:.2f}%")
        if latest_cpi is not None:
            summary_parts.append(f"소비자물가지수 {latest_cpi:.2f}")

        return {
            "summary": " / ".join(summary_parts) if summary_parts else "ECOS 조회 완료",
            "consumer_sentiment": latest_csi,
            "base_rate": latest_rate,
            "cpi": latest_cpi,
            "source": "ecos_api",
        }

    except Exception:
        return {
            "summary": "소비자심리지수 98.2 (전월 대비 -1.2), 내수 회복세 둔화",
            "consumer_sentiment": 98.2,
            "base_rate": 2.5,
            "cpi": None,
            "source": "mock",
        }
