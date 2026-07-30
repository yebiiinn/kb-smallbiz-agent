import type { CrisisInsight } from "@/types/market";

interface CrisisInsightCardProps {
  crisis: CrisisInsight | null | undefined;
  loading?: boolean;
}

const LEVEL_CONFIG = {
  normal: {
    label: "양호",
    accent: "#10B981",
    glow: "rgba(16,185,129,0.12)",
    border: "rgba(16,185,129,0.25)",
    icon: "✅",
  },
  warning: {
    label: "주의",
    accent: "#FFB81C",
    glow: "rgba(255,184,28,0.12)",
    border: "rgba(255,184,28,0.3)",
    icon: "⚠️",
  },
  critical: {
    label: "위험",
    accent: "#EF4444",
    glow: "rgba(239,68,68,0.12)",
    border: "rgba(239,68,68,0.3)",
    icon: "🚨",
  },
} as const;

export function CrisisInsightCard({ crisis, loading }: CrisisInsightCardProps) {
  if (!crisis && !loading) return null;

  const level = crisis?.level ?? "normal";
  const cfg = LEVEL_CONFIG[level] ?? LEVEL_CONFIG.normal;

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
        <span className="text-base">⚠️</span>
        <h3 className="text-sm font-semibold text-white">위기진단</h3>
        {loading && !crisis && (
          <span className="ml-auto animate-pulse text-xs" style={{ color: "#FFB81C" }}>
            분석 중...
          </span>
        )}
        {crisis && (
          <span
            className="ml-auto rounded-full px-2 py-0.5 text-xs font-bold"
            style={{ background: cfg.glow, color: cfg.accent, border: `1px solid ${cfg.border}` }}
          >
            {cfg.icon} {cfg.label} · {Math.round(crisis.score)}점
          </span>
        )}
      </div>

      {loading && !crisis && (
        <div className="space-y-2">
          <div className="h-3 w-full animate-pulse rounded-md" style={{ background: "rgba(255,255,255,0.06)" }} />
          <div className="h-3 w-4/5 animate-pulse rounded-md" style={{ background: "rgba(255,255,255,0.06)" }} />
        </div>
      )}

      {crisis && (
        <div
          className="rounded-xl p-3"
          style={{ background: cfg.glow, border: `1px solid ${cfg.border}` }}
        >
          <p className="text-[13px] leading-relaxed" style={{ color: "rgba(255,255,255,0.85)" }}>
            {crisis.summary}
          </p>
          {crisis.recommended_actions.length > 0 && (
            <ul className="mt-3 space-y-1.5">
              {crisis.recommended_actions.map((action) => (
                <li
                  key={action}
                  className="text-xs leading-relaxed"
                  style={{ color: "rgba(255,255,255,0.65)" }}
                >
                  · {action}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
