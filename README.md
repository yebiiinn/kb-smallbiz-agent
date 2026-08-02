# 소상공인 금융 지원 에이전트

> 2026 KB Future Finance AI Challenge — AI 기술을 활용한 소상공인 금융 지원 서비스

지역 상권, 경기지표, 소비 트렌드, 정책자금 정보를 종합 분석하여 소상공인의 경영 의사결정을 지원하는 멀티 에이전트 시스템입니다.

---

## 주요 기능

| 에이전트 | 설명 |
|--------|------|
| 🏪 **지역 상권 분석** | 소진공 상권 정보 · 서울시 추정매출 · 카카오맵 경쟁 분석 |
| 📈 **경기지표·소비트렌드** | 한국은행 ECOS · 국가데이터처 KOSIS 기반 업종별 경기 해석 |
| 💰 **정책자금·금융상품** | 기업마당 지원사업 · KB·소진공 정책자금 · 금감원 금융상품 비교 추천 |
| ⚠️ **위기진단** | 상권 활성도 · 주요상권 · 경기지표 기반 위험 신호 감지 |

---

## 프로젝트 구조

```
kb-smallbiz-agent/
├── frontend/                        # Next.js (App Router + TypeScript + Tailwind)
│
├── backend/
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── analysis/                    # 사전 데이터 분석 (에이전트 로직과 분리)
│   │   ├── economic/                # 경기지표·소비트렌드 분석
│   │   │   ├── collect.py           # ECOS/KOSIS 18개 지표 수집·상관관계 분석
│   │   │   ├── visualize.py         # 시각화 차트 생성
│   │   │   ├── data/                # 수집 데이터 (.gitignore 적용)
│   │   │   └── charts/              # 분석 차트 (.gitignore 적용)
│   │   ├── commercial/              # 지역상권 분석 스크립트
│   │   ├── finance/                 # 정책자금 분석 스크립트
│   │   └── crisis/                  # 위기진단 데이터 수집 스크립트
│   │
│   └── project/                     # FastAPI + LangGraph 핵심 서비스
│       ├── main.py                  # FastAPI 진입점
│       ├── graph.py                 # LangGraph 오케스트레이터
│       ├── state.py                 # 공유 State
│       ├── schemas.py               # API 요청/응답 스키마
│       ├── config.py                # 환경변수 로딩
│       ├── .env.example             # 환경변수 템플릿
│       ├── agents/
│       │   ├── router.py            # 질의 유형별 에이전트 라우팅
│       │   ├── commercial.py        # 지역 상권 에이전트
│       │   ├── economic.py          # 경기·소비트렌드 에이전트
│       │   ├── finance.py           # 정책자금·금융상품 에이전트
│       │   └── crisis.py            # 위기진단 에이전트
│       ├── tools/
│       │   ├── ecos_api.py          # 한국은행 ECOS API
│       │   ├── kosis_api.py         # 국가데이터처 KOSIS API
│       │   ├── sangkwon_api.py      # 소진공 상권 정보
│       │   ├── seoul_sales_api.py   # 서울시 추정매출
│       │   ├── kakao_map_api.py     # 카카오맵
│       │   ├── bizinfo_api.py       # 기업마당 지원사업
│       │   ├── finlife_api.py       # 금감원 금융상품 비교
│       │   ├── kb_crawler.py        # KB 정책자금·대출상품 수집
│       │   ├── semas_crawler.py     # 소진공 정책자금 수집
│       │   └── crisis_data.py       # 위기진단 데이터 로더
│       └── data/
│           ├── economic/
│           │   └── indicator_mapping.json  # 업종-지표 상관관계 매핑표
│           ├── crisis/              # 위기진단용 상권·시장 데이터
│           ├── cache/               # 외부 수집 캐시 (Mock 폴백)
│           └── mock/                # API 키 없을 때 사용하는 Mock 데이터
│
├── docker-compose.yml
└── .gitignore
```

---

## 실행 방법

### 1. Backend (FastAPI)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp project/.env.example project/.env
# .env 에 API 키 입력 후 실행 (없어도 Mock 모드로 동작)
uvicorn project.main:app --reload
```

→ http://localhost:8000/docs

### 2. Frontend (Next.js)

```bash
cd frontend
cp .env.local.example .env.local   # 필요 시
npm install
npm run dev
```

→ http://localhost:3000

### 3. Docker (선택)

```bash
# 먼저 backend/project/.env 를 .env.example 에서 생성
docker compose up
```

### 4. 경기지표 분석 재현 (선택)

```bash
cd backend/analysis/economic
python collect.py --step 3    # 데이터 수집 및 병합
python collect.py --step 4    # 상관관계 분석
python visualize.py           # 차트 생성
```

---

## 환경 변수

`backend/project/.env.example`을 복사해 `backend/project/.env`를 만든 뒤 키를 입력합니다.  
**실제 `.env` 파일은 제출/커밋하지 않습니다.**

| 변수 | 설명 | 비고 |
|------|------|------|
| `OPENAI_API_KEY` | OpenAI LLM | 없으면 템플릿/Mock 답변 |
| `LLM_MODEL` | 사용 모델 (기본 `gpt-4o-mini`) | 선택 |
| `ECOS_API_KEY` | 한국은행 ECOS | 없으면 Mock |
| `KOSIS_API_KEY` | 국가데이터처 KOSIS | 없으면 Mock |
| `SANGKWON_API_KEY` | 소진공 상권 정보 | 없으면 Mock |
| `SEOUL_SALES_API_KEY` | 서울시 추정매출 | 없으면 Mock |
| `KAKAO_REST_API_KEY` | 카카오맵 | 없으면 Mock |
| `BIZINFO_API_KEY` | 기업마당 지원사업 | 없으면 Mock |
| `FINLIFE_API_KEY` | 금감원 금융상품 비교 | 없으면 Mock |
| `VWORLD_API_KEY` | VWorld (국토부 주요상권) | 없으면 로컬 crisis 데이터 사용 |
| `CORS_ORIGINS` | CORS 허용 오리진 | 기본 `http://localhost:3000` |

> API 키가 없어도 Mock 데이터로 전체 흐름을 테스트할 수 있습니다.

---

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| GET | `/health` | 헬스체크 |
| POST | `/api/v1/agent/chat` | AI 에이전트 대화 |
| GET | `/api/v1/market/insights` | 상권·경기·소비 인사이트 |
| GET | `/api/v1/policy/funds` | 정책자금·지원사업 목록 |
| POST | `/api/v1/recommend/products` | 맞춤 금융상품 추천 |

Swagger UI: http://localhost:8000/docs

---

## 팀 규칙

아래 파일은 **팀 전체에 영향을 미치는 공유 파일**입니다. 임의 수정 금지.

| 파일 | 이유 |
|------|------|
| `project/state.py` | 공유 State 구조 — 변경 시 전 에이전트 영향 |
| `project/graph.py` | LangGraph 오케스트레이터 — 노드 추가·변경은 합의 필요 |
| `project/schemas.py` | API 응답 스키마 — 프론트엔드 연동 영향 |
