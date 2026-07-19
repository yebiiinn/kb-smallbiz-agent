import Link from "next/link";

export default function Home() {
  return (
    <div className="mx-auto max-w-4xl px-6 py-20">
      <div className="mb-4 inline-block rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-700">
        2026 KB AI Challenge
      </div>
      <h1 className="mb-4 text-4xl font-bold tracking-tight text-zinc-900">
        소상공인 금융 지원 에이전트
      </h1>
      <p className="mb-8 max-w-2xl text-lg leading-relaxed text-zinc-600">
        지역 상권, 경기지표, 소비 트렌드, 정책자금 정보를 종합 분석하여
        소상공인의 창업·운영 의사결정을 지원합니다.
      </p>

      <div className="mb-10 grid gap-4 sm:grid-cols-3">
        {[
          { icon: "📊", title: "시장 인사이트", desc: "상권·경기·소비 트렌드 분석" },
          { icon: "🏛️", title: "정책자금 안내", desc: "정부 지원 사업 매칭" },
          { icon: "💰", title: "금융상품 추천", desc: "단계별 맞춤 제안" },
        ].map((item) => (
          <div
            key={item.title}
            className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm"
          >
            <div className="mb-2 text-2xl">{item.icon}</div>
            <h3 className="mb-1 font-semibold">{item.title}</h3>
            <p className="text-sm text-zinc-500">{item.desc}</p>
          </div>
        ))}
      </div>

      <div className="flex gap-4">
        <Link
          href="/onboarding"
          className="rounded-xl bg-amber-500 px-6 py-3 text-sm font-medium text-white hover:bg-amber-600"
        >
          시작하기
        </Link>
        <Link
          href="/agent"
          className="rounded-xl border border-zinc-200 bg-white px-6 py-3 text-sm font-medium text-zinc-700 hover:bg-zinc-50"
        >
          바로 체험
        </Link>
      </div>
    </div>
  );
}
