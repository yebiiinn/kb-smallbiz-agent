"""KB국민은행 소상공인 대출상품 크롤러.

크롤링 대상 (httpx GET 가능 확인된 URL):
- C112618 / C112610 : 소상공인 정책자금대출 — 금리·이벤트 (분기별 갱신)
- C016282           : 비대면 사업자 대출상품 허브 — 상품 목록

크롤링 불가 (타임아웃):
- C100265 : KB소상공인 신용대출 — 캐시 seed 데이터로 대체

캐시 전략:
- 파일 기반 JSON 캐시 (data/cache/)
- TTL 24시간; 만료 또는 크롤링 실패 시 기존 캐시 반환
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
_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"
_CACHE_POLICY_FUND  = _CACHE_DIR / "kb_policy_fund.json"
_CACHE_LOAN_PRODUCTS = _CACHE_DIR / "kb_loan_products.json"

_CACHE_TTL_HOURS = 24

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_TIMEOUT = 10.0
_MAX_RETRY = 1

# 크롤링 대상 URL
_URL_POLICY_FUND_PRIMARY = (
    "https://zloan.kbstar.com/quics?page=C112618&CooperCD=A000115"
)
_URL_POLICY_FUND_FALLBACK = "https://obiz.kbstar.com/quics?page=C112610"
_URL_LOAN_HUB = "https://obiz.kbstar.com/quics?page=C016282"


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
                logger.warning("KB 크롤링 재시도 (%s): %s", url, exc)
                time.sleep(1.0)
            else:
                raise


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


# ---------------------------------------------------------------------------
# 캐시 유틸
# ---------------------------------------------------------------------------
def _now_kst() -> datetime:
    return datetime.now(tz=timezone.utc).astimezone()


def _load_cache(path: Path) -> dict[str, Any] | None:
    """캐시 파일을 읽는다. 파일 없으면 None 반환."""
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _is_cache_fresh(cache: dict[str, Any]) -> bool:
    """캐시가 TTL 이내인지 확인한다."""
    fetched_at = cache.get("fetched_at")
    if not fetched_at:
        return False
    try:
        ts = datetime.fromisoformat(fetched_at)
        return _now_kst() - ts < timedelta(hours=_CACHE_TTL_HOURS)
    except ValueError:
        return False


def _save_cache(path: Path, data: dict[str, Any]) -> None:
    """데이터를 JSON 캐시 파일로 저장한다."""
    data["fetched_at"] = _now_kst().isoformat()
    data["source"] = "crawled"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 정책자금 파싱
# ---------------------------------------------------------------------------
_RATE_PATTERN = re.compile(
    r"최저\s*연?\s*([\d.]+)%\s*[~～]\s*최고\s*연?\s*([\d.]+)%"
)
_BASE_RATE_PATTERN = re.compile(r"기준금리\s*[：:]\s*연?\s*([\d.]+)%")
_QUARTER_PATTERN   = re.compile(r"(\d{4}년\s*\d분기)\s*기준")
_LIMIT_PATTERN     = re.compile(r"최대\s*([\d천만억원]+)")
_EVENT_PERIOD_PATTERN = re.compile(
    r"(\d{4})[.\s](\d{1,2})[.\s](\d{1,2})\s*[（\(]?[월]?\s*[）\)]?\s*~\s*"
    r"(\d{4})[.\s](\d{1,2})[.\s](\d{1,2})"
)


def _parse_policy_fund(html: str) -> dict[str, Any]:
    """HTML 에서 정책자금 금리·이벤트 정보를 추출한다."""
    soup = _soup(html)
    text = soup.get_text(separator=" ", strip=True)

    result: dict[str, Any] = {
        "product_name": "소상공인 정책자금대출",
        "url": _URL_POLICY_FUND_PRIMARY,
    }

    # 금리
    m = _RATE_PATTERN.search(text)
    if m:
        result["interest_rate"] = {
            "min": float(m.group(1)),
            "max": float(m.group(2)),
        }
    mb = _BASE_RATE_PATTERN.search(text)
    if mb and "interest_rate" in result:
        result["interest_rate"]["base"] = float(mb.group(1))

    # 분기
    mq = _QUARTER_PATTERN.search(text)
    if mq and "interest_rate" in result:
        result["interest_rate"]["quarter"] = mq.group(1).replace(" ", "")

    # 한도
    ml = _LIMIT_PATTERN.search(text)
    if ml:
        result["loan_limit"] = f"최대 {ml.group(1)}"

    # 이벤트 기간 (첫 번째 매치)
    event_matches = list(_EVENT_PERIOD_PATTERN.finditer(text))
    if event_matches:
        em = event_matches[0]
        result["event"] = {
            "period_start": f"{em.group(1)}-{int(em.group(2)):02d}-{int(em.group(3)):02d}",
            "period_end":   f"{em.group(4)}-{int(em.group(5)):02d}-{int(em.group(6)):02d}",
        }

    # 이벤트 제목 (보증료 지원 키워드)
    if "보증료" in text and "50%" in text:
        result.setdefault("event", {})["title"] = "보증료 50% 지원"
        if "30만원" in text:
            result["event"]["benefit"] = "1인당 최대 30만원"

    # 상환 방법
    for kw in ["2년 거치 3년", "원금균등분할상환", "분할상환"]:
        if kw in text:
            result["repayment"] = "2년 거치 3년 원금균등분할상환"
            break

    return result


# ---------------------------------------------------------------------------
# 상품 목록 파싱
# ---------------------------------------------------------------------------
_SKIP_NAMES = {
    "신청하기", "비교하기", "상담하기", "더보기", "접기",
    "인터넷", "스타기업뱅킹", "영업점", "가입채널",
}


def _parse_loan_products(html: str) -> list[dict[str, Any]]:
    """HTML 에서 소상공인 대출상품 목록을 추출한다."""
    soup = _soup(html)

    # 상품 목록 섹션 탐색 — h3/h4 아래 링크·텍스트 블록
    products: list[dict[str, Any]] = []
    seen: set[str] = set()

    # 상품 카드: <h4> 가입채널 → 다음 형제에서 상품명·설명 추출
    channel_tags = soup.find_all(
        lambda tag: tag.name in ("h4",) and "가입채널" in tag.get_text()
    )

    for ch_tag in channel_tags:
        channel_text = ""
        name_text = ""
        desc_text = ""

        # 가입채널 태그 다음 텍스트 블록들
        siblings = list(ch_tag.next_siblings)
        for sib in siblings:
            t = sib.get_text(strip=True) if hasattr(sib, "get_text") else str(sib).strip()
            if not t or t in _SKIP_NAMES:
                continue
            if not channel_text:
                channel_text = t
            elif not name_text:
                name_text = t
            elif not desc_text:
                desc_text = t
                break

        if name_text and name_text not in seen and name_text not in _SKIP_NAMES:
            seen.add(name_text)
            products.append(
                {
                    "name": name_text,
                    "description": desc_text,
                    "channel": channel_text,
                    "category": "소상공인" if "소상공인" in name_text or "소상공인" in desc_text else "사업자",
                }
            )

    # 파싱 결과가 너무 적으면 텍스트 기반 폴백
    if len(products) < 3:
        products = _parse_loan_products_text_fallback(soup)

    return products


def _parse_loan_products_text_fallback(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """구조 파싱 실패 시 텍스트에서 소상공인 키워드 포함 상품명만 추출한다."""
    text_blocks = [
        tag.get_text(strip=True)
        for tag in soup.find_all(["h3", "h4", "strong", "b", "p", "li", "span"])
        if tag.get_text(strip=True)
    ]
    products: list[dict[str, Any]] = []
    seen: set[str] = set()
    keywords = {"소상공인", "사장님", "햇살론", "119plus", "셀러론", "보증서대출"}

    for block in text_blocks:
        if any(kw in block for kw in keywords) and block not in seen and len(block) < 80:
            seen.add(block)
            products.append(
                {
                    "name": block,
                    "description": "",
                    "channel": "",
                    "category": "소상공인",
                }
            )
    return products


# ---------------------------------------------------------------------------
# 공개 API — 정책자금 정보
# ---------------------------------------------------------------------------
def get_kb_policy_fund_info(force_refresh: bool = False) -> dict[str, Any]:
    """KB국민은행 소상공인 정책자금대출 정보를 반환한다.

    캐시(TTL 24시간)를 우선 사용하고, 만료·강제갱신 시 크롤링한다.
    크롤링 실패 시 기존 캐시(만료 포함)를 반환하여 서비스 연속성을 보장한다.

    Args:
        force_refresh: True 이면 캐시 TTL 무시하고 즉시 크롤링.

    Returns:
        정책자금 정보 dict.
    """
    cache = _load_cache(_CACHE_POLICY_FUND)

    if not force_refresh and cache and _is_cache_fresh(cache):
        return cache

    # 크롤링 시도 (primary → fallback)
    for url in (_URL_POLICY_FUND_PRIMARY, _URL_POLICY_FUND_FALLBACK):
        try:
            html = _fetch_html(url)
            data = _parse_policy_fund(html)
            data["url"] = url
            _save_cache(_CACHE_POLICY_FUND, data)
            logger.info("KB 정책자금 크롤링 완료: %s", url)
            return _load_cache(_CACHE_POLICY_FUND) or data
        except Exception as exc:
            logger.warning("KB 정책자금 크롤링 실패 (%s): %s", url, exc)

    # 크롤링 전부 실패 → 기존 캐시 반환 (만료라도)
    if cache:
        logger.warning("KB 정책자금: 캐시 만료본 반환")
        return cache

    # 캐시도 없으면 seed 데이터 로드 시도
    return _load_cache(_CACHE_POLICY_FUND) or {}


# ---------------------------------------------------------------------------
# 공개 API — 상품 목록
# ---------------------------------------------------------------------------
def get_kb_loan_products(force_refresh: bool = False) -> list[dict[str, Any]]:
    """KB국민은행 비대면 사업자 대출상품 목록을 반환한다.

    캐시(TTL 24시간)를 우선 사용하고, 만료·강제갱신 시 크롤링한다.

    Args:
        force_refresh: True 이면 캐시 TTL 무시하고 즉시 크롤링.

    Returns:
        상품 dict 의 리스트.
    """
    cache = _load_cache(_CACHE_LOAN_PRODUCTS)

    if not force_refresh and cache and _is_cache_fresh(cache):
        return cache.get("products", [])

    try:
        html = _fetch_html(_URL_LOAN_HUB)
        products = _parse_loan_products(html)
        if products:
            _save_cache(_CACHE_LOAN_PRODUCTS, {"products": products})
            logger.info("KB 상품 목록 크롤링 완료: %d건", len(products))
            loaded = _load_cache(_CACHE_LOAN_PRODUCTS)
            return loaded.get("products", products) if loaded else products
    except Exception as exc:
        logger.warning("KB 상품 목록 크롤링 실패: %s", exc)

    # 기존 캐시 반환
    if cache:
        return cache.get("products", [])
    return []


# ---------------------------------------------------------------------------
# 통합 조회 — 에이전트에서 직접 호출하는 진입점
# ---------------------------------------------------------------------------
def get_kb_sme_info() -> dict[str, Any]:
    """소상공인 관련 KB 상품 정보를 모두 묶어 반환한다.

    Returns:
        ``{"policy_fund": {...}, "loan_products": [...], "source": ...}`` 형태의 dict.
    """
    policy_fund   = get_kb_policy_fund_info()
    loan_products = get_kb_loan_products()

    source = policy_fund.get("source", "cache")

    return {
        "policy_fund":   policy_fund,
        "loan_products": loan_products,
        "source":        source,
    }
