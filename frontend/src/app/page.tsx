import Link from "next/link";

const FEATURES = [
  {
    icon: "🏪",
    title: "지역 상권 분석",
    desc: "상권 유동인구, 업종 밀집도, 경쟁 강도를 데이터 기반으로 분석합니다.",
    accent: "#3B82F6",
    glow: "rgba(59,130,246,0.15)",
  },
  {
    icon: "📈",
    title: "경기지표·소비트렌드 분석",
    desc: "최신 경기 지표와 소비 패턴 변화를 종합해 사업 환경을 진단합니다.",
    accent: "#10B981",
    glow: "rgba(16,185,129,0.15)",
  },
  {
    icon: "💳",
    title: "정책자금·금융상품 분석",
    desc: "정부 지원 사업과 KB 금융상품을 사업 단계·상황에 맞게 추천합니다.",
    accent: "#FFB81C",
    glow: "rgba(255,184,28,0.15)",
  },
  {
    icon: "🚨",
    title: "위기진단",
    desc: "매출 변화, 부채 수준, 시장 리스크를 종합해 경영 위기 신호를 조기 감지합니다.",
    accent: "#EF4444",
    glow: "rgba(239,68,68,0.15)",
  },
];

const STEPS = [
  { step: "01", title: "사업 정보 입력", desc: "지역·업종·사업 단계를 입력하세요." },
  { step: "02", title: "AI 멀티 에이전트 분석", desc: "4개 전문 에이전트가 병렬로 분석합니다." },
  { step: "03", title: "맞춤 결과 확인", desc: "상권·경기·정책자금·금융상품 결과를 확인하세요." },
];

const STATS = [
  { value: "4개", label: "전문 AI 에이전트" },
  { value: "15+", label: "분석 지역" },
  { value: "15+", label: "업종 지원" },
  { value: "실시간", label: "데이터 분석" },
];

export default function Home() {
  return (
    <div className="flex flex-col">
      {/* ─── Hero ──────────────────────────────────────────── */}
      <section
        className="relative overflow-hidden"
        style={{ background: "linear-gradient(135deg, #0A0F1E 0%, #0F1829 50%, #0A0F1E 100%)" }}
      >
        {/* Background orbs */}
        <div
          className="animate-float absolute -left-40 -top-40 h-96 w-96 rounded-full opacity-20 blur-3xl"
          style={{ background: "radial-gradient(circle, #FFB81C, transparent 70%)" }}
        />
        <div
          className="animate-float-slow absolute -right-32 top-20 h-80 w-80 rounded-full opacity-15 blur-3xl"
          style={{ background: "radial-gradient(circle, #3B82F6, transparent 70%)" }}
        />
        <div
          className="animate-float absolute bottom-0 left-1/2 h-64 w-64 -translate-x-1/2 rounded-full opacity-10 blur-3xl"
          style={{ background: "radial-gradient(circle, #FFB81C, transparent 70%)" }}
        />

        {/* Grid overlay */}
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)",
            backgroundSize: "60px 60px",
          }}
        />

        <div className="relative mx-auto max-w-5xl px-6 py-28 text-center">
          {/* Badge */}
          <div
            className="animate-fade-up mb-6 inline-flex items-center gap-2 rounded-full border px-4 py-1.5 text-xs font-semibold"
            style={{
              background: "rgba(255,184,28,0.1)",
              borderColor: "rgba(255,184,28,0.3)",
              color: "#FFB81C",
            }}
          >
            <span
              className="flex h-4 w-4 items-center justify-center rounded text-[9px] font-black text-white"
              style={{ background: "#FFB81C" }}
            >
              KB
            </span>
            2026 KB AI Challenge
          </div>

          {/* Headline */}
          <h1
            className="animate-fade-up mb-6 text-5xl font-black tracking-tight text-white sm:text-6xl lg:text-7xl"
            style={{ animationDelay: "0.1s", opacity: 0 }}
          >
            소상공인을 위한
            <br />
            <span className="gradient-text">AI 금융 지원</span>
            <br />
            <span className="text-white">에이전트</span>
          </h1>

          {/* Sub */}
          <p
            className="animate-fade-up mx-auto mb-10 max-w-xl text-base leading-relaxed"
            style={{ color: "rgba(255,255,255,0.5)", animationDelay: "0.2s", opacity: 0 }}
          >
            지역 상권·경기지표·소비 트렌드·정책자금 정보를 종합 분석하여
            창업·운영·확장 의사결정을 지원합니다.
          </p>

          {/* CTAs */}
          <div
            className="animate-fade-up flex flex-wrap items-center justify-center gap-3"
            style={{ animationDelay: "0.3s", opacity: 0 }}
          >
            <Link
              href="/onboarding"
              className="group relative overflow-hidden rounded-xl px-8 py-3.5 text-sm font-bold text-black shadow-2xl transition-all hover:scale-105"
              style={{ background: "linear-gradient(135deg, #FFB81C, #FF8C00)" }}
            >
              <span className="relative z-10">지금 시작하기 →</span>
            </Link>
            <Link
              href="/agent"
              className="rounded-xl border px-8 py-3.5 text-sm font-medium transition-all hover:scale-105"
              style={{
                borderColor: "rgba(255,255,255,0.15)",
                color: "rgba(255,255,255,0.75)",
                background: "rgba(255,255,255,0.05)",
              }}
            >
              바로 체험해보기
            </Link>
          </div>

          {/* Stats row */}
          <div
            className="animate-fade-up mx-auto mt-16 grid max-w-2xl grid-cols-2 gap-4 sm:grid-cols-4"
            style={{ animationDelay: "0.4s", opacity: 0 }}
          >
            {STATS.map((s) => (
              <div
                key={s.label}
                className="rounded-2xl border p-4 text-center"
                style={{
                  background: "rgba(255,255,255,0.04)",
                  borderColor: "rgba(255,255,255,0.08)",
                }}
              >
                <p className="text-xl font-black" style={{ color: "#FFB81C" }}>
                  {s.value}
                </p>
                <p className="mt-0.5 text-xs" style={{ color: "rgba(255,255,255,0.4)" }}>
                  {s.label}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── Features ──────────────────────────────────────── */}
      <section
        className="py-20"
        style={{ background: "linear-gradient(180deg, #0A0F1E 0%, #111827 100%)" }}
      >
        <div className="mx-auto max-w-5xl px-6">
          <div className="mb-12 text-center">
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest" style={{ color: "#FFB81C" }}>
              Multi-Agent System
            </p>
            <h2 className="text-3xl font-bold text-white">
              4가지 전문 에이전트가 함께합니다
            </h2>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {FEATURES.map((f) => (
              <div
                key={f.title}
                className="feature-card group rounded-2xl p-6 transition-all duration-300 hover:scale-[1.02] hover:-translate-y-1"
                style={{
                  background: "rgba(255,255,255,0.04)",
                  border: "1px solid rgba(255,255,255,0.1)",
                  ["--glow" as string]: f.glow,
                  ["--accent" as string]: f.accent,
                }}
              >
                <div
                  className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl text-2xl"
                  style={{ background: f.glow, border: `1px solid ${f.accent}30` }}
                >
                  {f.icon}
                </div>
                <h3 className="mb-2 text-sm font-bold leading-snug text-white">{f.title}</h3>
                <p className="text-xs leading-relaxed" style={{ color: "rgba(255,255,255,0.45)" }}>
                  {f.desc}
                </p>
                <div
                  className="mt-4 h-0.5 w-8 rounded-full transition-all duration-300 group-hover:w-full"
                  style={{ background: `linear-gradient(90deg, ${f.accent}, transparent)` }}
                />
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── How it works ──────────────────────────────────── */}
      <section className="bg-white py-20">
        <div className="mx-auto max-w-3xl px-6">
          <div className="mb-12 text-center">
            <p
              className="mb-2 text-xs font-semibold uppercase tracking-widest"
              style={{ color: "#FFB81C" }}
            >
              How it works
            </p>
            <h2 className="text-3xl font-bold text-zinc-900">3단계로 끝나는 분석</h2>
          </div>

          <div className="relative flex flex-col gap-6 sm:flex-row">
            {/* Connector line */}
            <div
              className="absolute left-6 top-6 hidden h-0.5 w-[calc(100%-48px)] sm:block"
              style={{ background: "linear-gradient(90deg, #FFB81C, #FF8C00, #FFB81C)" }}
            />
            {STEPS.map((s) => (
              <div key={s.step} className="relative flex flex-1 flex-col items-center text-center">
                <div
                  className="relative mb-5 flex h-12 w-12 items-center justify-center rounded-full text-sm font-black text-black shadow-lg"
                  style={{
                    background: "linear-gradient(135deg, #FFB81C, #FF8C00)",
                    boxShadow: "0 4px 20px rgba(255,184,28,0.4)",
                  }}
                >
                  {s.step}
                </div>
                <h3 className="mb-2 font-bold text-zinc-900">{s.title}</h3>
                <p className="text-sm leading-relaxed text-zinc-500">{s.desc}</p>
              </div>
            ))}
          </div>

          <div className="mt-12 text-center">
            <Link
              href="/onboarding"
              className="inline-block rounded-xl px-10 py-4 text-sm font-bold text-black shadow-lg transition-all hover:scale-105 hover:shadow-xl"
              style={{ background: "linear-gradient(135deg, #FFB81C, #FF8C00)" }}
            >
              지금 무료로 시작하기 →
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
