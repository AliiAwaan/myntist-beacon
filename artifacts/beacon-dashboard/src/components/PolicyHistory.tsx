import React from "react";

export interface PolicyEvent {
  id: string;
  policyId: string;
  policyName: string;
  action: string;
  trippedAt: Date;
  clearedAt: Date | null;
}

interface Props {
  events: PolicyEvent[];
}

function formatTime(d: Date): string {
  return d.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatDuration(start: Date, end: Date): string {
  const secs = Math.round((end.getTime() - start.getTime()) / 1000);
  if (secs < 60) return `${secs}s`;
  const mins = Math.floor(secs / 60);
  const rem = secs % 60;
  return rem > 0 ? `${mins}m ${rem}s` : `${mins}m`;
}

function rowClasses(action: string, cleared: boolean): string {
  if (cleared) return "bg-[#0f1c38] opacity-70";
  if (action === "block") return "bg-red-950/40 border border-red-800/50";
  if (action === "throttle") return "bg-yellow-950/40 border border-yellow-800/50";
  return "bg-[#0f1c38]";
}

function idBadgeClasses(action: string): string {
  if (action === "block") return "bg-red-900/60 text-red-300 border border-red-700";
  if (action === "throttle") return "bg-yellow-900/60 text-yellow-300 border border-yellow-700";
  return "bg-gray-800 text-gray-300 border border-gray-600";
}

function statusDot(action: string, cleared: boolean): React.ReactNode {
  if (cleared) {
    return <span className="inline-block w-2 h-2 rounded-full bg-green-500 flex-shrink-0" title="Cleared" />;
  }
  if (action === "block") {
    return <span className="inline-block w-2 h-2 rounded-full bg-red-500 animate-pulse flex-shrink-0" title="Active block" />;
  }
  return <span className="inline-block w-2 h-2 rounded-full bg-yellow-500 animate-pulse flex-shrink-0" title="Active throttle" />;
}

export default function PolicyHistory({ events }: Props) {
  return (
    <div className="bg-[#1F3864] rounded-xl p-5 border border-[#0f1c38]">
      <h2 className="text-sm font-semibold uppercase tracking-widest text-gray-400 mb-4">
        Policy History
      </h2>

      {events.length === 0 ? (
        <div className="text-center text-gray-600 py-8 text-sm">
          No policy events this session
        </div>
      ) : (
        <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
          {events.map((ev) => {
            const cleared = ev.clearedAt !== null;
            return (
              <div
                key={ev.id}
                className={`rounded-lg p-3 text-xs ${rowClasses(ev.action, cleared)}`}
              >
                <div className="flex items-center gap-2 mb-1">
                  {statusDot(ev.action, cleared)}
                  <span className={`font-mono font-bold px-1.5 py-0.5 rounded text-xs ${idBadgeClasses(ev.action)}`}>
                    {ev.policyId}
                  </span>
                  <span className="text-gray-300 truncate">{ev.policyName}</span>
                </div>
                <div className="flex items-center justify-between gap-2 mt-1 pl-4">
                  <span className="font-mono text-gray-400">
                    {formatTime(ev.trippedAt)}
                    {cleared && ev.clearedAt
                      ? ` → ${formatTime(ev.clearedAt)}`
                      : " → active"}
                  </span>
                  {cleared && ev.clearedAt && (
                    <span className="text-gray-500 font-mono">
                      {formatDuration(ev.trippedAt, ev.clearedAt)}
                    </span>
                  )}
                  {!cleared && (
                    <span className={`font-semibold ${ev.action === "block" ? "text-red-400" : "text-yellow-400"}`}>
                      {ev.action === "block" ? "BLOCKED" : "THROTTLED"}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
