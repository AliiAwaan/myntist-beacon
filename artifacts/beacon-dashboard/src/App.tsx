import React, { useState, useEffect, useRef } from "react";
// ADR: 12 s poll cadence — rationale:
// The spec minimum for role-decay heartbeats is 60 s, but the APScheduler
// live_telemetry job emits a fresh DB row every 12 s (matching POLL_INTERVAL_MS).
// Polling at that same rate ensures every dashboard refresh cycle returns a
// newly-written record rather than stale data from the previous minute.
// Increasing this above 12 s would cause apparent field-state lag in the
// Beacon Status header and TemporalBus panel.
import { useApi, POLL_INTERVAL_MS } from "./hooks/useApi";
import BeaconStatus from "./components/BeaconStatus";
import SurvivabilityGauge from "./components/SurvivabilityGauge";
import MetricsMatrix from "./components/MetricsMatrix";
import DNSStatus from "./components/DNSStatus";
import FeedHealth from "./components/FeedHealth";
import AuditLog from "./components/AuditLog";
import FloatYield from "./components/FloatYield";
import IntelligenceRate from "./components/IntelligenceRate";
import LiquiditySignal from "./components/LiquiditySignal";
import CoherenceSignal from "./components/CoherenceSignal";
import ReinvestmentRate from "./components/ReinvestmentRate";
// TemporalBus displays the real-time IAM policy gate state (tau, D, Ttau, S×D,
// admitted/blocked status, active policy IDs) sourced from /api/telemetry/temporal.
import TemporalBus from "./components/TemporalBus";
import PolicyAlertBanner from "./components/PolicyAlertBanner";
import PolicyHistory, { PolicyEvent } from "./components/PolicyHistory";
import { POLICY_META } from "./policyMeta";

function useLiveClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);
  return now;
}

export default function App() {
  const telemetry = useApi("/telemetry/latest");
  const historical = useApi("/telemetry/historical");
  const health = useApi("/health", 15000);
  const finance = useApi("/telemetry/finance");
  const temporal = useApi("/telemetry/temporal");
  const clock = useLiveClock();

  const [policyEvents, setPolicyEvents] = useState<PolicyEvent[]>([]);
  const prevActivePoliciesRef = useRef<Set<string>>(new Set());
  const eventCounterRef = useRef(0);

  useEffect(() => {
    if (!temporal.data) return;
    const currentIds: string[] = temporal.data.active_policy_ids ?? [];
    const currentSet = new Set(currentIds);
    const prevSet = prevActivePoliciesRef.current;

    const newlyTripped = currentIds.filter((id) => !prevSet.has(id));
    const nowCleared = Array.from(prevSet).filter((id) => !currentSet.has(id));

    if (newlyTripped.length > 0 || nowCleared.length > 0) {
      const now = new Date();

      setPolicyEvents((prev) => {
        let updated = [...prev];

        nowCleared.forEach((id) => {
          let idx = -1;
          for (let i = updated.length - 1; i >= 0; i--) {
            if (updated[i].policyId === id && updated[i].clearedAt === null) {
              idx = i;
              break;
            }
          }
          if (idx !== -1) {
            updated[idx] = { ...updated[idx], clearedAt: now };
          }
        });

        newlyTripped.forEach((id) => {
          const meta = POLICY_META[id] ?? { name: id, action: "block" };
          eventCounterRef.current += 1;
          updated.unshift({
            id: `${id}-${eventCounterRef.current}`,
            policyId: id,
            policyName: meta.name,
            action: meta.action,
            trippedAt: now,
            clearedAt: null,
          });
        });

        return updated.slice(0, 50);
      });
    }

    prevActivePoliciesRef.current = currentSet;
  }, [temporal.data]);

  const latest = telemetry.data;
  const records = historical.data?.records || [];
  const apiVersion = health.data?.version ?? "2.0.0";

  const clockStr = clock.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

  const secondsUntilRefresh = telemetry.lastRefreshed
    ? Math.max(
        0,
        Math.ceil(
          (telemetry.interval - (clock.getTime() - telemetry.lastRefreshed.getTime())) / 1000
        )
      )
    : null;

  return (
    <div className="min-h-screen bg-[#0f1c38] text-gray-100">
      <BeaconStatus
        latest={latest}
        loading={telemetry.loading}
        error={telemetry.error}
        secondsUntilRefresh={secondsUntilRefresh}
      />

      <PolicyAlertBanner data={temporal.data} loading={temporal.loading} />

      <div className="max-w-screen-2xl mx-auto p-4 space-y-4">
        {/* Phase 1 Row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-1">
            <SurvivabilityGauge latest={latest} loading={telemetry.loading} />
          </div>
          <div className="lg:col-span-2">
            <MetricsMatrix records={records} loading={historical.loading} />
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <DNSStatus health={health.data} loading={health.loading} error={health.error} />
          <FeedHealth latest={latest} loading={telemetry.loading} />
          <AuditLog records={records} loading={historical.loading} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <PolicyHistory events={policyEvents} />
        </div>

        {/* Phase 2 Row */}
        <div className="flex items-center gap-3 mt-6">
          <div className="h-px flex-1 bg-gray-700" />
          <span className="text-xs font-semibold uppercase tracking-widest text-indigo-400 px-2">
            Phase 2 · Financial Telemetry
          </span>
          <div className="h-px flex-1 bg-gray-700" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <FloatYield
            data={finance.data}
            loading={finance.loading}
            error={finance.error}
          />
          <IntelligenceRate
            data={finance.data}
            loading={finance.loading}
            error={finance.error}
          />
          <LiquiditySignal
            data={temporal.data}
            loading={temporal.loading}
            error={temporal.error}
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <CoherenceSignal
            data={temporal.data}
            loading={temporal.loading}
            error={temporal.error}
          />
          <ReinvestmentRate
            finance={finance.data}
            temporal={temporal.data}
            loading={finance.loading || temporal.loading}
            error={finance.error || temporal.error}
          />
        </div>

        <TemporalBus />
      </div>

      <div className="text-center py-4 text-xs text-gray-600 font-mono">
        API v{apiVersion} &middot; {clockStr}
      </div>
    </div>
  );
}
