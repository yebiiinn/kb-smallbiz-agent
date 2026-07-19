"""소상공인진흥공단(SEMAS) 정책 정보 크롤러.

크롤링 대상:
- SUP010301 : 소상공인 정책자금          → 타임아웃 — seed 데이터로 제공
- SUP010302 : 소상공인 정책자금 상환연장 → ✅ 크롤링 가능
- SUP010303 : 소상공인 경영안정 바우처   → ✅ 크롤링 가능

캐시 전략:
- 파일 기반 JSON 캐시 (data/cache/semas_policy.json)
- TTL 24시간; 만료 또는 크롤링 실패 시 기존 캐시(seed 포함) 반환
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------
_CACHE_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "cache" / "semas_policy.json"
)
_CACHE_TTL_HOURS = 24

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://www.semas.or.kr/",
}
_TIMEOUT = 10.0
_MAX_RETRY = 1

# 크롤링 가능 URL만 포함 (SUP010301은 타임아웃)
_CRAWL_TARGETS: list[dict[str, str]] = [
    {
        "id":  "repayment_extension",
        "url": "https://www.semas.or.kr/web/SUP01/SUP0103/SUP010302.kmdc",
    },
    {
        "id":  "management_voucher",
        "url": "https://www.semas.or.kr/web/SUP01/SUP0103/SUP010303.kmdc",
    },
]

# 섹션 레이블 → 필드명 매핑
_SECTION_MAP: dict[str, str] = {
    "사업목적":  "purpose",
    "사업기간":  "period",
    "지원규모":  "support_scale",
    "지원대상":  "target",
    "지원내용":  "support_content",
    "신청·접수": "application_url",
    "신청·접수": "application_url",
    "문의처":    "contact",
}


# ---------------------------------------------------------------------------
# 저수준 HTTP 헬퍼
# ---------------------------------------------------------------------------
def _fetch_html(url: str) -> str:
    """URL 에서 HTML 텍스트를 가져온다. 실패 시 1회 재시도."""
    for attempt in range(_MAX_RETRY + 1):
        try:
            with httpx.Client(timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True) as client:
                resp = client.get(url)
                resp.raise_for_status()
                return resp.text
        except httpx.HTTPError as exc:
            if attempt < _MAX_RETRY:
                logger.warning("SEMAS 크롤링 재시도 (%s): %s", url, exc)
                time.sleep(1.0)
            else:
                raise


# ---------------------------------------------------------------------------
# 캐시 유틸
# ---------------------------------------------------------------------------
def _now() -> datetime:
    return datetime.now(tz=timezone.utc).astimezone()


def _load_cache() -> dict[str, Any] | None:
    if not _CACHE_PATH.exists():
        return None
    try:
        with open(_CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _is_fresh(cache: dict[str, Any]) -> bool:
    fetched_at = cache.get("fetched_at")
    if not fetched_at:
        return False
    try:
        ts = datetime.fromisoformat(fetched_at)
        return _now() - ts < timedelta(hours=_CACHE_TTL_HOURS)
    except ValueError:
        return False


def _save_cache(programs: list[dict[str, Any]]) -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "fetched_at": _now().isoformat(),
        "programs":   programs,
        "source":     "crawled",
    }
    with open(_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 파싱 헬퍼
# ---------------------------------------------------------------------------
def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _extract_section_text(soup: BeautifulSoup, label: str) -> str:
    """레이블 텍스트와 인접한 다음 텍스트 블록을 반환한다."""
    # th/td 테이블 구조 시도
    for th in soup.find_all(["th", "dt", "strong", "b"]):
        if label in th.get_text(strip=True):
            # 같은 행의 td 또는 다음 dd 탐색
            td = th.find_next_sibling("td") or th.find_next("dd")
            if td:
                return td.get_text(separator=" ", strip=True)
            # 부모 tr의 다음 td들
            parent = th.parent
            if parent:
                tds = parent.find_all("td")
                if tds:
                    return " ".join(td.get_text(separator=" ", strip=True) for td in tds)
    # 텍스트 기반 폴백: label 뒤 첫 번째 의미있는 블록
    full_text = soup.get_text(separator="\n", strip=True)
    lines = full_text.splitlines()
    for i, line in enumerate(lines):
        if label in line:
            # 다음 비어있지 않은 줄들을 수집 (다음 레이블 전까지)
            result_lines: list[str] = []
            for j in range(i + 1, min(i + 8, len(lines))):
                next_line = lines[j].strip()
                if not next_line:
                    continue
                if any(sec in next_line for sec in _SECTION_MAP):
                    break
                result_lines.append(next_line)
            return " ".join(result_lines)
    return ""


def _extract_list_items(soup: BeautifulSoup, label: str) -> list[str]:
    """레이블 이후의 li 항목들을 리스트로 반환한다."""
    label_tag = None
    for tag in soup.find_all(["th", "dt", "strong", "b", "h3", "h4"]):
        if label in tag.get_text(strip=True):
            label_tag = tag
            break

    if not label_tag:
        return []

    items: list[str] = []
    for sib in label_tag.find_all_next(["li", "p", "dd"], limit=20):
        text = sib.get_text(separator=" ", strip=True)
        if not text or len(text) > 200:
            continue
        # 다른 섹션 레이블이 나오면 중단
        if any(sec in text for sec in _SECTION_MAP if sec != label):
            break
        if text not in items:
            items.append(text)
    return items


def _extract_contact(soup: BeautifulSoup) -> str:
    """문의처 전화번호 및 설명을 추출한다."""
    text = soup.get_text(separator=" ", strip=True)
    # 콜센터 패턴: 1357, 1533-XXXX 등
    phones = re.findall(r"(?:콜센터|통합콜센터|전용 콜센터)[^\d]*(\d{4}[-\d]*)", text)
    if phones:
        return " / ".join(phones)
    phones = re.findall(r"☎?\s*(\d{4}-\d{4})", text)
    return " / ".join(dict.fromkeys(phones))  # 중복 제거


def _extract_application_url(soup: BeautifulSoup) -> str:
    """신청 URL 또는 신청 방법 텍스트를 추출한다."""
    # <a> 태그 중 ols.semas, sbiz24, 바우처 관련
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if any(kw in href for kw in ["ols.semas", "sbiz24", "소상공인24", "바우처"]):
            return href
    # 텍스트에서 URL 패턴 추출
    text = soup.get_text(separator=" ", strip=True)
    urls = re.findall(r"https?://[^\s)】】,]+", text)
    if urls:
        return urls[0]
    # 한글 URL (소상공인경영안정바우처.kr 등)
    m = re.search(r"(소상공인\S+\.kr|ols\.semas\.or\.kr|sbiz24\.kr)", text)
    if m:
        return m.group(1)
    return ""


# ---------------------------------------------------------------------------
# 페이지별 파서
# ---------------------------------------------------------------------------
def _parse_page(html: str, program_id: str, url: str) -> dict[str, Any]:
    """SEMAS 지원사업 페이지 1개를 파싱하여 정규화된 dict 를 반환한다."""
    soup = _soup(html)

    # 제목: h3 또는 페이지 타이틀
    title = ""
    h3 = soup.find("h3")
    if h3:
        title = h3.get_text(strip=True)
    if not title:
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text(strip=True).split("〉")[-1].strip()

    result: dict[str, Any] = {
        "id":    program_id,
        "title": title,
        "url":   url,
    }

    # 각 섹션 추출
    for label, field in _SECTION_MAP.items():
        if field in ("support_content",):
            items = _extract_list_items(soup, label)
            if items:
                result[field] = items
        elif field == "contact":
            contact = _extract_contact(soup)
            if contact:
                result[field] = contact
        elif field == "application_url":
            app_url = _extract_application_url(soup)
            if app_url:
                result[field] = app_url
        else:
            text = _extract_section_text(soup, label)
            if text:
                result[field] = text

    return result


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------
def get_semas_programs(force_refresh: bool = False) -> list[dict[str, Any]]:
    """소진공 정책 프로그램 목록을 반환한다.

    캐시(TTL 24시간)를 우선 사용하고, 만료·강제갱신 시 크롤링한다.
    크롤링 실패 항목은 기존 캐시의 해당 항목으로 대체한다.
    SUP010301(정책자금 메인)은 타임아웃으로 seed 데이터를 항상 포함한다.

    Args:
        force_refresh: True 이면 TTL 무시하고 즉시 크롤링.

    Returns:
        정규화된 프로그램 dict 의 리스트.
    """
    cache = _load_cache()

    if not force_refresh and cache and _is_fresh(cache):
        return cache.get("programs", [])

    # 기존 캐시에서 id → 항목 인덱스 구성 (폴백용)
    existing: dict[str, dict[str, Any]] = {}
    if cache:
        for prog in cache.get("programs", []):
            existing[prog["id"]] = prog

    refreshed: list[dict[str, Any]] = []

    for target in _CRAWL_TARGETS:
        prog_id = target["id"]
        url = target["url"]
        try:
            html = _fetch_html(url)
            parsed = _parse_page(html, prog_id, url)
            parsed["source"] = "crawled"
            refreshed.append(parsed)
            logger.info("SEMAS 크롤링 완료: %s (%s)", prog_id, url)
        except Exception as exc:
            logger.warning("SEMAS 크롤링 실패 (%s): %s", url, exc)
            # 기존 캐시 항목으로 폴백
            if prog_id in existing:
                refreshed.append(existing[prog_id])

    # SUP010301(정책자금 메인)은 seed 항목을 항상 삽입 (앞에 배치)
    seed_policy_fund = existing.get(
        "policy_fund",
        {
            "id":    "policy_fund",
            "title": "소상공인 정책자금",
            "url":   "https://www.semas.or.kr/web/SUP01/SUP0103/SUP010301.kmdc",
            "purpose": "소상공인의 경영 안정 및 성장을 위한 시설·운전자금 저금리 융자 지원",
            "target": "업종·매출액·상시근로자수 등 소상공인 요건 충족 사업자",
            "support_content": [
                "직접대출: 소진공이 직접 자금을 대출 (일반경영안정자금, 성장기반자금 등)",
                "대리대출: 시중은행을 통한 정책자금 지원",
            ],
            "application_url": "https://ols.semas.or.kr",
            "contact": "중소기업 통합콜센터 1357 / 소진공 통합콜센터 1533-0100",
            "source": "seed",
        },
    )
    programs = [seed_policy_fund] + refreshed

    _save_cache(programs)
    logger.info("SEMAS 캐시 저장 완료: %d건", len(programs))
    return programs


def search_semas_by_intent(intent: str) -> list[dict[str, Any]]:
    """의도(intent) 에 따라 관련 소진공 프로그램을 반환한다.

    Args:
        intent: 사용자 의도 문자열 (예: "정책자금", "상환 어려움", "경영비용").

    Returns:
        관련 프로그램 dict 의 리스트.
    """
    programs = get_semas_programs()

    _INTENT_KEYWORDS: list[tuple[set[str], str]] = [
        ({"정책자금", "대출", "창업자금", "운전자금", "시설자금"}, "policy_fund"),
        ({"상환", "연장", "코로나", "분할상환", "금리감면"},       "repayment_extension"),
        ({"바우처", "공과금", "보험료", "경영비용", "경영안정"},   "management_voucher"),
    ]

    matched_ids: set[str] = set()
    for keywords, prog_id in _INTENT_KEYWORDS:
        if any(kw in intent for kw in keywords):
            matched_ids.add(prog_id)

    if not matched_ids:
        return programs  # 매칭 없으면 전체 반환

    return [p for p in programs if p.get("id") in matched_ids]
