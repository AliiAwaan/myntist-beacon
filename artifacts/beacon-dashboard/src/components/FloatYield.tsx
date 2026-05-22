import React from "react";

interface Props {
  data: any;
  loading: boolean;
  error?: string | null;
}

export default function FloatYield({ data, loading, error }: Props) {
  const value: number | null = data?.float_yield ?? null;
  const TARGET = 0.007;

  const fmt = (v: number | null) => {
    if (v === null || v === undefined) return "—";
    return (v * 1000).toFixed(4) + " ‰/day";
  };

  const statusColor =
    value === null
      ? "text-gray-400"
      : value >= TARGET
      ? "text-emerald-400"
      : value >= 0
      ? "text-amber-400"
      : "text-red-400";

  const barPct =
    value === null ? 0 : Math.min(100, Math.max(0, (value / (TARGET * 2)) * 100));

  return (
    <div className="rounded-xl border border-gray-700 bg-[#152040] p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
          Float Yield
        </h3>
        <span className="text-xs text-gray-500">Target ≥ {(TARGET * 1000).toFixed(1)}‰</span>
      </div>

      {loading ? (
        <div className="animate-pulse h-8 bg-gray-700 rounded w-32" />
      ) : error ? (
        <p className="text-xs text-red-400">{error}</p>
      ) : (
        <>
          <div className={`text-2xl font-mono font-bold ${statusColor}`}>{fmt(value)}</div>
          <div className="mt-3 h-2 rounded-full bg-gray-700 overflow-hidden">
            <div
              className={`h-2 rounded-full transition-all ${
                value !== null && value >= TARGET ? "bg-emerald-500" : "bg-amber-500"
              }`}
              style={{ width: `${barPct}%` }}
            />
          </div>
          <div className="mt-1 flex justify-between text-xs text-gray-600">
            <span>0</span>
            <span>Target {(TARGET * 1000).toFixed(1)}‰</span>
            <span>{(TARGET * 2 * 1000).toFixed(1)}‰</span>
          </div>
          {value !== null && (
            <p className={`mt-2 text-xs ${statusColor}`}>
              {value >= TARGET
                ? "✓ Yield above target"
                : value >= 0
                ? "⚠ Yield below target"
                : "✗ Yield contraction"}
            </p>
          )}
        </>
      )}

      <div className="mt-2 text-xs text-gray-600">
        Source: <code>/api/telemetry/finance</code>
      </div>
    </div>
  );
}
