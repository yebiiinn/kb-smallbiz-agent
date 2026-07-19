# 소상공인 금융 지원 에이전트

> 2026 KB AI Challenge — AI 기술을 활용한 금융 관련 서비스

지역 상권, 경기지표, 소비 트렌드, 정책자금 정보를 종합 분석하여 소상공인의 경영 의사결정을 지원하는 AI 에이전트입니다.

## 주요 기능

- **시장 인사이트**: 지역 상권·경기지표·소비 트렌드 종합 분석
- **정책자금 안내**: 정부 지원 사업·정책자금 매칭
- **금융상품 추천**: 창업/운영 단계별 맞춤 금융 상품 제안
- **AI 에이전트**: 자연어 대화 기반 의사결정 지원

## 프로젝트 구조

```
kb-ai-challenge/
├── frontend/              # Next.js (App Router + TypeScript + Tailwind)
├── backend/
│   └── project/           # FastAPI + LangGraph (팀 공동 작업)
│       ├── main.py        # FastAPI 진입점
│       ├── graph.py       # LangGraph 오케스트레이터
│       ├── state.py       # 공유 State
│       ├── agents/
│       │   ├── commercial.py   # 지역 상권 (담당 A)
│       │   ├── economic.py     # 경기·소비 (담당 A/B)
│       │   ├── finance.py      # 정책자금·금융상품 (담당 B)
│       │   └── crisis.py       # 위기진단 (담당 B)
│       ├── tools/
│       │   ├── sangkwon_api.py     # 소진공 상권 정보
│       │   ├── seoul_sales_api.py  # 서울시 추정매출
│       │   ├── kakao_map_api.py    # 카카오맵
│       │   ├── ecos_api.py         # 한국은행 ECOS
│       │   ├── kosis_api.py        # 통계청 KOSIS
│       │   ├── bizinfo_api.py      # 기업마당 지원사업
│       │   └── finlife_api.py      # 금감원 금융상품 비교
│       └── .env.example
└── docker-compose.yml
```

## 실행 방법

### 1. Backend (FastAPI)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp project/.env.example project/.env
uvicorn project.main:app --reload
```

→ http://localhost:8000/docs

### 2. Frontend (Next.js)

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

→ http://localhost:3000

### 3. Docker (선택)

```bash
docker compose up
```

## 환경 변수

| 파일 | 변수 | 설명 |
|------|------|------|
| `backend/project/.env` | `OPENAI_API_KEY` | LLM |
| | `SANGKWON_API_KEY` | 소진공 상권 정보 |
| | `SEOUL_SALES_API_KEY` | 서울시 추정매출 |
| | `KAKAO_REST_API_KEY` | 카카오맵 |
| | `ECOS_API_KEY` | 한국은행 ECOS |
| | `KOSIS_API_KEY` | 통계청 KOSIS |
| | `BIZINFO_API_KEY` | 기업마당 지원사업 |
| | `FINLIFE_API_KEY` | 금감원 금융상품 비교 |
| | *(키 없으면 mock)* | |
| | *API 호출 URL* | 각 `tools/*_api.py` 상단 `API_URL` |
| `frontend/.env.local` | `NEXT_PUBLIC_API_URL` | 백엔드 URL (기본: http://localhost:8000) |

## 데모 시나리오

1. `/onboarding` — 지역(강남구), 업종(카페), 단계(창업) 입력
2. `/agent` — "창업 자금 어떻게 마련할까?" 질문
3. 에이전트가 상권 분석 + 정책자금 + 금융상품 추천 제공

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/v1/agent/chat` | AI 에이전트 대화 |
| GET | `/api/v1/market/insights` | 상권·경기·소비 인사이트 |
| GET | `/api/v1/policy/funds` | 정책자금·지원사업 목록 |
| POST | `/api/v1/recommend/products` | 맞춤 금융상품 추천 |

## 팀원

| 이름 | 학교 | 역할 |
|------|------|------|
| (작성) | | |
