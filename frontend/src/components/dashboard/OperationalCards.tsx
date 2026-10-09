import React from 'react';
import {
  Satellite,
  DownloadCloud,
  ShieldCheck,
  Zap,
  TrendingUp,
} from 'lucide-react';
import type { ScheduleRunResponse } from '../../types/api';

interface OperationalCardsProps {
  activeRun: ScheduleRunResponse | null;
  baselineRun?: ScheduleRunResponse | null;
}

export const OperationalCards: React.FC<OperationalCardsProps> = ({
  activeRun,
  baselineRun,
}) => {
  if (!activeRun) return null;

  const m = activeRun.metrics;
  const isOptimal = activeRun.algorithm === 'cp_sat_optimizer';

  // Calculate throughput improvement over baseline if available
  const throughputGainPercent =
    baselineRun && baselineRun.metrics.total_data_downlinked_gb > 0
      ? (
          ((m.total_data_downlinked_gb - baselineRun.metrics.total_data_downlinked_gb) /
            baselineRun.metrics.total_data_downlinked_gb) *
          100
        ).toFixed(1)
      : null;

  // Average station utilization
  const stationUtils = Object.values(m.ground_station_utilization || {});
  const avgUtilization =
    stationUtils.length > 0
      ? (stationUtils.reduce((a, b) => a + b, 0) / stationUtils.length).toFixed(1)
      : '0.0';

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* 1. Scheduled Passes Card */}
      <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 backdrop-blur-sm relative overflow-hidden group hover:border-slate-700 transition">
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Pass Allocation
          </span>
          <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
            <Satellite className="w-4 h-4" />
          </div>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold tracking-tight text-slate-100">
            {m.scheduled_passes_count}
          </span>
          <span className="text-xs text-slate-400 font-mono">
            / {m.total_passes} opportunities
          </span>
        </div>
        <div className="mt-3 flex items-center justify-between text-xs">
          <span className="text-slate-400">Success Rate</span>
          <span className="font-semibold font-mono text-cyan-400">
            {m.scheduled_percentage.toFixed(1)}%
          </span>
        </div>
        <div className="w-full bg-slate-800 rounded-full h-1.5 mt-1.5 overflow-hidden">
          <div
            className="bg-cyan-500 h-1.5 rounded-full transition-all duration-500"
            style={{ width: `${Math.min(100, m.scheduled_percentage)}%` }}
          />
        </div>
      </div>

      {/* 2. Downlinked Data Volume */}
      <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 backdrop-blur-sm relative overflow-hidden group hover:border-slate-700 transition">
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Data Downlinked
          </span>
          <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            <DownloadCloud className="w-4 h-4" />
          </div>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold tracking-tight text-slate-100">
            {m.total_data_downlinked_gb.toFixed(1)}
          </span>
          <span className="text-xs text-slate-400 font-mono">
            GB / {m.total_pending_data_gb.toFixed(1)} GB
          </span>
        </div>
        <div className="mt-3 flex items-center justify-between text-xs">
          <span className="text-slate-400">Throughput Capture</span>
          {throughputGainPercent && Number(throughputGainPercent) > 0 ? (
            <span className="inline-flex items-center gap-0.5 text-emerald-400 font-semibold font-mono">
              <TrendingUp className="w-3 h-3" />+{throughputGainPercent}% vs FCFS
            </span>
          ) : (
            <span className="font-semibold font-mono text-indigo-300">
              {((m.total_data_downlinked_gb / (m.total_pending_data_gb || 1)) * 100).toFixed(1)}%
            </span>
          )}
        </div>
        <div className="w-full bg-slate-800 rounded-full h-1.5 mt-1.5 overflow-hidden">
          <div
            className="bg-indigo-500 h-1.5 rounded-full transition-all duration-500"
            style={{
              width: `${Math.min(
                100,
                (m.total_data_downlinked_gb / (m.total_pending_data_gb || 1)) * 100
              )}%`,
            }}
          />
        </div>
      </div>

      {/* 3. Priority Satisfaction Rate */}
      <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 backdrop-blur-sm relative overflow-hidden group hover:border-slate-700 transition">
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Critical Priority (P1)
          </span>
          <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <ShieldCheck className="w-4 h-4" />
          </div>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold tracking-tight text-slate-100">
            {m.priority_satisfaction_rate.toFixed(1)}%
          </span>
          <span className="text-xs text-slate-400 font-mono">satisfied</span>
        </div>
        <div className="mt-3 flex items-center justify-between text-xs">
          <span className="text-slate-400">P1 Passes Served</span>
          <span className="font-semibold font-mono text-emerald-400">
            {m.priority_breakdown['1'] || 0} Critical
          </span>
        </div>
        <div className="w-full bg-slate-800 rounded-full h-1.5 mt-1.5 overflow-hidden">
          <div
            className="bg-emerald-500 h-1.5 rounded-full transition-all duration-500"
            style={{ width: `${Math.min(100, m.priority_satisfaction_rate)}%` }}
          />
        </div>
      </div>

      {/* 4. Objective Score & Solver Status */}
      <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 backdrop-blur-sm relative overflow-hidden group hover:border-slate-700 transition">
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Objective Score (w × GB)
          </span>
          <div className="p-2 rounded-lg bg-purple-500/10 text-purple-400 border border-purple-500/20">
            <Zap className="w-4 h-4" />
          </div>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold tracking-tight text-purple-200">
            {m.objective_value.toFixed(1)}
          </span>
          <span className="text-[11px] font-mono px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">
            {activeRun.solver_status_detail || (isOptimal ? 'OPTIMAL' : 'FEASIBLE')}
          </span>
        </div>
        <div className="mt-3 flex items-center justify-between text-xs">
          <span className="text-slate-400">Station Fleet Util.</span>
          <span className="font-semibold font-mono text-purple-300">
            {avgUtilization}%
          </span>
        </div>
        <div className="w-full bg-slate-800 rounded-full h-1.5 mt-1.5 overflow-hidden">
          <div
            className="bg-purple-500 h-1.5 rounded-full transition-all duration-500"
            style={{ width: `${Math.min(100, Number(avgUtilization))}%` }}
          />
        </div>
      </div>
    </div>
  );
};
