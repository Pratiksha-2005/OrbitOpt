import React from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
} from 'recharts';
import type { ScheduleRunResponse } from '../../types/api';

interface ComparisonChartsProps {
  baselineRun: ScheduleRunResponse;
  optimizedRun: ScheduleRunResponse;
}

export const ComparisonCharts: React.FC<ComparisonChartsProps> = ({
  baselineRun,
  optimizedRun,
}) => {
  const b = baselineRun.metrics;
  const o = optimizedRun.metrics;

  // Comparison metrics bar chart data
  const comparisonData = [
    {
      metric: 'Data Downlinked (GB)',
      FCFS: Number(b.total_data_downlinked_gb.toFixed(1)),
      CPSAT: Number(o.total_data_downlinked_gb.toFixed(1)),
    },
    {
      metric: 'Objective Value (Score)',
      FCFS: Number(b.objective_value.toFixed(1)),
      CPSAT: Number(o.objective_value.toFixed(1)),
    },
    {
      metric: 'Scheduled Passes',
      FCFS: b.scheduled_passes_count,
      CPSAT: o.scheduled_passes_count,
    },
    {
      metric: 'P1 Satisfaction (%)',
      FCFS: Number(b.priority_satisfaction_rate.toFixed(1)),
      CPSAT: Number(o.priority_satisfaction_rate.toFixed(1)),
    },
  ];

  // Priority satisfaction comparison data
  const priorityData = [
    {
      priority: 'P1 (Critical)',
      FCFS: b.priority_breakdown['1'] || 0,
      CPSAT: o.priority_breakdown['1'] || 0,
    },
    {
      priority: 'P2 (High)',
      FCFS: b.priority_breakdown['2'] || 0,
      CPSAT: o.priority_breakdown['2'] || 0,
    },
    {
      priority: 'P3 (Medium)',
      FCFS: b.priority_breakdown['3'] || 0,
      CPSAT: o.priority_breakdown['3'] || 0,
    },
    {
      priority: 'P4 (Low)',
      FCFS: b.priority_breakdown['4'] || 0,
      CPSAT: o.priority_breakdown['4'] || 0,
    },
    {
      priority: 'P5 (Lowest)',
      FCFS: b.priority_breakdown['5'] || 0,
      CPSAT: o.priority_breakdown['5'] || 0,
    },
  ];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {/* 1. Global KPI Benchmark Chart */}
      <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 backdrop-blur-sm">
        <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
          Throughput & Efficiency Comparison
        </h4>
        <p className="text-[11px] text-slate-400 mb-4">
          Baseline First-Come-First-Served vs CP-SAT Constraint Programming Solver
        </p>

        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={comparisonData}
              margin={{ top: 10, right: 10, left: -15, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="metric" stroke="#64748b" tick={{ fontSize: 11 }} />
              <YAxis stroke="#64748b" tick={{ fontSize: 11 }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0f172a',
                  borderColor: '#334155',
                  borderRadius: '0.75rem',
                  fontSize: '12px',
                }}
              />
              <Legend
                wrapperStyle={{ fontSize: '12px', paddingTop: '8px' }}
              />
              <Bar
                dataKey="FCFS"
                name="Baseline FCFS"
                fill="#f59e0b"
                radius={[4, 4, 0, 0]}
              />
              <Bar
                dataKey="CPSAT"
                name="CP-SAT Optimizer"
                fill="#06b6d4"
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 2. Priority Satisfaction Breakdown */}
      <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 backdrop-blur-sm">
        <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
          Scheduled Passes by Priority Tier
        </h4>
        <p className="text-[11px] text-slate-400 mb-4">
          Protection of Mission-Critical (P1 & P2) contacts during antenna contention
        </p>

        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={priorityData}
              margin={{ top: 10, right: 10, left: -15, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="priority" stroke="#64748b" tick={{ fontSize: 11 }} />
              <YAxis
                stroke="#64748b"
                tick={{ fontSize: 11 }}
                allowDecimals={false}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0f172a',
                  borderColor: '#334155',
                  borderRadius: '0.75rem',
                  fontSize: '12px',
                }}
              />
              <Legend
                wrapperStyle={{ fontSize: '12px', paddingTop: '8px' }}
              />
              <Bar
                dataKey="FCFS"
                name="Baseline FCFS"
                fill="#eab308"
                radius={[4, 4, 0, 0]}
              />
              <Bar
                dataKey="CPSAT"
                name="CP-SAT Optimizer"
                fill="#8b5cf6"
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};
