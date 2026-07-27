import type { RecommendationItem } from "@/types/market";

interface ProductRecommendListProps {
  items: RecommendationItem[];
  loading?: boolean;
}

const TYPE_CONFIG = {
  policy_fund: {
    label: "정책자금",
    icon: "🏛️",
    accent: "#3B82F6",
    glow: "rgba(59,130,246,0.1)",
    border: "rgba(59,130,246,0.2)",
    badgeBg: "rgba(59,130,246,0.15)",
    badgeColor: "#60A5FA",
  },
  financial_product: {
    label: "KB 금융상품",
    icon: "💳",
    accent: "#FFB81C",
    glow: "rgba(255,184,28,0.1)",
    border: "rgba(255,184,28,0.2)",
    badgeBg: "rgba(255,184,28,0.12)",
    badgeColor: "#FFB81C",
  },
} as const;

function getTypeConfig(type: string) {
  return (
    TYPE_CONFIG[type as keyof typeof TYPE_CONFIG] ?? {
      label: type,
      icon: "📌",
      accent: "#9CA3AF",
      glow: "rgba(156,163,175,0.1)",
      border: "rgba(156,163,175,0.2)",
      badgeBg: "rgba(156,163,175,0.12)",
      badgeColor: "#9CA3AF",
    }
  );
}

function SkeletonCard() {
  return (
    <div
      className="rounded-xl p-4"
      style={{
        background: "rgba(255,255,255,0.04)",
        border: "1px solid rgba(255,255,255,0.08)",
      }}
    >
      <div className="mb-2 flex items-center gap-2">
        <div className="h-4 w-16 animate-pulse rounded-full" style={{ background: "rgba(255,255,255,0.08)" }} />
        <div className="h-4 w-28 animate-pulse rounded" style={{ background: "rgba(255,255,255,0.08)" }} />
      </div>
      <div className="space-y-1.5">
        <div className="h-3 w-full animate-pulse rounded" style={{ background: "rgba(255,255,255,0.06)" }} />
        <div className="h-3 w-4/5 animate-pulse rounded" style={{ background: "rgba(255,255,255,0.06)" }} />
      </div>
    </div>
  );
}

export function ProductRecommendList({ items, loading }: ProductRecommendListProps) {
  return (
    <div
      className="rounded-2xl p-5"
      style={{
        background: "rgba(255,255,255,0.04)",
        border: "1px solid rgba(255,255,255,0.1)",
        backdropFilter: "blur(20px)",
      }}
    >
      <div className="mb-4 flex items-center gap-2">
        <span className="text-base">💰</span>
        <h3 className="text-sm font-semibold text-white">맞춤 추천</h3>
        {items.length > 0 && (
          <span
            className="ml-auto rounded-full px-2 py-0.5 text-xs font-bold"
            style={{ background: "rgba(255,184,28,0.15)", color: "#FFB81C" }}
          >
            {items.length}건
          </span>
        )}
        {loading && (
          <span className="ml-auto animate-pulse text-xs" style={{ color: "#FFB81C" }}>
            추천 생성 중...
          </span>
        )}
      </div>

      {!loading && items.length === 0 && (
        <p className="text-sm" style={{ color: "rgba(255,255,255,0.3)" }}>
          정책자금·금융상품 추천이 여기에 표시됩니다.
        </p>
      )}

      {loading && items.length === 0 && (
        <div className="space-y-3">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      )}

      {items.length > 0 && (
        <div className="space-y-3">
          {items.map((item, i) => {
            const cfg = getTypeConfig(item.type);
            return (
              <div
                key={i}
                className="rounded-xl p-4 transition-all duration-200 hover:scale-[1.01]"
                style={{
                  background: cfg.glow,
                  border: `1px solid ${cfg.border}`,
                }}
              >
                <div className="mb-2 flex flex-wrap items-start gap-2">
                  <span
                    className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold"
                    style={{ background: cfg.badgeBg, color: cfg.badgeColor }}
                  >
                    {cfg.icon} {cfg.label}
                  </span>
                  <p className="text-sm font-semibold leading-snug text-white">{item.name}</p>
                </div>
                <p className="mb-3 text-xs leading-relaxed" style={{ color: "rgba(255,255,255,0.5)" }}>
                  {item.reason}
                </p>
                {item.link && (
                  <a
                    href={item.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs font-semibold underline-offset-2 hover:underline"
                    style={{ color: cfg.accent }}
                  >
                    자세히 보기 →
                  </a>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
