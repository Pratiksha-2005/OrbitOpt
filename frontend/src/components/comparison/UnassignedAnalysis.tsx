import React from 'react';
import { CheckCircle2, XCircle, ShieldCheck } from 'lucide-react';
import type { ScheduleRunResponse } from '../../types/api';

interface UnassignedAnalysisProps {
  baselineRun: ScheduleRunResponse;
  optimizedRun: ScheduleRunResponse;
}

export const UnassignedAnalysis: React.FC<UnassignedAnalysisProps> = ({
  baselineRun,
  optimizedRun,
}) => {
  const fcfsUnassigned = baselineRun.unassigned_passes;
  const cpsatUnassigned = optimizedRun.unassigned_passes;

  // Passes dropped in FCFS but successfully salvaged by CP-SAT!
  const salvagedPasses = fcfsUnassigned.filter(
    (fcfsPass) =>
      !cpsatUnassigned.some((optPass) => optPass.pass_id === fcfsPass.pass_id)
  );

  return (
    <div className="space-y-4">
      {/* Salvaged Passes Highlight Card */}
      {salvagedPasses.length > 0 && (
        <div className="p-4 rounded-xl bg-emerald-950/30 border border-emerald-500/40 backdrop-blur-sm">
          <div className="flex items-center gap-2 mb-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <h4 className="text-xs font-bold text-emerald-200 uppercase tracking-wider">
              Optimization Breakthrough: {salvagedPasses.length} Conflict{salvagedPasses.length === 1 ? '' : 's'} Resolved by CP-SAT
            </h4>
          </div>
          <p className="text-xs text-slate-300 leading-relaxed mb-3">
            The CP-SAT solver restructured antenna repointing sequences and solved temporal overlap conflicts, successfully allocating these passes which were dropped by naive FCFS:
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {salvagedPasses.map((p) => (
              <div
                key={p.pass_id}
                className="p-3 rounded-lg bg-slate-900/80 border border-emerald-500/30 text-xs flex items-center justify-between"
              >
                <div>
                  <div className="font-semibold text-slate-100 flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    <span className="font-mono">{p.pass_id}</span>
                  </div>
                  <div className="text-[11px] text-slate-400 mt-0.5">
                    {p.satellite_id} @ {p.ground_station_id} (Priority P{p.priority})
                  </div>
                </div>
                <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono text-[10px] font-semibold">
                  SALVAGED
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Side-by-Side Unassigned Passes Table */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Baseline FCFS Drops */}
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 backdrop-blur-sm">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <XCircle className="w-4 h-4 text-amber-400" />
              <h4 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">
                FCFS Dropped Passes ({fcfsUnassigned.length})
              </h4>
            </div>
            <span className="text-[11px] font-mono text-amber-400">
              {baselineRun.metrics.conflicts_detected} conflicts detected
            </span>
          </div>

          {fcfsUnassigned.length === 0 ? (
            <p className="text-xs text-slate-400 py-4 text-center">
              No passes were dropped in the baseline run.
            </p>
          ) : (
            <div className="space-y-2">
              {fcfsUnassigned.map((p) => (
                <div
                  key={p.pass_id}
                  className="p-3 rounded-lg bg-slate-950/60 border border-slate-800 text-xs"
                >
                  <div className="flex items-center justify-between font-mono mb-1">
                    <span className="font-semibold text-slate-200">{p.pass_id}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300">
                      P{p.priority}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-400 mb-1">
                    {p.satellite_id} · {p.ground_station_id}
                  </div>
                  <div className="text-[11px] text-amber-300/90 font-sans italic bg-amber-950/20 p-1.5 rounded border border-amber-900/30">
                    "{p.reason}"
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* CP-SAT Drops */}
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 backdrop-blur-sm">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <XCircle className="w-4 h-4 text-rose-400" />
              <h4 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">
                CP-SAT Dropped Passes ({cpsatUnassigned.length})
              </h4>
            </div>
            <span className="text-[11px] font-mono text-cyan-400">
              Optimal tradeoff reduction
            </span>
          </div>

          {cpsatUnassigned.length === 0 ? (
            <div className="p-6 text-center">
              <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
              <p className="text-xs font-semibold text-emerald-300">
                100% Conflict Resolution
              </p>
              <p className="text-[11px] text-slate-400 mt-1">
                All pass opportunities successfully scheduled within physical antenna constraints.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {cpsatUnassigned.map((p) => (
                <div
                  key={p.pass_id}
                  className="p-3 rounded-lg bg-slate-950/60 border border-slate-800 text-xs"
                >
                  <div className="flex items-center justify-between font-mono mb-1">
                    <span className="font-semibold text-slate-200">{p.pass_id}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300">
                      P{p.priority}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-400 mb-1">
                    {p.satellite_id} · {p.ground_station_id}
                  </div>
                  <div className="text-[11px] text-rose-300/90 font-sans italic bg-rose-950/20 p-1.5 rounded border border-rose-900/30">
                    "{p.reason}"
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
