import React from "react";

function stateColor(S: number) {
  if (S >= 0.85) return "text-green-400";
  if (S >= 0.70) return "text-amber-400";
  return "text-red-400";
}

function eventBadge(eventType: string) {
  if (!eventType) return "bg-gray-800 text-gray-400";
  if (eventType.includes("token")) return "bg-blue-900 text-blue-300";
  if (eventType.includes("role")) return "bg-purple-900 text-purple-300";
  if (eventType.includes("revoc")) return "bg-red-900 text-red-300";
  return "bg-gray-800 text-gray-400";
}

function formatTs(ts: string) {
  if (!ts) return "—";
  try {
    return new Date(ts).toLocaleTimeString();
  } catch {
    return ts;
  }
}

interface Props {
  records: any[];
  loading: boolean;
}

export default function AuditLog({ records, loading }: Props) {
  const auditEntries = (records || []).filter((r) => r.identity_id).slice(0, 10);

  return (
    <div className="bg-[#1F3864] rounded-xl p-5 border border-[#0f1c38]">
      <h2 className="text-sm font-semibold uppercase tracking-widest text-gray-400 mb-4">
        Audit Log
      </h2>

      {loading && auditEntries.length === 0 ? (
        <div className="text-center text-gray-500 py-8 text-sm">Loading...</div>
      ) : auditEntries.length === 0 ? (
        <div className="text-center text-gray-600 py-8 text-sm">No audit entries yet</div>
      ) : (
        <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
          {auditEntries.map((entry: any, i: number) => (
            <div key={entry.id || i} className="bg-[#0f1c38] rounded-lg p-3 text-xs">
              <div className="flex items-center justify-between gap-2 mb-1">
                <span className="font-mono text-gray-500">{formatTs(entry.recorded_at)}</span>
                <span className={`px-1.5 py-0.5 rounded text-xs font-semibold ${eventBadge(entry.event_type)}`}>
                  {entry.event_type || "telemetry"}
                </span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-blue-300 truncate max-w-[100px]">{entry.identity_id}</span>
                <span className={`font-mono font-bold ${stateColor(entry.S)}`}>
                  {entry.S?.toFixed(4) ?? "—"}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
