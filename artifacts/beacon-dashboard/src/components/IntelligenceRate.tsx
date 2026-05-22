import React from "react";

interface Props {
  data: any;
  loading: boolean;
  error?: string | null;
}

const BAND_LOW = 0.005;
const BAND_HIGH = 0.03;

export default function IntelligenceRate({ data, loading, error }: Props) {
  const value: number | null = data?.r_HSCE ?? null;

  const fmt = (v: number | null) => {
    if (v === null || v === undefined) return "—";
    return v.toFixed(6) + " /day";
  };

  const inBand = value !== null && value >= BAND_LOW && value <= BAND_HIGH;
  const statusColor =
    value === null
      ? "text-gray-400"
      : inBand
      ? "text-emerald-400"
      : value < BAND_LOW
      ? "text-amber-400"
      : "text-orange-400";

  return (
    <div className="rounded-xl border border-gray-700 bg-[#152040] p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
          Intelligence Rate (r_HSCE)
        </h3>
        <span className="text-xs text-gray-500">
          Band [{BAND_LOW.toFixed(3)}–{BAND_HIGH.toFixed(3)}]
        </span>
      </div>

      {loading ? (
        <div className="animate-pulse h-8 bg-gray-700 rounded w-40" />
      ) : error ? (
        <p className="text-xs text-red-400">{error}</p>
      ) : (
        <>
          <div className={`text-2xl font-mono font-bold ${statusColor}`}>{fmt(value)}</div>

          {value === null ? (
            <p className="mt-2 text-xs text-gray-500">
              Insufficient history (requires 7 days)
            </p>
          ) : (
            <>
              <div className="mt-3 relative h-4 rounded-full bg-gray-700 overflow-hidden">
                <div
                  className="absolute inset-y-0 bg-emerald-800 opacity-50"
                  style={{
                    left: `${(BAND_LOW / (BAND_HIGH * 2)) * 100}%`,
                    right: `${100 - (BAND_HIGH / (BAND_HIGH * 2)) * 100}%`,
                  }}
                />
                <div
                  className="absolute top-1/2 -translate-y-1/2 w-2 h-4 rounded bg-white"
                  style={{
                    left: `${Math.min(100, Math.max(0, (value / (BAND_HIGH * 2)) * 100))}%`,
                  }}
                />
              </div>
              <p className={`mt-2 text-xs ${statusColor}`}>
                {inBand
                  ? "✓ Within coherence band"
                  : value < BAND_LOW
                  ? "⚠ Below coherence band"
                  : "⚠ Above coherence band"}
              </p>
            </>
          )}
        </>
      )}

      <div className="mt-2 text-xs text-gray-600">
        Source: <code>/api/telemetry/finance</code>
      </div>
    </div>
  );
}
