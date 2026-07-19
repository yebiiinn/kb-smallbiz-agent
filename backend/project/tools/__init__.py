"""외부 API 연동 — API별 파일 1개.

- sangkwon_api.py   소진공 상권 정보
- seoul_sales_api.py 서울시 추정매출
- kakao_map_api.py  카카오맵
- ecos_api.py       한국은행 ECOS
- kosis_api.py      통계청 KOSIS
- bizinfo_api.py    기업마당
- finlife_api.py    금감원 finlife
- kb_crawler.py     KB국민은행 소상공인 상품 크롤러 (캐시: data/cache/)
- semas_crawler.py  소상공인진흥공단 정책 정보 크롤러 (캐시: data/cache/)

각 파일 상단 API_URL(또는 API_URL_TEMPLATE)에 명세의 요청 URL 붙여넣기.
KEY는 backend/project/.env
"""
