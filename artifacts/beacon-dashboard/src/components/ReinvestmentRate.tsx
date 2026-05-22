import React from "react";

interface Props {
  finance: any;
  temporal: any;
  loading: boolean;
  error?: string | null;
}

export default function ReinvestmentRate({ finance, temporal, loading, error }: Props) {
  const rate: number | null = finance?.float_reinvestment_rate ?? null;
  const admitted: boolean | null = temporal?.admitted ?? null;
  const throttle: number | null = temporal?.throttle_rate ?? null;
  const activePolicies: string[] = temporal?.active_policy_ids ?? [];

  const fmt = (v: number | null) => {
    if (v === null || v === undefined) return "—";
    return (v * 100).toFixed(1) + "%";
  };

  const rateColor =
    rate === null
      ? "text-gray-400"
      : rate >= 0.5
      ? "text-emerald-400"
      : "text-amber-400";

  return (
    <div className="rounded-xl border border-gray-700 bg-[#152040] p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
          Reinvestment Rate
        </h3>
        <span className="text-xs text-gray-500">Constant from env</span>
      </div>

      {loading ? (
        <div className="animate-pulse space-y-2">
          <div className="h-8 bg-gray-700 rounded w-24" />
          <div className="h-4 bg-gray-700 rounded w-40" />
        </div>
      ) : error ? (
        <p className="text-xs text-red-400">{error}</p>
      ) : (
        <div className="space-y-4">
          <div>
            <p className="text-xs text-gray-500 mb-1">Float Reinvestment Rate</p>
            <div className={`text-3xl font-mono font-bold ${rateColor}`}>{fmt(rate)}</div>
          </div>

          <div className="border-t border-gray-700 pt-3">
            <p className="text-xs text-gray-500 mb-2">Policy Gate Status</p>
            <div className="flex items-center gap-2">
              <div
                className={`w-3 h-3 rounded-full ${
                  admitted === null
                    ? "bg-gray-500"
                    : admitted
                    ? "bg-emerald-500"
                    : "bg-red-500"
                }`}
              />
              <span className="text-sm font-medium">
                {admitted === null
                  ? "Unknown"
                  : admitted
                  ? "Admitted"
                  : "Blocked / Throttled"}
              </span>
              {throttle !== null && (
                <span className="text-xs text-amber-400 ml-auto">
                  Throttle {fmt(throttle)}
                </span>
              )}
            </div>
          </div>

          {activePolicies.length > 0 && (
            <div>
              <p className="text-xs text-gray-500 mb-1">Active Policies</p>
              <div className="flex flex-wrap gap-1">
                {activePolicies.map((pid) => (
                  <span
                    key={pid}
                    className="px-2 py-0.5 text-xs rounded bg-red-900 text-red-300 border border-red-700"
                  >
                    {pid}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="mt-3 text-xs text-gray-600">
        Sources: <code>/api/telemetry/finance</code> · <code>/api/telemetry/temporal</code>
      </div>
    </div>
  );
}
