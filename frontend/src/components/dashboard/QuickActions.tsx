import React from 'react';
import { Play, Sliders, Cpu, Scale } from 'lucide-react';

interface QuickActionsProps {
  onRunOptimizer: () => void;
  onRunBaseline: () => void;
  onRunComparison: () => void;
  isLoading: boolean;
  setupTimeSeconds: number;
  onChangeSetupTime: (val: number) => void;
  timeLimitSeconds: number;
  onChangeTimeLimit: (val: number) => void;
}

export const QuickActions: React.FC<QuickActionsProps> = ({
  onRunOptimizer,
  onRunBaseline,
  onRunComparison,
  isLoading,
  setupTimeSeconds,
  onChangeSetupTime,
  timeLimitSeconds,
  onChangeTimeLimit,
}) => {
  return (
    <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800 backdrop-blur-sm">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        {/* Left: Solver Parameter Controls */}
        <div className="flex flex-wrap items-center gap-4 text-xs">
          <div className="flex items-center gap-1.5 text-slate-300 font-semibold uppercase tracking-wider">
            <Sliders className="w-3.5 h-3.5 text-cyan-400" />
            <span>Solver Constraints</span>
          </div>

          <div className="flex items-center gap-2 bg-slate-950/80 px-3 py-1.5 rounded-lg border border-slate-800">
            <label htmlFor="setup-time" className="text-slate-400">Antenna Slew Setup:</label>
            <input
              id="setup-time"
              type="number"
              min={0}
              max={600}
              step={10}
              value={setupTimeSeconds}
              onChange={(e) => onChangeSetupTime(Number(e.target.value) || 0)}
              className="w-14 bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5 text-right font-mono text-cyan-300 focus:outline-none focus:border-cyan-500"
            />
            <span className="text-slate-500">sec</span>
          </div>

          <div className="flex items-center gap-2 bg-slate-950/80 px-3 py-1.5 rounded-lg border border-slate-800">
            <label htmlFor="time-limit" className="text-slate-400">Optimizer Time Limit:</label>
            <input
              id="time-limit"
              type="number"
              min={1}
              max={120}
              value={timeLimitSeconds}
              onChange={(e) => onChangeTimeLimit(Number(e.target.value) || 1)}
              className="w-12 bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5 text-right font-mono text-purple-300 focus:outline-none focus:border-purple-500"
            />
            <span className="text-slate-500">sec</span>
          </div>
        </div>

        {/* Right: Trigger Action Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Baseline FCFS */}
          <button
            onClick={onRunBaseline}
            disabled={isLoading}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition disabled:opacity-50"
          >
            <Play className="w-3.5 h-3.5 text-amber-400" />
            Run Baseline (FCFS)
          </button>

          {/* Head-to-Head Comparison */}
          <button
            onClick={onRunComparison}
            disabled={isLoading}
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-indigo-950/80 hover:bg-indigo-900 text-indigo-200 text-xs font-medium border border-indigo-700/60 transition disabled:opacity-50"
          >
            <Scale className="w-3.5 h-3.5 text-indigo-400" />
            Run Comparison (FCFS vs CP-SAT)
          </button>

          {/* CP-SAT Optimizer */}
          <button
            onClick={onRunOptimizer}
            disabled={isLoading}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white text-xs font-semibold shadow-md shadow-cyan-600/20 transition disabled:opacity-50"
          >
            <Cpu className="w-4 h-4 text-cyan-200" />
            Solve with CP-SAT
          </button>
        </div>
      </div>
    </div>
  );
};
