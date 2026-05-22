import React from "react";

interface Props {
  data: any;
  loading: boolean;
  error?: string | null;
}

const RED_THRESHOLD = 0.10;

export default function LiquiditySignal({ data, loading, error }: Props) {
  const value: number | null = data?.D ?? data?.liquidity_signal ?? null;

  const fmt = (v: number | null) => {
    if (v === null || v === undefined) return "—";
    return v.toFixed(6);
  };

  const statusColor =
    value === null
      ? "text-gray-400"
      : value >= RED_THRESHOLD
      ? "text-emerald-400"
      : "text-red-400";

  const pct = value === null ? 0 : Math.min(100, Math.max(0, (value / 0.5) * 100));

  const arcPath = (percent: number) => {
    const angle = (percent / 100) * 180 - 90;
    const rad = (angle * Math.PI) / 180;
    const r = 44;
    const cx = 60;
    const cy = 55;
    const x = cx + r * Math.cos(rad);
    const y = cy + r * Math.sin(rad);
    return `M ${cx} ${cy} L ${x} ${y}`;
  };

  return (
    <div className="rounded-xl border border-gray-700 bg-[#152040] p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
          Liquidity Signal (D)
        </h3>
        <span className="text-xs text-gray-500">Alert below {RED_THRESHOLD}</span>
      </div>

      {loading ? (
        <div className="animate-pulse h-20 bg-gray-700 rounded" />
      ) : error ? (
        <p className="text-xs text-red-400">{error}</p>
      ) : (
        <>
          <div className="flex items-center gap-4">
            <svg width="120" height="70" className="shrink-0">
              <path
                d="M 16 60 A 44 44 0 0 1 104 60"
                fill="none"
                stroke="#374151"
                strokeWidth="8"
                strokeLinecap="round"
              />
              <path
                d="M 16 60 A 44 44 0 0 1 104 60"
                fill="none"
                stroke={value !== null && value < RED_THRESHOLD ? "#ef4444" : "#10b981"}
                strokeWidth="8"
                strokeLinecap="round"
                strokeDasharray={`${pct * 1.385} 138.5`}
              />
              <line
                x1="60"
                y1="60"
                x2={60 + 40 * Math.cos(((pct / 100) * 180 - 90 + 180) * (Math.PI / 180))}
                y2={60 + 40 * Math.sin(((pct / 100) * 180 - 90 + 180) * (Math.PI / 180))}
                stroke="white"
                strokeWidth="2"
                strokeLinecap="round"
              />
              <circle cx="60" cy="60" r="4" fill="white" />
            </svg>
            <div>
              <div className={`text-2xl font-mono font-bold ${statusColor}`}>{fmt(value)}</div>
              <p className={`mt-1 text-xs ${statusColor}`}>
                {value === null
                  ? "No data"
                  : value >= RED_THRESHOLD
                  ? "✓ Adequate liquidity"
                  : "✗ Low liquidity — P001 may block tokens"}
              </p>
            </div>
          </div>
        </>
      )}

      <div className="mt-2 text-xs text-gray-600">
        Source: <code>/api/telemetry/temporal</code>
      </div>
    </div>
  );
}
