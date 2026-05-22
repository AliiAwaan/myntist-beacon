import React from "react";

interface Props {
  data: any;
  loading: boolean;
  error?: string | null;
}

const ALERT_THRESHOLD = 0.25;

export default function CoherenceSignal({ data, loading, error }: Props) {
  const value: number | null = data?.Ttau ?? data?.coherence_signal ?? null;

  const fmt = (v: number | null) => {
    if (v === null || v === undefined) return "—";
    return v.toFixed(6);
  };

  const alert = value !== null && value > ALERT_THRESHOLD;
  const statusColor =
    value === null ? "text-gray-400" : alert ? "text-red-400" : "text-emerald-400";

  const barPct =
    value === null ? 0 : Math.min(100, Math.max(0, (value / (ALERT_THRESHOLD * 2)) * 100));

  return (
    <div className="rounded-xl border border-gray-700 bg-[#152040] p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
          Coherence Signal (Ttau)
        </h3>
        <span className={`text-xs ${alert ? "text-red-400 font-semibold" : "text-gray-500"}`}>
          {alert ? "⚠ ALERT > " : "Alert at >"}{ALERT_THRESHOLD}
        </span>
      </div>

      {loading ? (
        <div className="animate-pulse h-8 bg-gray-700 rounded w-32" />
      ) : error ? (
        <p className="text-xs text-red-400">{error}</p>
      ) : (
        <>
          <div className={`text-2xl font-mono font-bold ${statusColor}`}>{fmt(value)}</div>

          <div className="mt-3 relative h-2 rounded-full bg-gray-700 overflow-hidden">
            <div
              className="absolute inset-y-0 left-0 right-1/2 bg-emerald-800 opacity-30 rounded-full"
            />
            <div
              className={`h-2 rounded-full transition-all ${alert ? "bg-red-500" : "bg-emerald-500"}`}
              style={{ width: `${barPct}%` }}
            />
            <div
              className="absolute top-0 bottom-0 w-0.5 bg-yellow-400"
              style={{ left: "50%" }}
            />
          </div>
          <div className="mt-1 flex justify-between text-xs text-gray-600">
            <span>0</span>
            <span className="text-yellow-500">{ALERT_THRESHOLD} ⚠</span>
            <span>{ALERT_THRESHOLD * 2}</span>
          </div>

          <p className={`mt-2 text-xs ${statusColor}`}>
            {value === null
              ? "No data"
              : alert
              ? "✗ P002 may throttle after 3 consecutive breaches"
              : "✓ Ttau within safe range"}
          </p>
        </>
      )}

      <div className="mt-2 text-xs text-gray-600">
        Source: <code>/api/telemetry/temporal</code>
      </div>
    </div>
  );
}
