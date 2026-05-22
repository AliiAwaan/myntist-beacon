import React from "react";
import { useApi, POLL_INTERVAL_MS } from "../hooks/useApi";

const P_COLORS: Record<string, string> = {
  P001: "bg-orange-700 text-orange-100",
  P002: "bg-red-700 text-red-100",
  P003: "bg-amber-700 text-amber-100",
};

function policyBadge(id: string) {
  return P_COLORS[id] ?? "bg-gray-700 text-gray-100";
}

export default function TemporalBus() {
  const { data, loading, error } = useApi("/telemetry/temporal", POLL_INTERVAL_MS);

  const S: number | null = data?.S ?? null;
  const Q: number | null = data?.Q ?? null;
  const tau: number | null = data?.tau ?? null;
  const D: number | null = data?.D ?? null;
  const Ttau: number | null = data?.Ttau ?? null;
  const S_times_D: number | null = data?.S_times_D ?? null;
  const admitted: boolean | null = data?.admitted ?? null;
  const activePolicies: string[] = data?.active_policy_ids ?? [];
  const throttleRate: number | null = data?.throttle_rate ?? null;

  const fmt4 = (v: number | null) => (v === null ? "—" : v.toFixed(4));
  const fmt6 = (v: number | null) => (v === null ? "—" : v.toFixed(6));

  const admittedColor =
    admitted === null
      ? "text-gray-400"
      : admitted
      ? "text-emerald-400"
      : "text-red-400";

  const admittedLabel =
    admitted === null ? "—" : admitted ? "ADMITTED" : "BLOCKED";

  return (
    <div className="rounded-xl border border-gray-700 bg-[#152040] p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
          TemporalBus · IAM Policy Gate
        </h3>
        <span className="text-xs text-gray-500">
          Source: <code>/api/telemetry/temporal</code>
        </span>
      </div>

      {loading ? (
        <div className="space-y-2 animate-pulse">
          <div className="h-6 bg-gray-700 rounded w-24" />
          <div className="h-4 bg-gray-700 rounded w-full" />
          <div className="h-4 bg-gray-700 rounded w-3/4" />
        </div>
      ) : error ? (
        <p className="text-xs text-red-400">{error}</p>
      ) : (
        <>
          <div className="flex items-center gap-4 mb-4">
            <div>
              <div className={`text-2xl font-mono font-bold ${admittedColor}`}>
                {admittedLabel}
              </div>
              <div className="text-xs text-gray-500 mt-0.5">Token gate status</div>
            </div>
            {throttleRate !== null && throttleRate > 0 && (
              <div className="ml-auto text-right">
                <div className="text-lg font-mono font-bold text-amber-400">
                  {(throttleRate * 100).toFixed(0)}%
                </div>
                <div className="text-xs text-gray-500">Throttle rate</div>
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-2 text-sm mb-4">
            <div>
              <span className="text-gray-500 text-xs uppercase tracking-wider">S (survivability)</span>
              <div className={`font-mono ${S !== null && S < 0.7 ? "text-red-400" : "text-gray-200"}`}>
                {fmt4(S)}
              </div>
            </div>
            <div>
              <span className="text-gray-500 text-xs uppercase tracking-wider">Q (coherence)</span>
              <div className="font-mono text-gray-200">{fmt4(Q)}</div>
            </div>
            <div>
              <span className="text-gray-500 text-xs uppercase tracking-wider">tau</span>
              <div className="font-mono text-gray-200">{fmt4(tau)}</div>
            </div>
            <div>
              <span className="text-gray-500 text-xs uppercase tracking-wider">D (liquidity)</span>
              <div className={`font-mono ${D !== null && D < 0.1 ? "text-red-400" : "text-emerald-400"}`}>
                {fmt6(D)}
              </div>
            </div>
            <div>
              <span className="text-gray-500 text-xs uppercase tracking-wider">Ttau (coherence drift)</span>
              <div className={`font-mono ${Ttau !== null && Ttau > 0.25 ? "text-red-400" : "text-emerald-400"}`}>
                {fmt6(Ttau)}
              </div>
            </div>
            <div>
              <span className="text-gray-500 text-xs uppercase tracking-wider">S × D</span>
              <div className="font-mono text-gray-200">{fmt6(S_times_D)}</div>
            </div>
          </div>

          <div>
            <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">
              Active policies
            </div>
            {activePolicies.length === 0 ? (
              <span className="text-xs text-emerald-400">✓ No policies tripped</span>
            ) : (
              <div className="flex flex-wrap gap-1">
                {activePolicies.map((id) => (
                  <span
                    key={id}
                    className={`text-xs px-2 py-0.5 rounded-full font-mono font-semibold ${policyBadge(id)}`}
                  >
                    {id}
                  </span>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
