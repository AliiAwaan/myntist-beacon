import React from "react";

const FEEDS = [
  { key: "status", name: "status.json", path: "/api/field/v1/status.json" },
  { key: "matrix", name: "matrix.json", path: "/api/field/v1/matrix.json" },
  { key: "benchmarks", name: "benchmarks.json", path: "/api/field/v1/benchmarks.json" },
  { key: "pulse", name: "pulse.json", path: "/api/field/v1/pulse.json" },
];

const STALE_THRESHOLD_MS = 15 * 60 * 1000;

function isFresh(timestamp: string | null) {
  if (!timestamp) return false;
  try {
    const ts = new Date(timestamp).getTime();
    return Date.now() - ts < STALE_THRESHOLD_MS;
  } catch {
    return false;
  }
}

function formatAge(timestamp: string | null) {
  if (!timestamp) return "never";
  try {
    const diffMs = Date.now() - new Date(timestamp).getTime();
    const mins = Math.floor(diffMs / 60000);
    if (mins < 1) return "< 1m ago";
    if (mins < 60) return `${mins}m ago`;
    return `${Math.floor(mins / 60)}h ago`;
  } catch {
    return "—";
  }
}

interface Props {
  latest: any;
  loading: boolean;
}

export default function FeedHealth({ latest, loading }: Props) {
  const timestamp: string | null = latest?.timestamp ?? null;

  return (
    <div className="bg-[#1F3864] rounded-xl p-5 border border-[#0f1c38]">
      <h2 className="text-sm font-semibold uppercase tracking-widest text-gray-400 mb-4">
        Feed Health
      </h2>

      <div className="space-y-3">
        {FEEDS.map((feed) => {
          const fresh = isFresh(timestamp);
          return (
            <div key={feed.key} className="bg-[#0f1c38] rounded-lg p-3 flex items-center justify-between">
              <div>
                <div className="font-mono text-xs text-blue-300">{feed.name}</div>
                <div className="text-xs text-gray-500 mt-0.5 truncate max-w-[140px]">{feed.path}</div>
              </div>
              <div className="flex flex-col items-end gap-1">
                {loading ? (
                  <span className="text-gray-500 text-xs">…</span>
                ) : fresh ? (
                  <span className="text-green-400 text-sm font-semibold">FRESH</span>
                ) : (
                  <span className="text-amber-400 text-sm font-semibold">STALE</span>
                )}
                <span className="text-xs text-gray-600">{formatAge(timestamp)}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
