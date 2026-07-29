"""기업마당(bizinfo.go.kr) 지원사업정보 API — 정책자금·지원사업 조회 및 파싱."""

from __future__ import annotations

import logging
import re
import time
from typing import Any

import httpx

from project.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do"

_TIMEOUT = 5.0
_MAX_RETRY = 1

# 분야코드 매핑
_CATEGORY_CODE: dict[str, str] = {
    "금융":   "01",
    "기술":   "02",
    "인력":   "03",
    "수출":   "04",
    "내수":   "05",
    "창업":   "06",
    "경영":   "07",
    "기타":   "09",
}

# intent 키워드 → (분야코드, 분야한글명)
_INTENT_MAP: list[tuple[set[str], str, str]] = [
    ({"정책자금", "대출", "금융지원", "금융", "창업자금", "사업자금", "상환연장", "대환"}, "01", "금융"),
    ({"창업"},                                     "06", "창업"),
    ({"경영", "운영", "운전자금", "경영비용"},     "07", "경영"),
]


# ---------------------------------------------------------------------------
# 저수준 HTTP 헬퍼
# ---------------------------------------------------------------------------
def _get(params: dict[str, Any]) -> dict[str, Any]:
    """GET 요청을 수행하고 JSON 을 반환한다. 실패 시 1회 재시도."""
    for attempt in range(_MAX_RETRY + 1):
        try:
            with httpx.Client(timeout=_TIMEOUT) as client:
                resp = client.get(BASE_URL, params=params)
                resp.raise_for_status()
                try:
                    return resp.json()
                except Exception:
                    logger.warning("bizinfo API JSON 파싱 실패: %s", resp.text[:500])
                    raise ValueError("JSON decode error")
        except (httpx.HTTPError, ValueError):
            if attempt < _MAX_RETRY:
                time.sleep(0.5)
            else:
                raise


# ---------------------------------------------------------------------------
# 정규화 함수
# ---------------------------------------------------------------------------
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str | None) -> str:
    """HTML 태그를 제거하고 공백을 정리한다."""
    if not text:
        return ""
    return _HTML_TAG_RE.sub("", text).strip()


def normalize_program(item: dict[str, Any]) -> dict[str, Any]:
    """기업마당 공고 항목 1건을 정규화한다.

    Args:
        item: jsonArray.item 의 원소 dict.

    Returns:
        정규화된 공고 dict.
    """
    raw_hashtags: str = item.get("hashTags", "") or ""
    hashtag_list = [h.strip() for h in raw_hashtags.split(",") if h.strip()]

    return {
        "title":        item.get("pblancNm") or item.get("title", ""),
        "org_name":     item.get("jrsdInsttNm", ""),
        "summary":      _strip_html(item.get("bsnsSumryCn", "")),
        "category":     item.get("pldirSportRealmLclasCodeNm", ""),
        "apply_period": item.get("reqstBeginEndDe", ""),
        "target":       item.get("trgetNm", ""),
        "url":          item.get("pblancUrl", ""),
        "hashtags":     hashtag_list,
    }


# ---------------------------------------------------------------------------
# 원본 호출 함수
# ---------------------------------------------------------------------------
def get_support_programs(
    search_lclas_id: str | None = None,
    hashtags: list[str] | None = None,
    search_cnt: int = 100,
    page_index: int = 1,
) -> dict[str, Any]:
    """기업마당 지원사업 공고 목록을 조회한다.

    Args:
        search_lclas_id: 분야코드 ("01" 금융 / "06" 창업 / "07" 경영 등).
            None 이면 전체 분야 조회.
        hashtags: 해시태그 필터 목록 (예: ["금융", "서울"]).
            콤마로 join 하여 전달.
        search_cnt: 조회 건수 (기본값 100).
        page_index: 페이지 번호 (기본값 1).

    Returns:
        ``{"programs": [...], "source": "bizinfo_api" | "mock"}`` 형태의 dict.
    """
    if not settings.bizinfo_api_key:
        return _mock_support_programs()

    params: dict[str, Any] = {
        "crtfcKey":  settings.bizinfo_api_key,
        "dataType":  "json",
        "pageUnit":  search_cnt,   # API 실제 파라미터명 (searchCnt X)
        "pageIndex": page_index,
    }
    if search_lclas_id:
        params["searchLclasId"] = search_lclas_id
    if hashtags:
        params["hashtags"] = ",".join(hashtags)

    try:
        data = _get(params)
        items = _extract_items(data)
        programs = [normalize_program(item) for item in items]
        return {"programs": programs, "source": "bizinfo_api"}
    except Exception:
        return _mock_support_programs()


def _extract_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    """API 응답에서 공고 항목 리스트를 안전하게 추출한다.

    방어 처리 (실제 API 응답 형식 대응):
    - jsonArray 가 list 이면 그대로 반환 (실제 API 형식).
    - jsonArray 가 dict 이고 item 키를 가지면 item 반환 (레거시 형식).
    - item 이 단일 dict 이면 리스트로 감싸서 반환.
    - 없거나 비어있으면 빈 리스트 반환.

    Args:
        data: API 응답 전체 dict.

    Returns:
        공고 항목 list.
    """
    json_array = data.get("jsonArray")
    if not json_array:
        return []

    # 실제 API 응답: {"jsonArray": [...]} — 리스트 직접 반환
    if isinstance(json_array, list):
        return json_array

    # 레거시 형식: {"jsonArray": {"item": [...]}}
    raw = json_array.get("item")
    if raw is None:
        return []
    if isinstance(raw, dict):
        return [raw]
    return raw  # list[dict]


# ---------------------------------------------------------------------------
# 의도 기반 검색 함수
# ---------------------------------------------------------------------------
def _parse_region_tokens(region: str | None) -> tuple[str | None, str | None]:
    """지역 문자열에서 시·도 약칭과 시·군·구를 추출한다."""
    if not region:
        return None, None
    parts = [part for part in region.strip().split() if part]
    if not parts:
        return None, None
    if len(parts) >= 2:
        return parts[0], parts[-1]
    token = parts[0]
    if token.endswith(("구", "군", "시")):
        return None, token
    return token, None


def _region_match_score(program: dict[str, Any], sido: str | None, signgu: str | None) -> int:
    """지역 일치 점수. 다른 시·도 공고는 -1, 전국 공고는 낮은 양수."""
    title = program.get("title", "") or ""
    text = " ".join(
        [
            title,
            program.get("summary", "") or "",
            " ".join(program.get("hashtags", []) or []),
        ]
    )

    bracket = re.search(r"\[([^\]]+)\]", title)
    bracket_region = bracket.group(1) if bracket else None
    mentioned_signgu = re.findall(r"[가-힣]+(?:구|군|시)", title)

    if signgu and signgu in text:
        return 100
    if signgu and any(gu != signgu for gu in mentioned_signgu):
        return -1
    if bracket_region and sido and bracket_region != sido:
        return -1
    if bracket_region and sido and bracket_region == sido:
        return 60
    if sido and sido in text:
        return 50
    if bracket_region:
        return -1
    return 20


def _filter_programs_by_region(
    programs: list[dict[str, Any]],
    region: str | None,
) -> list[dict[str, Any]]:
    """사용자 지역과 맞는 공고를 우선하고, 다른 지역 공고는 제외한다."""
    sido, signgu = _parse_region_tokens(region)
    if not sido and not signgu:
        return programs

    scored = [(program, _region_match_score(program, sido, signgu)) for program in programs]
    matched = [program for program, score in scored if score >= 0]
    if not matched:
        return programs

    matched.sort(key=lambda program: _region_match_score(program, sido, signgu), reverse=True)
    return matched


def search_support_programs(
    intent: str,
    region: str | None = None,
) -> list[dict[str, Any]]:
    """의도(intent)와 지역(region)에 따라 지원사업 공고를 검색한다.

    intent → 분야코드 매핑:
    - "정책자금"/"대출"/"금융지원" 계열 → "01" (금융)
    - "창업"/"창업자금" 계열            → "06" (창업)
    - "경영"/"운영" 계열                → "07" (경영)
    - 매칭 없음                         → None (전체)

    호출 후 target 또는 summary 에 "소상공인" 이 포함된 항목을 우선 반환.
    필터 결과가 0건이면 원본 리스트 전체를 반환한다.

    Args:
        intent: 사용자 의도 문자열 (예: "정책자금 마련", "창업 준비").
        region: 지역 문자열 (예: "서울", "경기"). None 이면 전국 조회.

    Returns:
        정규화된 공고 dict 의 리스트.
    """
    search_lclas_id: str | None = None
    base_hashtag: str | None = None

    for keywords, code, name in _INTENT_MAP:
        if any(kw in intent for kw in keywords):
            search_lclas_id = code
            base_hashtag = name
            break

    hashtags: list[str] = []
    if base_hashtag:
        hashtags.append(base_hashtag)
    if region:
        sido, signgu = _parse_region_tokens(region)
        if sido:
            hashtags.append(sido)
        if signgu:
            hashtags.append(signgu)

    result = get_support_programs(
        search_lclas_id=search_lclas_id,
        hashtags=hashtags or None,
    )
    programs: list[dict[str, Any]] = result.get("programs", [])

    # 소상공인 후처리 필터
    filtered = [
        p for p in programs
        if "소상공인" in p.get("target", "") or "소상공인" in p.get("summary", "")
    ]
    filtered = filtered if filtered else programs
    return _filter_programs_by_region(filtered, region)


# ---------------------------------------------------------------------------
# Mock 데이터
# ---------------------------------------------------------------------------
def _mock_support_programs() -> dict[str, Any]:
    return {
        "programs": [
            {
                "title":        "소상공인 정책자금 융자 지원 공고",
                "org_name":     "중소벤처기업부",
                "summary":      "소상공인의 경영 안정 및 성장을 위해 시설·운전자금을 저금리로 융자 지원합니다.",
                "category":     "금융",
                "apply_period": "20240101 ~ 20241231",
                "target":       "소상공인",
                "url":          "https://www.bizinfo.go.kr/web/lay1/program/S1T122C128/PBLN_0000000073928/view.do",
                "hashtags":     ["소상공인", "정책자금", "융자"],
            },
            {
                "title":        "착한임대인 장관 표창 신청 연장 공고",
                "org_name":     "중소벤처기업부",
                "summary":      "임대료를 자발적으로 인하한 착한임대인을 발굴·포상하여 상생문화를 확산합니다.",
                "category":     "경영",
                "apply_period": "20240301 ~ 20240531",
                "target":       "소상공인, 임대인",
                "url":          "https://www.bizinfo.go.kr/web/lay1/program/S1T122C128/PBLN_0000000072100/view.do",
                "hashtags":     ["소상공인", "착한임대인", "표창"],
            },
            {
                "title":        "소상공인 스마트화 지원사업 참여기업 모집",
                "org_name":     "소상공인시장진흥공단",
                "summary":      "소상공인의 디지털 전환을 위해 스마트 기기·솔루션 도입 비용을 최대 400만 원 지원합니다.",
                "category":     "기술",
                "apply_period": "20240401 ~ 20240630",
                "target":       "소상공인",
                "url":          "https://www.bizinfo.go.kr/web/lay1/program/S1T122C128/PBLN_0000000074500/view.do",
                "hashtags":     ["소상공인", "스마트화", "디지털전환"],
            },
        ],
        "source": "mock",
    }
