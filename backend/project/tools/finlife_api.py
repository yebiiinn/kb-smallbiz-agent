"""금융감독원 finlife 오픈API — 금융상품 조회 및 파싱."""

from __future__ import annotations

import time
from typing import Any

import httpx

from project.config import settings

# ---------------------------------------------------------------------------
# 엔드포인트 URL
# ---------------------------------------------------------------------------
_BASE = "http://finlife.fss.or.kr"

_URLS: dict[str, str] = {
    "business_loans": f"{_BASE}/finlifeapi/busiLoanProductsSearch.json",
    "credit_loans":   f"{_BASE}/finlifeapi/creditLoanProductsSearch.json",
    "savings":        f"{_BASE}/finlifeapi/savingProductsSearch.json",
    "deposits":       f"{_BASE}/finlife/fdrmDpstApi/list.json",
    "mortgage_loans": f"{_BASE}/finlifeapi/mortgageLoanProductsSearch.json",
}

_TIMEOUT = 5.0
_MAX_RETRY = 1


# ---------------------------------------------------------------------------
# 저수준 HTTP 헬퍼
# ---------------------------------------------------------------------------
def _get(url: str, params: dict[str, Any]) -> dict[str, Any]:
    """GET 요청을 수행하고 JSON 을 반환한다. 실패 시 1회 재시도."""
    for attempt in range(_MAX_RETRY + 1):
        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                return resp.json()
        except (httpx.HTTPError, ValueError):
            if attempt < _MAX_RETRY:
                time.sleep(0.5)
            else:
                raise


def _fetch(
    endpoint_key: str,
    top_fin_grp_no: str,
    page_no: int = 1,
) -> dict[str, Any]:
    """finlife API 를 호출하고 raw JSON 을 반환한다."""
    params = {
        "auth": settings.finlife_api_key,
        "topFinGrpNo": top_fin_grp_no,
        "pageNo": page_no,
    }
    return _get(_URLS[endpoint_key], params)


# ---------------------------------------------------------------------------
# 정규화 함수
# ---------------------------------------------------------------------------
def normalize_business_loan(
    base: dict[str, Any],
    options: list[dict[str, Any]],
) -> dict[str, Any]:
    """기업 대출 상품 1건을 정규화한다.

    Args:
        base: baseList 항목 1개.
        options: 해당 상품의 optionList 항목 목록.

    Returns:
        정규화된 상품 dict.
    """
    lend_rate_min = min(
        (o.get("lend_rate_min") for o in options if o.get("lend_rate_min") is not None),
        default=None,
    )
    lend_rate_max = max(
        (o.get("lend_rate_max") for o in options if o.get("lend_rate_max") is not None),
        default=None,
    )
    return {
        "fin_co_name":    base.get("kor_co_nm", ""),
        "product_name":   base.get("fin_prdt_nm", ""),
        "loan_type":      base.get("loan_type", ""),
        "join_way":       base.get("join_way", ""),
        "lend_rate_min":  lend_rate_min,
        "lend_rate_max":  lend_rate_max,
        "join_deny_detl": base.get("join_deny", ""),
    }


def normalize_credit_loan(
    base: dict[str, Any],
    options: list[dict[str, Any]],
) -> dict[str, Any]:
    """개인 신용 대출 상품 1건을 정규화한다.

    Args:
        base: baseList 항목 1개.
        options: 해당 상품의 optionList 항목 목록.
            crdt_lend_rate_type == "A" (대출금리) 인 행만 평균 금리로 사용.

    Returns:
        정규화된 상품 dict.
    """
    # 대출금리 타입 "A" 행만 추출
    rate_rows = [o for o in options if o.get("crdt_lend_rate_type") == "A"]
    avg_rate = rate_rows[0].get("crdt_grad_avg") if rate_rows else None

    return {
        "fin_co_name":       base.get("kor_co_nm", ""),
        "product_name":      base.get("fin_prdt_nm", ""),
        "crdt_prdt_type_nm": base.get("crdt_prdt_type_nm", ""),
        "join_way":          base.get("join_way", ""),
        "avg_rate":          avg_rate,
    }


def normalize_deposit_saving(
    base: dict[str, Any],
    options: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """예·적금 상품 1건을 정규화한다.

    기간(save_trm) 옵션이 여러 개이면 각각 별도 항목으로 펼쳐 반환한다.

    Args:
        base: baseList 항목 1개.
        options: 해당 상품의 optionList 항목 목록.

    Returns:
        정규화된 상품 dict 의 리스트.
    """
    result: list[dict[str, Any]] = []
    for opt in options:
        result.append(
            {
                "fin_co_name":   base.get("kor_co_nm", ""),
                "product_name":  base.get("fin_prdt_nm", ""),
                "save_trm":      opt.get("save_trm"),
                "intr_rate":     opt.get("intr_rate"),
                "intr_rate2":    opt.get("intr_rate2"),
                "rsrv_type_nm":  opt.get("rsrv_type_nm"),  # 적금만 존재, 예금은 None
            }
        )
    # 옵션 없는 경우 기본 항목 1개
    if not result:
        result.append(
            {
                "fin_co_name":  base.get("kor_co_nm", ""),
                "product_name": base.get("fin_prdt_nm", ""),
                "save_trm":     None,
                "intr_rate":    None,
                "intr_rate2":   None,
                "rsrv_type_nm": None,
            }
        )
    return result


def normalize_mortgage(
    base: dict[str, Any],
    options: list[dict[str, Any]],
) -> dict[str, Any]:
    """주택담보대출 상품 1건을 정규화한다.

    Args:
        base: baseList 항목 1개.
        options: 해당 상품의 optionList 항목 목록.

    Returns:
        정규화된 상품 dict.
    """
    lend_rate_min = min(
        (o.get("lend_rate_min") for o in options if o.get("lend_rate_min") is not None),
        default=None,
    )
    lend_rate_max = max(
        (o.get("lend_rate_max") for o in options if o.get("lend_rate_max") is not None),
        default=None,
    )
    lend_rate_avg = options[0].get("lend_rate_avg") if options else None

    return {
        "fin_co_name":    base.get("kor_co_nm", ""),
        "product_name":   base.get("fin_prdt_nm", ""),
        "mrtg_type_nm":   options[0].get("mrtg_type_nm", "") if options else "",
        "rpay_type_nm":   options[0].get("rpay_type_nm", "") if options else "",
        "lend_rate_min":  lend_rate_min,
        "lend_rate_max":  lend_rate_max,
        "lend_rate_avg":  lend_rate_avg,
        "loan_lmt":       base.get("loan_lmt", ""),
    }


# ---------------------------------------------------------------------------
# 내부 join 헬퍼
# ---------------------------------------------------------------------------
def _join_base_options(
    result: dict[str, Any],
    join_keys: tuple[str, ...] = ("fin_co_no", "fin_prdt_cd"),
) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
    """baseList 와 optionList 를 join_keys 기준으로 조인한다."""
    base_list: list[dict[str, Any]] = result.get("result", {}).get("baseList", [])
    option_list: list[dict[str, Any]] = result.get("result", {}).get("optionList", [])

    # optionList 를 복합키 기준으로 그룹화
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for opt in option_list:
        key = tuple(opt.get(k, "") for k in join_keys)
        grouped.setdefault(key, []).append(opt)

    pairs: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    for base in base_list:
        key = tuple(base.get(k, "") for k in join_keys)
        pairs.append((base, grouped.get(key, [])))

    return pairs


# ---------------------------------------------------------------------------
# 공개 API 함수
# ---------------------------------------------------------------------------
def get_business_loans(
    top_fin_grp_no: str,
    page_no: int = 1,
) -> dict[str, Any]:
    """기업 대출 상품 목록을 조회하고 정규화하여 반환한다.

    Args:
        top_fin_grp_no: 금융회사 그룹 코드 (예: "020000" 은행).
        page_no: 페이지 번호 (기본값 1).

    Returns:
        ``{"products": [...], "source": "finlife_api"}`` 형태의 dict.
    """
    if not settings.finlife_api_key:
        return _mock_business_loans()

    try:
        raw = _fetch("business_loans", top_fin_grp_no, page_no)
        pairs = _join_base_options(raw)
        products = [normalize_business_loan(b, o) for b, o in pairs]
        return {"products": products, "source": "finlife_api"}
    except Exception:
        return _mock_business_loans()


def get_credit_loans(
    top_fin_grp_no: str,
    page_no: int = 1,
) -> dict[str, Any]:
    """개인 신용 대출 상품 목록을 조회하고 정규화하여 반환한다.

    Args:
        top_fin_grp_no: 금융회사 그룹 코드.
        page_no: 페이지 번호 (기본값 1).

    Returns:
        ``{"products": [...], "source": "finlife_api"}`` 형태의 dict.
    """
    if not settings.finlife_api_key:
        return _mock_credit_loans()

    try:
        raw = _fetch("credit_loans", top_fin_grp_no, page_no)
        # 신용대출은 join key 에 crdt_prdt_type 추가
        pairs = _join_base_options(raw, join_keys=("fin_co_no", "fin_prdt_cd", "crdt_prdt_type"))
        products = [normalize_credit_loan(b, o) for b, o in pairs]
        return {"products": products, "source": "finlife_api"}
    except Exception:
        return _mock_credit_loans()


def get_savings(
    top_fin_grp_no: str,
    page_no: int = 1,
) -> dict[str, Any]:
    """적금 상품 목록을 조회하고 정규화하여 반환한다.

    Args:
        top_fin_grp_no: 금융회사 그룹 코드.
        page_no: 페이지 번호 (기본값 1).

    Returns:
        ``{"products": [...], "source": "finlife_api"}`` 형태의 dict.
    """
    if not settings.finlife_api_key:
        return _mock_savings()

    try:
        raw = _fetch("savings", top_fin_grp_no, page_no)
        pairs = _join_base_options(raw)
        products: list[dict[str, Any]] = []
        for base, opts in pairs:
            products.extend(normalize_deposit_saving(base, opts))
        return {"products": products, "source": "finlife_api"}
    except Exception:
        return _mock_savings()


def get_deposits(
    top_fin_grp_no: str,
    page_no: int = 1,
) -> dict[str, Any]:
    """정기예금 상품 목록을 조회하고 정규화하여 반환한다.

    Args:
        top_fin_grp_no: 금융회사 그룹 코드.
        page_no: 페이지 번호 (기본값 1).

    Returns:
        ``{"products": [...], "source": "finlife_api"}`` 형태의 dict.
    """
    if not settings.finlife_api_key:
        return _mock_deposits()

    try:
        raw = _fetch("deposits", top_fin_grp_no, page_no)
        pairs = _join_base_options(raw)
        products: list[dict[str, Any]] = []
        for base, opts in pairs:
            products.extend(normalize_deposit_saving(base, opts))
        return {"products": products, "source": "finlife_api"}
    except Exception:
        return _mock_deposits()


def get_mortgage_loans(
    top_fin_grp_no: str,
    page_no: int = 1,
) -> dict[str, Any]:
    """주택담보대출 상품 목록을 조회하고 정규화하여 반환한다.

    Args:
        top_fin_grp_no: 금융회사 그룹 코드.
        page_no: 페이지 번호 (기본값 1).

    Returns:
        ``{"products": [...], "source": "finlife_api"}`` 형태의 dict.
    """
    if not settings.finlife_api_key:
        return _mock_mortgage_loans()

    try:
        raw = _fetch("mortgage_loans", top_fin_grp_no, page_no)
        pairs = _join_base_options(raw)
        products = [normalize_mortgage(b, o) for b, o in pairs]
        return {"products": products, "source": "finlife_api"}
    except Exception:
        return _mock_mortgage_loans()


# ---------------------------------------------------------------------------
# 통합 검색 함수
# ---------------------------------------------------------------------------
_BUSINESS_KEYWORDS = {"창업자금", "사업자금", "대출", "창업", "사업"}
_SAVINGS_KEYWORDS  = {"여유자금", "예치", "저축", "예금", "적금"}
_MORTGAGE_KEYWORDS = {"주택", "부동산", "아파트", "주담대", "모기지"}


def search_finance_products(
    intent: str,
    top_fin_grp_no: str = "020000",
) -> dict[str, Any]:
    """의도(intent) 에 따라 적절한 finlife 상품을 조회하고 통합 반환한다.

    - 창업자금/사업자금/대출 계열 → 기업 대출 + 개인 신용 대출
    - 여유자금/예치/저축 계열     → 정기예금 + 적금
    - 주택/부동산 계열            → 주택담보대출
    - 기본값(소상공인 시나리오)   → 기업 대출 + 개인 신용 대출

    Args:
        intent: 사용자 의도 키워드 (예: "창업자금 마련", "주택 구입").
        top_fin_grp_no: 금융회사 그룹 코드 (기본값 "020000" 은행).

    Returns:
        ``{"products": [...], "source": ..., "categories": [...]}`` 형태의 dict.
    """
    intent_lower = intent.lower()

    if any(kw in intent_lower for kw in _MORTGAGE_KEYWORDS):
        mortgage = get_mortgage_loans(top_fin_grp_no)
        return {
            "products": mortgage["products"],
            "source": mortgage["source"],
            "categories": ["mortgage_loans"],
        }

    if any(kw in intent_lower for kw in _SAVINGS_KEYWORDS):
        deposits = get_deposits(top_fin_grp_no)
        savings  = get_savings(top_fin_grp_no)
        return {
            "products": deposits["products"] + savings["products"],
            "source": deposits["source"],
            "categories": ["deposits", "savings"],
        }

    # 창업자금/사업자금/대출 계열 또는 기본값
    biz    = get_business_loans(top_fin_grp_no)
    credit = get_credit_loans(top_fin_grp_no)
    return {
        "products": biz["products"] + credit["products"],
        "source": biz["source"],
        "categories": ["business_loans", "credit_loans"],
    }


# ---------------------------------------------------------------------------
# Mock 데이터
# ---------------------------------------------------------------------------
def _mock_business_loans() -> dict[str, Any]:
    return {
        "products": [
            {
                "fin_co_name":    "우리은행",
                "product_name":   "우리CUBE론-X",
                "loan_type":      "시설·운전 복합",
                "join_way":       "인터넷, 스마트폰",
                "lend_rate_min":  3.97,
                "lend_rate_max":  7.50,
                "join_deny_detl": "사업자등록증 보유자",
            },
            {
                "fin_co_name":    "국민은행",
                "product_name":   "KB소상공인대출",
                "loan_type":      "운전자금",
                "join_way":       "영업점",
                "lend_rate_min":  4.20,
                "lend_rate_max":  8.10,
                "join_deny_detl": "개인사업자 및 법인",
            },
            {
                "fin_co_name":    "신한은행",
                "product_name":   "신한 사업자 햇살론",
                "loan_type":      "보증부 대출",
                "join_way":       "영업점, 인터넷",
                "lend_rate_min":  3.50,
                "lend_rate_max":  6.80,
                "join_deny_detl": "연 매출 3억 이하 소상공인",
            },
        ],
        "source": "mock",
    }


def _mock_credit_loans() -> dict[str, Any]:
    return {
        "products": [
            {
                "fin_co_name":       "우리은행",
                "product_name":      "우리 주거래 우대론",
                "crdt_prdt_type_nm": "일반신용대출",
                "join_way":          "인터넷, 스마트폰",
                "avg_rate":          5.30,
            },
            {
                "fin_co_name":       "하나은행",
                "product_name":      "하나 원큐 신용대출",
                "crdt_prdt_type_nm": "마이너스통장",
                "join_way":          "스마트폰",
                "avg_rate":          5.80,
            },
            {
                "fin_co_name":       "기업은행",
                "product_name":      "IBK 중소기업론",
                "crdt_prdt_type_nm": "일반신용대출",
                "join_way":          "영업점",
                "avg_rate":          4.95,
            },
        ],
        "source": "mock",
    }


def _mock_deposits() -> dict[str, Any]:
    return {
        "products": [
            {
                "fin_co_name":  "우리은행",
                "product_name": "우리 WON플러스 예금",
                "save_trm":     12,
                "intr_rate":    3.60,
                "intr_rate2":   3.80,
                "rsrv_type_nm": None,
            },
            {
                "fin_co_name":  "국민은행",
                "product_name": "KB Star 정기예금",
                "save_trm":     24,
                "intr_rate":    3.40,
                "intr_rate2":   3.70,
                "rsrv_type_nm": None,
            },
        ],
        "source": "mock",
    }


def _mock_savings() -> dict[str, Any]:
    return {
        "products": [
            {
                "fin_co_name":  "신한은행",
                "product_name": "신한 My적금",
                "save_trm":     12,
                "intr_rate":    4.00,
                "intr_rate2":   4.50,
                "rsrv_type_nm": "정액적립식",
            },
            {
                "fin_co_name":  "하나은행",
                "product_name": "하나 더 적금",
                "save_trm":     24,
                "intr_rate":    3.80,
                "intr_rate2":   4.30,
                "rsrv_type_nm": "자유적립식",
            },
        ],
        "source": "mock",
    }


def _mock_mortgage_loans() -> dict[str, Any]:
    return {
        "products": [
            {
                "fin_co_name":   "우리은행",
                "product_name":  "우리 아파트론",
                "mrtg_type_nm":  "아파트",
                "rpay_type_nm":  "원리금균등분할상환",
                "lend_rate_min": 3.60,
                "lend_rate_max": 5.50,
                "lend_rate_avg": 4.20,
                "loan_lmt":      "LTV 70%",
            },
            {
                "fin_co_name":   "국민은행",
                "product_name":  "KB 주택담보대출",
                "mrtg_type_nm":  "아파트외",
                "rpay_type_nm":  "원금균등분할상환",
                "lend_rate_min": 3.80,
                "lend_rate_max": 5.80,
                "lend_rate_avg": 4.50,
                "loan_lmt":      "LTV 60%",
            },
            {
                "fin_co_name":   "신한은행",
                "product_name":  "신한 주담대 플러스",
                "mrtg_type_nm":  "아파트",
                "rpay_type_nm":  "일시상환",
                "lend_rate_min": 3.70,
                "lend_rate_max": 5.60,
                "lend_rate_avg": 4.30,
                "loan_lmt":      "LTV 70%",
            },
        ],
        "source": "mock",
    }
