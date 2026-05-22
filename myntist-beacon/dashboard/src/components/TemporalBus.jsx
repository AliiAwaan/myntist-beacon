import React from "react";

function fmt(val, decimals = 4) {
  if (val === null || val === undefined) return "—";
  return Number(val).toFixed(decimals);
}

export default function TemporalBus({ data, loading, error }) {
  const admitted = data?.admitted ?? null;
  const policyIds = data?.active_policy_ids ?? [];

  return (
    <div className="bg-[#1F3864] rounded-xl p-5 border border-navy-700">
      <h2 className="text-sm font-semibold uppercase tracking-widest text-gray-400 mb-4">
        Temporal Bus
      </h2>

      {error && (
        <div className="text-xs text-red-400 bg-red-900 bg-opacity-30 rounded px-2 py-1 mb-3">
          {error}
        </div>
      )}

      {/* Admission badge */}
      <div className="flex items-center gap-3 mb-4">
        {loading && admitted === null ? (
          <span className="text-gray-500 text-xs">…</span>
        ) : admitted === null ? (
          <span className="px-3 py-1 rounded-full text-sm font-semibold uppercase tracking-widest bg-gray-600 text-gray-300">
            Unknown
          </span>
        ) : (
          <span
            className={`px-3 py-1 rounded-full text-sm font-semibold uppercase tracking-widest ${
              admitted ? "bg-green-500 text-white" : "bg-red-600 text-white"
            }`}
          >
            {admitted ? "Admitted" : "Denied"}
          </span>
        )}
        <span className="text-xs text-gray-500 uppercase tracking-widest">IAM Gate</span>
      </div>

      {/* Metric grid */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        {[
          { label: "S", value: fmt(data?.S) },
          { label: "Q", value: fmt(data?.Q) },
          { label: "tau (τ)", value: fmt(data?.tau) },
          { label: "D", value: fmt(data?.D) },
          { label: "Ttau", value: fmt(data?.Ttau) },
          { label: "S × D", value: fmt(data?.S_times_D) },
        ].map(({ label, value }) => (
          <div key={label} className="bg-[#0f1c38] rounded-lg p-3">
            <div className="text-xs text-gray-500 uppercase tracking-widest mb-1">
              {label}
            </div>
            <div className="font-mono text-sm text-blue-300">
              {loading && value === "—" ? "…" : value}
            </div>
          </div>
        ))}
      </div>

      {/* Active policy IDs */}
      <div>
        <div className="text-xs text-gray-500 uppercase tracking-widest mb-2">
          Active Policies
        </div>
        {loading && policyIds.length === 0 ? (
          <span className="text-gray-500 text-xs">…</span>
        ) : policyIds.length === 0 ? (
          <span className="text-xs text-gray-600 italic">none</span>
        ) : (
          <div className="flex flex-wrap gap-2">
            {policyIds.map((id) => (
              <span
                key={id}
                className="bg-[#0f1c38] text-blue-300 font-mono text-xs px-2 py-0.5 rounded"
              >
                {id}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
