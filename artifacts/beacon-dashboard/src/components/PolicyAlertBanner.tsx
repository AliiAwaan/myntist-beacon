import React, { useState, useEffect, useRef, useCallback } from "react";
import { POLICY_META } from "../policyMeta";

interface Props {
  data: any;
  loading: boolean;
}

function getActionBadgeClass(action: string): string {
  if (action === "block") return "bg-red-900/60 text-red-300 border border-red-700";
  if (action === "throttle") return "bg-yellow-900/60 text-yellow-300 border border-yellow-700";
  return "bg-gray-800 text-gray-300 border border-gray-600";
}

type WindowWithWebkitAudio = Window & { webkitAudioContext?: typeof AudioContext };

function playAlertBeep(isHardBlock: boolean) {
  try {
    const AudioCtx = window.AudioContext || (window as WindowWithWebkitAudio).webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const oscillator = ctx.createOscillator();
    const gainNode = ctx.createGain();

    oscillator.connect(gainNode);
    gainNode.connect(ctx.destination);

    oscillator.type = "sine";
    oscillator.frequency.setValueAtTime(isHardBlock ? 880 : 660, ctx.currentTime);
    oscillator.frequency.exponentialRampToValueAtTime(isHardBlock ? 440 : 550, ctx.currentTime + 0.3);

    gainNode.gain.setValueAtTime(0.4, ctx.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);

    oscillator.start(ctx.currentTime);
    oscillator.stop(ctx.currentTime + 0.4);

    oscillator.onended = () => ctx.close();
  } catch {
  }
}

const MUTE_KEY = "policy_alert_muted";

export default function PolicyAlertBanner({ data, loading }: Props) {
  const admitted: boolean = data?.admitted !== false;
  const activePolicyIds: string[] = data?.active_policy_ids ?? [];
  const hasAlert = !admitted;

  const [dismissed, setDismissed] = useState(false);
  const [flashing, setFlashing] = useState(false);
  const [muted, setMuted] = useState<boolean>(() => {
    try {
      return localStorage.getItem(MUTE_KEY) === "true";
    } catch {
      return false;
    }
  });

  const prevHasAlertRef = useRef<boolean | null>(null);
  const isFirstRenderRef = useRef(true);

  const isHardBlock = activePolicyIds.length === 0
    ? true
    : activePolicyIds.some((id) => POLICY_META[id]?.action === "block");

  const triggerAlertEffects = useCallback(() => {
    if (!muted) {
      playAlertBeep(isHardBlock);
    }
    setFlashing(true);
    const timeout = setTimeout(() => setFlashing(false), 600);
    return timeout;
  }, [muted, isHardBlock]);

  useEffect(() => {
    if (hasAlert) {
      setDismissed(false);
    }
  }, [hasAlert]);

  useEffect(() => {
    if (loading) return;

    if (isFirstRenderRef.current) {
      isFirstRenderRef.current = false;
      prevHasAlertRef.current = hasAlert;
      return;
    }

    const prev = prevHasAlertRef.current;
    prevHasAlertRef.current = hasAlert;

    if (!prev && hasAlert) {
      const timeout = triggerAlertEffects();
      return () => clearTimeout(timeout);
    }
    return undefined;
  }, [hasAlert, loading, triggerAlertEffects]);

  const toggleMute = () => {
    setMuted((m) => {
      const next = !m;
      try {
        localStorage.setItem(MUTE_KEY, String(next));
      } catch {
      }
      return next;
    });
  };

  if (!hasAlert || dismissed) return null;

  return (
    <>
      {flashing && (
        <div
          className="fixed inset-0 pointer-events-none z-50 animate-flash-overlay"
          style={{
            background: isHardBlock
              ? "rgba(220, 38, 38, 0.25)"
              : "rgba(234, 179, 8, 0.2)",
            animation: "flashOverlay 0.6s ease-out forwards",
          }}
        />
      )}

      <style>{`
        @keyframes flashOverlay {
          0%   { opacity: 1; }
          100% { opacity: 0; }
        }
        @keyframes flashBorder {
          0%, 100% { box-shadow: none; }
          25%  { box-shadow: 0 0 0 3px rgba(220,38,38,0.8); }
          75%  { box-shadow: 0 0 0 3px rgba(220,38,38,0.4); }
        }
        .flash-border {
          animation: flashBorder 0.6s ease-out;
        }
      `}</style>

      <div
        className={`relative mx-auto max-w-screen-2xl px-4 pt-4`}
        role="alert"
        aria-live="assertive"
      >
        <div
          className={`rounded-xl border px-5 py-4 flex items-start gap-4 shadow-lg ${
            isHardBlock
              ? "bg-red-950/60 border-red-600"
              : "bg-yellow-950/60 border-yellow-600"
          } ${flashing ? "flash-border" : ""}`}
        >
          <div className="flex-shrink-0 mt-0.5">
            <span className={`text-xl ${isHardBlock ? "text-red-400" : "text-yellow-400"}`}>
              {isHardBlock ? "⛔" : "⚠"}
            </span>
          </div>

          <div className="flex-1 min-w-0">
            <p className={`text-sm font-bold uppercase tracking-wider mb-2 ${isHardBlock ? "text-red-300" : "text-yellow-300"}`}>
              {isHardBlock ? "Token Issuance Blocked" : "Traffic Throttled"} — Policy Alert
            </p>

            <div className="flex flex-wrap gap-3">
              {activePolicyIds.length === 0 ? (
                <div className="flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs bg-red-900/60 text-red-300 border border-red-700">
                  <span className="font-semibold">Admission denied — no active policy IDs reported. Check field state.</span>
                </div>
              ) : (
                activePolicyIds.map((id) => {
                  const meta = POLICY_META[id];
                  const badgeClass = meta ? getActionBadgeClass(meta.action) : "bg-gray-800 text-gray-300 border border-gray-600";
                  return (
                    <div
                      key={id}
                      className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs ${badgeClass}`}
                    >
                      <span className="font-mono font-bold">{id}</span>
                      {meta && (
                        <>
                          <span className="text-gray-400 hidden sm:inline">·</span>
                          <span className="hidden sm:inline">{meta.name}</span>
                          <span className="text-gray-400">·</span>
                          <span className={`font-semibold ${meta.color}`}>{meta.actionLabel}</span>
                        </>
                      )}
                    </div>
                  );
                })
              )}
            </div>

            <p className="mt-2 text-xs text-gray-400">
              Admitted: <span className="font-mono text-red-400">false</span> — review field state to resolve.
              This banner clears automatically when policies deactivate.
            </p>
          </div>

          <div className="flex items-center gap-2 flex-shrink-0 ml-2">
            <button
              onClick={toggleMute}
              className="text-gray-500 hover:text-gray-200 transition-colors"
              aria-label={muted ? "Unmute alert sound" : "Mute alert sound"}
              title={muted ? "Unmute alert sound" : "Mute alert sound"}
            >
              {muted ? (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" />
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M15.536 8.464a5 5 0 010 7.072M12 6v12m0 0l-4-4m4 4l4-4M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                </svg>
              )}
            </button>

            <button
              onClick={() => setDismissed(true)}
              className="text-gray-500 hover:text-gray-200 transition-colors"
              aria-label="Dismiss alert"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
