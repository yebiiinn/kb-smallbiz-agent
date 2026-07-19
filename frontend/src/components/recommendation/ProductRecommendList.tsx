import type { RecommendationItem } from "@/types/market";

interface ProductRecommendListProps {
  items: RecommendationItem[];
}

export function ProductRecommendList({ items }: ProductRecommendListProps) {
  if (items.length === 0) {
    return (
      <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
        <h3 className="mb-2 text-sm font-semibold text-zinc-900">💰 추천</h3>
        <p className="text-sm text-zinc-400">정책자금·금융상품 추천이 여기에 표시됩니다.</p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
      <h3 className="mb-4 text-sm font-semibold text-zinc-900">💰 추천</h3>
      <div className="space-y-3">
        {items.map((item, i) => (
          <div
            key={i}
            className="rounded-xl border border-zinc-100 bg-zinc-50 p-4"
          >
            <div className="mb-1 flex items-center gap-2">
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                  item.type === "policy_fund"
                    ? "bg-blue-100 text-blue-700"
                    : "bg-emerald-100 text-emerald-700"
                }`}
              >
                {item.type === "policy_fund" ? "정책자금" : "금융상품"}
              </span>
              <p className="text-sm font-medium text-zinc-900">{item.name}</p>
            </div>
            <p className="text-xs leading-relaxed text-zinc-500">{item.reason}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
