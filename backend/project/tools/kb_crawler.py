"""KB국민은행 소상공인 대출상품 크롤러.

크롤링 대상 (httpx GET 가능 확인된 URL):
- C112618 / C112610 : 소상공인 정책자금대출 — 금리·이벤트 (분기별 갱신)
- C016282           : 비대면 사업자 대출상품 허브 — 상품 목록
- C016282?prcode=.. : 개별 소상공인 대출상품 세부 페이지 (금리·한도)

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
_CACHE_POLICY_FUND   = _CACHE_DIR / "kb_policy_fund.json"
_CACHE_LOAN_PRODUCTS = _CACHE_DIR / "kb_loan_products.json"
_CACHE_SME_PRODUCTS  = _CACHE_DIR / "kb_sme_products.json"

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
_URL_SME_PRODUCT_BASE = (
    "https://obiz.kbstar.com/quics?page=C016282&cc=b035264:b035393&isNew=N"
)

# 개별 소상공인 상품 prcode 목록
_SME_PRODUCT_PCODES: list[str] = [
    "LN25001536",  # KB사장님+ 마이너스통장
    "LN25001383",  # KB소상공인 보증서대출(온택트)
    "LN25001287",  # KB소상공인 신용대출
    "LN25001614",  # KB 소상공인 119plus 장기분할상환 대출
    "LN25001621",  # KB 소상공인 119plus 만기연장 대출
    "LN25001564",  # KB소상공인보증서대출(모바일우대보증)
    "LN25001435",  # 소상공인 저금리 대환대출(수탁보증)
    "LN25000001",  # KB 프랜차이즈 대출
]

# 크롤링 실패 시 fallback seed 데이터 (2026-07-27 기준 직접 확인)
_SME_PRODUCTS_SEED: list[dict[str, Any]] = [
    {
        "product_name": "KB사장님+ 마이너스통장",
        "target": "개인사업자",
        "loan_limit": "최대 1억원",
        "min_rate": 3.62,
        "prcode": "LN25001536",
        "url": f"{_URL_SME_PRODUCT_BASE}&prcode=LN25001536",
        "description": "필요한만큼 사용하고 언제든 상환",
        "category": "일반대출",
    },
    {
        "product_name": "KB소상공인 보증서대출(온택트)",
        "target": "개인사업자",
        "loan_limit": "최대 3천만원",
        "min_rate": 5.63,
        "prcode": "LN25001383",
        "url": f"{_URL_SME_PRODUCT_BASE}&prcode=LN25001383",
        "description": "사업장에서 모바일로 간편하게 신청하는 보증서 기반 대출",
        "category": "보증서대출",
    },
    {
        "product_name": "KB소상공인 신용대출",
        "target": "개인사업자",
        "loan_limit": "최대 2억원",
        "min_rate": 3.63,
        "prcode": "LN25001287",
        "url": f"{_URL_SME_PRODUCT_BASE}&prcode=LN25001287",
        "description": "바쁜 개인사업자를 위한 비대면 신용대출",
        "category": "신용대출",
    },
    {
        "product_name": "KB 소상공인 119plus 장기분할상환 대출",
        "target": "개인사업자&법인",
        "loan_limit": None,
        "min_rate": None,
        "prcode": "LN25001614",
        "url": f"{_URL_SME_PRODUCT_BASE}&prcode=LN25001614",
        "description": "일시적 자금사정 악화 소상공인 채무조정 지원",
        "category": "채무조정",
    },
    {
        "product_name": "KB 소상공인 119plus 만기연장 대출",
        "target": "개인사업자&법인",
        "loan_limit": None,
        "min_rate": None,
        "prcode": "LN25001621",
        "url": f"{_URL_SME_PRODUCT_BASE}&prcode=LN25001621",
        "description": "일시적 자금사정 악화 소상공인 만기연장 채무조정 지원",
        "category": "채무조정",
    },
    {
        "product_name": "KB소상공인보증서대출(모바일우대보증)",
        "target": "개인사업자",
        "loan_limit": "최대 5천만원",
        "min_rate": 5.43,
        "prcode": "LN25001564",
        "url": f"{_URL_SME_PRODUCT_BASE}&prcode=LN25001564",
        "description": "경기도 소재 소상공인을 위한 비대면 전용 보증서대출",
        "category": "보증서대출",
        "region": "경기도",
    },
    {
        "product_name": "소상공인 저금리 대환대출(수탁보증)",
        "target": "개인사업자&법인",
        "loan_limit": "개인 최대 1억원, 법인 최대 2억원",
        "min_rate": None,
        "prcode": "LN25001435",
        "url": f"{_URL_SME_PRODUCT_BASE}&prcode=LN25001435",
        "description": "고금리(연 7% 이상) 기업대출을 저금리 보증서대출로 대환",
        "category": "대환대출",
    },
    {
        "product_name": "KB 프랜차이즈 대출",
        "target": "개인사업자",
        "loan_limit": "동일인 최대 10억원",
        "min_rate": None,
        "prcode": "LN25000001",
        "url": f"{_URL_SME_PRODUCT_BASE}&prcode=LN25000001",
        "description": "프랜차이즈 가맹점주를 위한 사업자 대출",
        "category": "일반대출",
    },
]


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
_LIMIT_PATTERN     = re.compile(r"최대\s*([\d]+(?:천만|억)\s*원?)")
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
# 개별 소상공인 상품 페이지 파싱
# ---------------------------------------------------------------------------
def _parse_sme_product_page(
    html: str, prcode: str, url: str
) -> dict[str, Any] | None:
    """개별 상품 페이지 HTML 에서 상품명·가입대상·한도·최저금리를 추출한다."""
    soup = _soup(html)

    # 상품명: 페이지 본문 h3 내 마지막 <strong> (네비게이션 h3 제외)
    product_name: str | None = None
    for h3 in soup.find_all("h3"):
        strongs = h3.find_all("strong")
        if not strongs:
            continue
        candidate = strongs[-1].get_text(strip=True)
        if len(candidate) > 3 and not any(
            kw in candidate
            for kw in ["전체메뉴", "서비스 메뉴", "HOME", "목록", "가이드"]
        ):
            product_name = candidate
            break

    if not product_name:
        return None

    text = soup.get_text(" ", strip=True)
    result: dict[str, Any] = {
        "product_name": product_name,
        "prcode": prcode,
        "url": url,
    }

    # 가입대상
    m = re.search(r"가입대상\s+(개인사업자(?:\s*&\s*법인)?|법인)", text)
    if m:
        result["target"] = m.group(1).strip()

    # 한도 (다양한 형태 대응)
    m = re.search(
        r"한도\s+((?:개인\s*)?최대\s*[\d천만억원,\s]+(?:,?\s*법인\s*최대\s*[\d천만억\s원]+)?|동일인\s*최대\s*[\d억원이내]+)",
        text,
    )
    if m:
        result["loan_limit"] = m.group(1).strip()

    # 최저금리
    m = re.search(r"최저금리\s+연\s+([\d.]+)%", text)
    if m:
        result["min_rate"] = float(m.group(1))

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
# 공개 API — 소상공인 개별 상품 목록
# ---------------------------------------------------------------------------
def get_kb_sme_products(force_refresh: bool = False) -> list[dict[str, Any]]:
    """KB 소상공인 개별 대출상품 8종의 상세 정보를 반환한다.

    캐시(TTL 24시간)를 우선 사용하고, 만료·강제갱신 시 각 prcode 페이지를 크롤링한다.
    크롤링 실패 시 seed 데이터를 반환하여 서비스 연속성을 보장한다.

    Args:
        force_refresh: True 이면 캐시 TTL 무시하고 즉시 크롤링.

    Returns:
        상품 dict 의 리스트.
    """
    cache = _load_cache(_CACHE_SME_PRODUCTS)

    if not force_refresh and cache and _is_cache_fresh(cache):
        return cache.get("products", _SME_PRODUCTS_SEED)

    # 개별 상품 페이지 크롤링
    crawled: list[dict[str, Any]] = []
    for prcode in _SME_PRODUCT_PCODES:
        url = f"{_URL_SME_PRODUCT_BASE}&prcode={prcode}"
        try:
            html = _fetch_html(url)
            parsed = _parse_sme_product_page(html, prcode, url)
            if parsed:
                # seed 데이터에서 category·description·region 보완
                seed = next(
                    (s for s in _SME_PRODUCTS_SEED if s["prcode"] == prcode), {}
                )
                merged = {**seed, **{k: v for k, v in parsed.items() if v is not None}}
                crawled.append(merged)
                logger.debug("KB SME 상품 크롤링 완료: %s → %s", prcode, parsed.get("product_name"))
            else:
                # 파싱 실패 시 seed 데이터 사용
                seed = next(
                    (s for s in _SME_PRODUCTS_SEED if s["prcode"] == prcode), None
                )
                if seed:
                    crawled.append(seed)
        except Exception as exc:
            logger.warning("KB SME 상품 크롤링 실패 (%s): %s", prcode, exc)
            seed = next(
                (s for s in _SME_PRODUCTS_SEED if s["prcode"] == prcode), None
            )
            if seed:
                crawled.append(seed)

    if crawled:
        _save_cache(_CACHE_SME_PRODUCTS, {"products": crawled})
        logger.info("KB SME 상품 목록 갱신 완료: %d건", len(crawled))
        loaded = _load_cache(_CACHE_SME_PRODUCTS)
        return loaded.get("products", crawled) if loaded else crawled

    # 크롤링 전부 실패 → 기존 캐시 또는 seed
    if cache:
        logger.warning("KB SME 상품: 캐시 만료본 반환")
        return cache.get("products", _SME_PRODUCTS_SEED)

    logger.warning("KB SME 상품: seed 데이터 반환")
    return _SME_PRODUCTS_SEED


# ---------------------------------------------------------------------------
# 통합 조회 — 에이전트에서 직접 호출하는 진입점
# ---------------------------------------------------------------------------
def get_kb_sme_info() -> dict[str, Any]:
    """소상공인 관련 KB 상품 정보를 모두 묶어 반환한다.

    Returns:
        ``{"policy_fund": {...}, "loan_products": [...], "sme_products": [...], "source": ...}``
        형태의 dict.
    """
    policy_fund   = get_kb_policy_fund_info()
    loan_products = get_kb_loan_products()
    sme_products  = get_kb_sme_products()

    source = policy_fund.get("source", "cache")

    return {
        "policy_fund":   policy_fund,
        "loan_products": loan_products,
        "sme_products":  sme_products,
        "source":        source,
    }
