import React from 'react';
import {
  Scale,
  TrendingUp,
  Clock,
  Sparkles,
  Zap,
  ShieldCheck,
  RotateCw,
} from 'lucide-react';
import type { ScheduleRunResponse } from '../../types/api';
import { ComparisonCharts } from './ComparisonCharts';
import { UnassignedAnalysis } from './UnassignedAnalysis';

interface AlgorithmComparisonProps {
  baselineRun: ScheduleRunResponse;
  optimizedRun: ScheduleRunResponse;
  onRerunComparison: () => void;
  isLoading: boolean;
}

export const AlgorithmComparison: React.FC<AlgorithmComparisonProps> = ({
  baselineRun,
  optimizedRun,
  onRerunComparison,
  isLoading,
}) => {
  const b = baselineRun.metrics;
  const o = optimizedRun.metrics;

  // Compute key delta statistics
  const dataDeltaGb = o.total_data_downlinked_gb - b.total_data_downlinked_gb;
  const dataDeltaPct = b.total_data_downlinked_gb > 0
    ? ((dataDeltaGb / b.total_data_downlinked_gb) * 100).toFixed(1)
    : '0';

  const objDelta = o.objective_value - b.objective_value;
  const objDeltaPct = b.objective_value > 0
    ? ((objDelta / b.objective_value) * 100).toFixed(1)
    : '0';

  const p1Delta = o.priority_satisfaction_rate - b.priority_satisfaction_rate;

  return (
    <div className="space-y-6">
      {/* Top Banner & Trigger */}
      <div className="p-5 rounded-2xl bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 border border-indigo-500/30 backdrop-blur-md flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Scale className="w-5 h-5 text-indigo-400" />
            <h3 className="text-base font-bold text-slate-100">
              Algorithmic Benchmark: Baseline (FCFS) vs CP-SAT Optimizer
            </h3>
          </div>
          <p className="text-xs text-slate-300 mt-1 max-w-2xl leading-relaxed">
            Evaluates the mathematical optimization gain achieved by Google OR-Tools CP-SAT solver over standard First-Come-First-Served scheduling under 60-second antenna setup constraints.
          </p>
        </div>

        <button
          onClick={onRerunComparison}
          disabled={isLoading}
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-lg shadow-indigo-600/25 transition disabled:opacity-50 shrink-0 self-start md:self-auto"
        >
          <RotateCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          Re-run Benchmark
        </button>
      </div>

      {/* Delta Performance Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Data Throughput Gain */}
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-slate-400 uppercase">
              Downlink Throughput
            </span>
            <span className="p-1.5 rounded-md bg-emerald-500/10 text-emerald-400">
              <TrendingUp className="w-3.5 h-3.5" />
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-emerald-400 font-mono">
              {dataDeltaGb >= 0 ? `+${dataDeltaGb.toFixed(1)}` : dataDeltaGb.toFixed(1)} GB
            </span>
            <span className="text-xs text-emerald-400 font-semibold font-mono">
              ({dataDeltaGb >= 0 ? `+${dataDeltaPct}` : dataDeltaPct}%)
            </span>
          </div>
          <p className="text-[11px] text-slate-400 mt-2">
            FCFS: {b.total_data_downlinked_gb.toFixed(1)} GB → CP-SAT: {o.total_data_downlinked_gb.toFixed(1)} GB
          </p>
        </div>

        {/* Global Objective Score */}
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-slate-400 uppercase">
              Objective Value Gain
            </span>
            <span className="p-1.5 rounded-md bg-purple-500/10 text-purple-400">
              <Zap className="w-3.5 h-3.5" />
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-purple-300 font-mono">
              {objDelta >= 0 ? `+${objDelta.toFixed(1)}` : objDelta.toFixed(1)}
            </span>
            <span className="text-xs text-purple-400 font-semibold font-mono">
              ({objDelta >= 0 ? `+${objDeltaPct}` : objDeltaPct}%)
            </span>
          </div>
          <p className="text-[11px] text-slate-400 mt-2">
            FCFS: {b.objective_value.toFixed(1)} → CP-SAT: {o.objective_value.toFixed(1)}
          </p>
        </div>

        {/* P1 Satisfaction Improvement */}
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-slate-400 uppercase">
              Critical P1 Serviced
            </span>
            <span className="p-1.5 rounded-md bg-cyan-500/10 text-cyan-400">
              <ShieldCheck className="w-3.5 h-3.5" />
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-cyan-300 font-mono">
              {o.priority_satisfaction_rate.toFixed(1)}%
            </span>
            {p1Delta > 0 && (
              <span className="text-xs text-cyan-400 font-semibold font-mono">
                (+{p1Delta.toFixed(1)}%)
              </span>
            )}
          </div>
          <p className="text-[11px] text-slate-400 mt-2">
            FCFS: {b.priority_satisfaction_rate.toFixed(1)}% ({b.priority_breakdown['1'] || 0} P1 served)
          </p>
        </div>

        {/* Solver Execution Time */}
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-slate-400 uppercase">
              Solver Runtime
            </span>
            <span className="p-1.5 rounded-md bg-slate-700/50 text-slate-300">
              <Clock className="w-3.5 h-3.5" />
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-200 font-mono">
              {optimizedRun.execution_time_ms.toFixed(1)}
            </span>
            <span className="text-xs text-slate-400 font-mono">ms</span>
          </div>
          <p className="text-[11px] text-slate-400 mt-2">
            Fast CP-SAT convergence (Status: <strong className="text-emerald-400">{optimizedRun.solver_status_detail || 'OPTIMAL'}</strong>)
          </p>
        </div>
      </div>

      {/* Mathematical Formulation Explainer */}
      <div className="p-4 rounded-xl bg-slate-950/70 border border-slate-800 text-xs text-slate-300">
        <div className="flex items-center gap-2 font-semibold text-slate-200 mb-1.5">
          <Sparkles className="w-4 h-4 text-cyan-400" />
          <span>Mathematical Formulation (from OrbitOpt API Contract)</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-2">
          <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800 font-mono text-[11px] text-slate-300">
            <span className="text-cyan-400 font-semibold">Objective Function:</span>
            <div className="mt-1 text-slate-200">
              max ∑ (w_p × transferable_data_gb)
            </div>
            <div className="text-[10px] text-slate-500 mt-1">
              Weights: P1=10.0, P2=5.0, P3=2.0, P4=1.0, P5=0.5
            </div>
          </div>

          <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800 font-mono text-[11px] text-slate-300">
            <span className="text-indigo-400 font-semibold">Operational Constraints:</span>
            <div className="mt-1 text-slate-200">
              No overlapping passes on single antenna + Slew setup gap ≥ 60s
            </div>
            <div className="text-[10px] text-slate-500 mt-1">
              Transferable Data = min(pending_data, channel_capacity)
            </div>
          </div>
        </div>
      </div>

      {/* Visual Benchmark Charts */}
      <ComparisonCharts baselineRun={baselineRun} optimizedRun={optimizedRun} />

      {/* Unassigned Drops & Conflict Resolution */}
      <UnassignedAnalysis baselineRun={baselineRun} optimizedRun={optimizedRun} />
    </div>
  );
};
