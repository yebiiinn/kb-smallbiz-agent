"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type { BusinessContext, BusinessStage } from "@/types/business";

const REGIONS = ["서울 강남구", "서울 마포구", "부산 해운대구"];
const INDUSTRIES = ["카페", "음식점", "소매"];
const STAGES: { value: BusinessStage; label: string }[] = [
  { value: "startup", label: "창업" },
  { value: "operation", label: "운영" },
  { value: "expansion", label: "확장" },
];

export default function OnboardingPage() {
  const router = useRouter();
  const [context, setContext] = useState<BusinessContext>({
    region: "서울 강남구",
    industry: "카페",
    stage: "startup",
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    sessionStorage.setItem("businessContext", JSON.stringify(context));
    router.push("/agent");
  }

  return (
    <div className="mx-auto max-w-lg px-6 py-16">
      <h1 className="mb-2 text-2xl font-bold">사업 정보 입력</h1>
      <p className="mb-8 text-sm text-zinc-500">
        맞춤 분석을 위해 기본 정보를 입력해 주세요.
      </p>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="mb-2 block text-sm font-medium">지역</label>
          <select
            value={context.region}
            onChange={(e) => setContext({ ...context, region: e.target.value })}
            className="w-full rounded-xl border border-zinc-200 px-4 py-2.5 text-sm outline-none focus:border-amber-400"
          >
            {REGIONS.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="mb-2 block text-sm font-medium">업종</label>
          <select
            value={context.industry}
            onChange={(e) => setContext({ ...context, industry: e.target.value })}
            className="w-full rounded-xl border border-zinc-200 px-4 py-2.5 text-sm outline-none focus:border-amber-400"
          >
            {INDUSTRIES.map((i) => (
              <option key={i} value={i}>
                {i}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="mb-2 block text-sm font-medium">사업 단계</label>
          <div className="flex gap-2">
            {STAGES.map(({ value, label }) => (
              <button
                key={value}
                type="button"
                onClick={() => setContext({ ...context, stage: value })}
                className={`flex-1 rounded-xl border py-2.5 text-sm font-medium transition-colors ${
                  context.stage === value
                    ? "border-amber-400 bg-amber-50 text-amber-700"
                    : "border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-50"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <button
          type="submit"
          className="w-full rounded-xl bg-amber-500 py-3 text-sm font-medium text-white hover:bg-amber-600"
        >
          AI 에이전트 시작
        </button>
      </form>
    </div>
  );
}
