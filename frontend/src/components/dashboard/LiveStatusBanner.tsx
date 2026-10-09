import React from 'react';
import { ShieldAlert, Server, Sparkles } from 'lucide-react';

interface LiveStatusBannerProps {
  isBackendConnected: boolean;
  isMock: boolean;
  onRetryConnection: () => void;
}

export const LiveStatusBanner: React.FC<LiveStatusBannerProps> = ({
  isBackendConnected,
  isMock,
  onRetryConnection,
}) => {
  if (isBackendConnected && !isMock) {
    return (
      <div className="flex items-center justify-between gap-3 p-3 px-4 rounded-xl bg-emerald-950/30 border border-emerald-500/30 text-emerald-200 text-xs">
        <div className="flex items-center gap-2">
          <Server className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>
            <strong className="text-emerald-100 font-semibold">Live Backend Mode:</strong> Connected to FastAPI backend service. Solver requests run live OR-Tools CP-SAT & FCFS scheduling algorithms.
          </span>
        </div>
        <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono text-[10px] border border-emerald-500/40 shrink-0">
          REAL-TIME PERSISTENCE
        </span>
      </div>
    );
  }

  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 px-4 rounded-xl bg-amber-950/30 border border-amber-500/30 text-amber-200 text-xs">
      <div className="flex items-start sm:items-center gap-2.5">
        <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0 mt-0.5 sm:mt-0" />
        <div>
          <span className="font-semibold text-amber-100">Simulated / Demonstration Mode:</span>{' '}
          <span className="text-amber-300/90">
            Backend is offline or unverified. Displaying calibrated benchmark metrics based on the OrbitOpt CP-SAT formulation. Metrics are clearly marked as simulated.
          </span>
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0 self-end sm:self-auto">
        <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-mono text-[10px] border border-amber-500/40">
          DEMO BENCHMARK DATA
        </span>
        <button
          onClick={onRetryConnection}
          className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-slate-900 hover:bg-slate-800 text-amber-300 text-[11px] border border-amber-500/30 transition"
        >
          <Sparkles className="w-3 h-3 text-amber-400" />
          Test Backend
        </button>
      </div>
    </div>
  );
};
