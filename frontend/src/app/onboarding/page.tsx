"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { buildRegion, REGION_GROUPS } from "@/data/regions";
import type { BusinessContext, BusinessStage } from "@/types/business";

const INDUSTRIES = [
  "카페·커피전문점",
  "한식 음식점",
  "양식·패밀리레스토랑",
  "치킨·피자·패스트푸드",
  "술집·포차",
  "편의점·슈퍼마켓",
  "소매(의류·잡화)",
  "미용실·네일샵",
  "학원·교습소",
  "PC방·오락",
  "헬스장·필라테스",
  "세탁소·수선",
  "의원·약국",
  "숙박·게스트하우스",
  "인테리어·수리",
];

const STAGES: { value: BusinessStage; label: string; desc: string }[] = [
  { value: "startup", label: "창업 준비", desc: "아직 개업 전" },
  { value: "operation", label: "운영 중", desc: "개업 후 운영" },
  { value: "expansion", label: "확장 계획", desc: "추가 점포·확장" },
];

export default function OnboardingPage() {
  const router = useRouter();
  const [context, setContext] = useState<BusinessContext>({
    region: "",
    industry: "",
    stage: "startup",
    revenue: null,
  });
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [selectedSido, setSelectedSido] = useState("");
  const [selectedSigungu, setSelectedSigungu] = useState("");

  const currentRegionGroup = REGION_GROUPS.find((group) => group.sido === selectedSido);
  const sigunguOptions = currentRegionGroup?.sigungu ?? [];

  function handleSidoChange(sido: string) {
    setSelectedSido(sido);
    setSelectedSigungu("");
    setContext({ ...context, region: "" });
  }

  function handleSigunguChange(sigungu: string) {
    setSelectedSigungu(sigungu);
    const group = REGION_GROUPS.find((item) => item.sido === selectedSido);
    if (!group || !sigungu) {
      setContext({ ...context, region: "" });
      return;
    }
    setContext({ ...context, region: buildRegion(group.label, sigungu) });
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    sessionStorage.setItem("businessContext", JSON.stringify(context));
    router.push("/agent");
  }

  const canNext1 = context.region !== "" && context.industry !== "";

  const stepLabel = step === 1 ? "지역 · 업종" : step === 2 ? "사업 단계" : "매출 정보";

  return (
    <div
      className="min-h-screen px-6 py-12"
      style={{ background: "linear-gradient(160deg, #0A0F1E 0%, #111827 100%)" }}
    >
      <div className="mx-auto max-w-lg">
        {/* Progress */}
        <div className="mb-8 flex items-center gap-2">
          {[1, 2, 3].map((n) => (
            <div key={n} className="flex items-center gap-2">
              <div
                className="flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold transition-all"
                style={
                  n <= step
                    ? {
                        background: "linear-gradient(135deg, #FFB81C, #FF8C00)",
                        color: "black",
                        boxShadow: "0 2px 10px rgba(255,184,28,0.4)",
                      }
                    : {
                        background: "rgba(255,255,255,0.08)",
                        color: "rgba(255,255,255,0.3)",
                        border: "1px solid rgba(255,255,255,0.1)",
                      }
                }
              >
                {n}
              </div>
              {n < 3 && (
                <div
                  className="h-0.5 w-8 rounded transition-all"
                  style={{
                    background: n < step ? "linear-gradient(90deg, #FFB81C, #FF8C00)" : "rgba(255,255,255,0.08)",
                  }}
                />
              )}
            </div>
          ))}
          <span className="ml-2 text-xs" style={{ color: "rgba(255,255,255,0.35)" }}>
            {stepLabel}
          </span>
        </div>

        <form onSubmit={handleSubmit}>
          {/* Step 1 */}
          {step === 1 && (
            <div className="space-y-6">
              <div>
                <h1 className="mb-1 text-xl font-bold text-white">어디서 운영하시나요?</h1>
                <p className="mb-5 text-sm" style={{ color: "rgba(255,255,255,0.4)" }}>
                  지역과 업종을 선택해 주세요.
                </p>
              </div>

              <div className="space-y-3">
                <label className="mb-2 block text-sm font-medium" style={{ color: "rgba(255,255,255,0.65)" }}>
                  지역
                </label>
                <select
                  value={selectedSido}
                  onChange={(e) => handleSidoChange(e.target.value)}
                  className="w-full rounded-xl px-4 py-2.5 text-sm outline-none transition-all"
                  style={{
                    background: "rgba(255,255,255,0.07)",
                    border: "1px solid rgba(255,255,255,0.12)",
                    color: selectedSido ? "white" : "rgba(255,255,255,0.35)",
                  }}
                >
                  <option value="" style={{ background: "#1a2236" }}>시·도를 선택하세요</option>
                  {REGION_GROUPS.map((group) => (
                    <option key={group.sido} value={group.sido} style={{ background: "#1a2236" }}>
                      {group.label}
                    </option>
                  ))}
                </select>
                <select
                  value={selectedSigungu}
                  onChange={(e) => handleSigunguChange(e.target.value)}
                  disabled={!selectedSido}
                  className="w-full rounded-xl px-4 py-2.5 text-sm outline-none transition-all disabled:cursor-not-allowed disabled:opacity-50"
                  style={{
                    background: "rgba(255,255,255,0.07)",
                    border: "1px solid rgba(255,255,255,0.12)",
                    color: selectedSigungu ? "white" : "rgba(255,255,255,0.35)",
                  }}
                >
                  <option value="" style={{ background: "#1a2236" }}>
                    {selectedSido ? "시·군·구를 선택하세요" : "먼저 시·도를 선택하세요"}
                  </option>
                  {sigunguOptions.map((sigungu) => (
                    <option key={sigungu} value={sigungu} style={{ background: "#1a2236" }}>
                      {sigungu}
                    </option>
                  ))}
                </select>
                {context.region && (
                  <p className="text-xs" style={{ color: "rgba(255,184,28,0.8)" }}>
                    선택: {context.region}
                  </p>
                )}
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium" style={{ color: "rgba(255,255,255,0.65)" }}>
                  업종
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {INDUSTRIES.map((ind) => (
                    <button
                      key={ind}
                      type="button"
                      onClick={() => setContext({ ...context, industry: ind })}
                      className="rounded-xl px-3 py-2 text-left text-xs transition-all hover:scale-[1.01]"
                      style={
                        context.industry === ind
                          ? {
                              background: "rgba(255,184,28,0.15)",
                              border: "1px solid rgba(255,184,28,0.4)",
                              color: "#FFB81C",
                              fontWeight: 600,
                            }
                          : {
                              background: "rgba(255,255,255,0.05)",
                              border: "1px solid rgba(255,255,255,0.09)",
                              color: "rgba(255,255,255,0.55)",
                            }
                      }
                    >
                      {ind}
                    </button>
                  ))}
                </div>
              </div>

              <button
                type="button"
                disabled={!canNext1}
                onClick={() => setStep(2)}
                className="w-full rounded-xl py-3 text-sm font-bold text-black transition-all hover:scale-[1.01] disabled:opacity-40 disabled:hover:scale-100"
                style={{ background: "linear-gradient(135deg, #FFB81C, #FF8C00)" }}
              >
                다음 →
              </button>
            </div>
          )}

          {/* Step 2 */}
          {step === 2 && (
            <div className="space-y-6">
              <div>
                <h1 className="mb-1 text-xl font-bold text-white">사업 단계를 알려주세요</h1>
                <p className="mb-5 text-sm" style={{ color: "rgba(255,255,255,0.4)" }}>
                  현재 상황에 맞는 단계를 선택하세요.
                </p>
              </div>

              <div className="space-y-3">
                {STAGES.map(({ value, label, desc }) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setContext({ ...context, stage: value })}
                    className="flex w-full items-center justify-between rounded-xl px-5 py-4 text-left transition-all hover:scale-[1.01]"
                    style={
                      context.stage === value
                        ? {
                            background: "rgba(255,184,28,0.12)",
                            border: "1px solid rgba(255,184,28,0.35)",
                          }
                        : {
                            background: "rgba(255,255,255,0.05)",
                            border: "1px solid rgba(255,255,255,0.09)",
                          }
                    }
                  >
                    <div>
                      <p
                        className="font-semibold"
                        style={{ color: context.stage === value ? "#FFB81C" : "white" }}
                      >
                        {label}
                      </p>
                      <p className="text-sm" style={{ color: "rgba(255,255,255,0.4)" }}>
                        {desc}
                      </p>
                    </div>
                    {context.stage === value && (
                      <div
                        className="flex h-5 w-5 items-center justify-center rounded-full text-black text-xs font-bold"
                        style={{ background: "linear-gradient(135deg, #FFB81C, #FF8C00)" }}
                      >
                        ✓
                      </div>
                    )}
                  </button>
                ))}
              </div>

              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => setStep(1)}
                  className="flex-1 rounded-xl py-3 text-sm font-medium transition-all"
                  style={{
                    background: "rgba(255,255,255,0.06)",
                    border: "1px solid rgba(255,255,255,0.1)",
                    color: "rgba(255,255,255,0.6)",
                  }}
                >
                  ← 이전
                </button>
                <button
                  type="button"
                  onClick={() => setStep(3)}
                  className="flex-1 rounded-xl py-3 text-sm font-bold text-black transition-all hover:scale-[1.01]"
                  style={{ background: "linear-gradient(135deg, #FFB81C, #FF8C00)" }}
                >
                  다음 →
                </button>
              </div>
            </div>
          )}

          {/* Step 3 */}
          {step === 3 && (
            <div className="space-y-6">
              <div>
                <h1 className="mb-1 text-xl font-bold text-white">월 매출을 입력해 주세요</h1>
                <p className="mb-5 text-sm" style={{ color: "rgba(255,255,255,0.4)" }}>
                  선택 사항입니다. 입력하면 더 정확한 금융상품을 추천드립니다.
                </p>
              </div>

              <div>
                <label className="mb-2 block text-sm font-medium" style={{ color: "rgba(255,255,255,0.65)" }}>
                  월 평균 매출 (만원){" "}
                  <span className="text-xs font-normal" style={{ color: "rgba(255,255,255,0.3)" }}>
                    선택
                  </span>
                </label>
                <div className="relative">
                  <input
                    type="number"
                    min={0}
                    placeholder="예: 3000"
                    value={context.revenue ?? ""}
                    onChange={(e) =>
                      setContext({
                        ...context,
                        revenue: e.target.value === "" ? null : Number(e.target.value),
                      })
                    }
                    className="w-full rounded-xl px-4 py-2.5 pr-12 text-sm outline-none transition-all"
                    style={{
                      background: "rgba(255,255,255,0.07)",
                      border: "1px solid rgba(255,255,255,0.12)",
                      color: "white",
                    }}
                    onFocus={(e) => {
                      e.currentTarget.style.borderColor = "rgba(255,184,28,0.5)";
                      e.currentTarget.style.boxShadow = "0 0 0 3px rgba(255,184,28,0.1)";
                    }}
                    onBlur={(e) => {
                      e.currentTarget.style.borderColor = "rgba(255,255,255,0.12)";
                      e.currentTarget.style.boxShadow = "none";
                    }}
                  />
                  <span
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-sm"
                    style={{ color: "rgba(255,255,255,0.3)" }}
                  >
                    만원
                  </span>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {[500, 1000, 2000, 3000, 5000].map((v) => (
                    <button
                      key={v}
                      type="button"
                      onClick={() => setContext({ ...context, revenue: v })}
                      className="rounded-lg px-3 py-1.5 text-xs transition-all"
                      style={
                        context.revenue === v
                          ? {
                              background: "rgba(255,184,28,0.15)",
                              border: "1px solid rgba(255,184,28,0.4)",
                              color: "#FFB81C",
                              fontWeight: 600,
                            }
                          : {
                              background: "rgba(255,255,255,0.05)",
                              border: "1px solid rgba(255,255,255,0.09)",
                              color: "rgba(255,255,255,0.45)",
                            }
                      }
                    >
                      {v.toLocaleString()}만원
                    </button>
                  ))}
                </div>
              </div>

              <div
                className="rounded-xl p-4 text-sm"
                style={{
                  background: "rgba(255,255,255,0.04)",
                  border: "1px solid rgba(255,255,255,0.09)",
                }}
              >
                <p className="mb-2 font-semibold text-white">입력하신 정보</p>
                <p style={{ color: "rgba(255,255,255,0.55)" }}>📍 {context.region} · {context.industry}</p>
                <p style={{ color: "rgba(255,255,255,0.55)" }}>
                  🏢 {STAGES.find((s) => s.value === context.stage)?.label}
                </p>
                {context.revenue && (
                  <p style={{ color: "rgba(255,255,255,0.55)" }}>
                    💵 월 {context.revenue.toLocaleString()}만원
                  </p>
                )}
              </div>

              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => setStep(2)}
                  className="flex-1 rounded-xl py-3 text-sm font-medium transition-all"
                  style={{
                    background: "rgba(255,255,255,0.06)",
                    border: "1px solid rgba(255,255,255,0.1)",
                    color: "rgba(255,255,255,0.6)",
                  }}
                >
                  ← 이전
                </button>
                <button
                  type="submit"
                  className="flex-1 rounded-xl py-3 text-sm font-bold text-black transition-all hover:scale-[1.01]"
                  style={{ background: "linear-gradient(135deg, #FFB81C, #FF8C00)" }}
                >
                  AI 에이전트 시작 →
                </button>
              </div>
            </div>
          )}
        </form>
      </div>
    </div>
  );
}
