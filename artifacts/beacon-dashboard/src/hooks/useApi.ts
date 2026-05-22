import { useState, useEffect, useCallback } from "react";

// ADR: 12 s poll cadence — rationale:
// The APScheduler live_telemetry job emits a fresh DB row every 12 s.
// Polling at the same rate ensures every cycle returns a newly-written record
// rather than stale data from the previous minute.
export const POLL_INTERVAL_MS = 12000;

export interface ApiState<T = any> {
  data: T | null;
  error: string | null;
  loading: boolean;
  lastRefreshed: Date | null;
  interval: number;
}

export function useApi<T = any>(path: string, interval = POLL_INTERVAL_MS): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const resp = await fetch(`/api${path}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const json = await resp.json();
      setData(json);
      setError(null);
      setLastRefreshed(new Date());
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    fetchData();
    const timer = setInterval(fetchData, interval);
    return () => clearInterval(timer);
  }, [fetchData, interval]);

  return { data, error, loading, lastRefreshed, interval };
}
