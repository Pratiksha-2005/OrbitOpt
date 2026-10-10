import React, { useState, useEffect } from 'react';
import {
  FileText,
  Download,
  ShieldAlert,
  Clock,
  Radio,
  CheckCircle2,
  AlertTriangle,
  TrendingUp,
  Info,
  Server,
  Sparkles,
  HelpCircle,
} from 'lucide-react';
import type {
  OperationalAnalyticsResponse,
  DeadlineRiskSummary,
  RiskLevel,
  ScheduleRunResponse,
} from '../../types/api';
import {
  getOperationalAnalytics,
  getDeadlineRisks,
  downloadMissionReport,
  getApiErrorMessage,
} from '../../services/orbitOptApi';

interface MissionReportsViewProps {
  activeRun: ScheduleRunResponse | null;
  datasetId: string;
  isBackendConnected: boolean;
}

export const MissionReportsView: React.FC<MissionReportsViewProps> = ({
  activeRun,
  isBackendConnected,
}) => {
  const [analytics, setAnalytics] = useState<OperationalAnalyticsResponse | null>(null);
  const [risks, setRisks] = useState<DeadlineRiskSummary | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedRiskFilter, setSelectedRiskFilter] = useState<'ALL' | RiskLevel>('ALL');
  const [activeSubTab, setActiveSubTab] = useState<'risks' | 'stations' | 'comparison' | 'docs'>('risks');
  const [isExporting, setIsExporting] = useState<'csv' | 'json' | null>(null);

  useEffect(() => {
    let ignore = false;

    const fetchAnalytics = async () => {
      if (!activeRun || !isBackendConnected) {
        setAnalytics(null);
        setRisks(null);
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const [analyticsData, risksData] = await Promise.all([
          getOperationalAnalytics(activeRun.run_id),
          getDeadlineRisks(activeRun.run_id),
        ]);

        if (!ignore) {
          setAnalytics(analyticsData);
          setRisks(risksData);
        }
      } catch (err) {
        if (!ignore) {
          setError(getApiErrorMessage(err));
        }
      } finally {
        if (!ignore) {
          setIsLoading(false);
        }
      }
    };

    fetchAnalytics();

    return () => {
      ignore = true;
    };
  }, [activeRun?.run_id, isBackendConnected]);

  const handleExport = async (format: 'csv' | 'json') => {
    if (!activeRun) return;
    setIsExporting(format);
    try {
      await downloadMissionReport(activeRun.run_id, format);
    } catch (err) {
      alert(`Export failed: ${getApiErrorMessage(err)}`);
    } finally {
      setIsExporting(null);
    }
  };

  if (!activeRun) {
    return (
      <div className="p-12 text-center rounded-2xl bg-slate-900/60 border border-slate-800 text-slate-400">
        <FileText className="w-12 h-12 mx-auto text-slate-500 mb-4 opacity-50" />
        <h3 className="text-lg font-semibold text-slate-200 mb-2">No Active Schedule Run</h3>
        <p className="text-sm max-w-md mx-auto">
          Execute a Baseline FCFS or CP-SAT schedule run on the dashboard to generate and inspect operational analytics and mission reports.
        </p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="p-12 text-center rounded-2xl bg-slate-900/60 border border-slate-800 text-slate-400">
        <div className="inline-block animate-spin w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full mb-4" />
        <p className="text-sm font-medium text-slate-300">Auditing Schedule Records & Compiling Analytics...</p>
        <p className="text-xs text-slate-500 mt-1">Reconciling planned vs actual telemetry and station outages</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 rounded-2xl bg-red-950/40 border border-red-800 text-red-200">
        <div className="flex items-center gap-3 mb-2">
          <AlertTriangle className="w-5 h-5 text-red-400" />
          <h4 className="font-semibold text-red-100">Analytics Service Unavailable</h4>
        </div>
        <p className="text-sm text-red-300">{error}</p>
      </div>
    );
  }

  if (!analytics) return null;

  const filteredRisks = risks
    ? risks.items.filter((item) => {
        if (selectedRiskFilter === 'ALL') return true;
        return item.risk_level === selectedRiskFilter;
      })
    : [];

  return (
    <div className="space-y-6">
      {/* 1. Header & Real Export Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 rounded-2xl bg-slate-900/70 border border-slate-800 backdrop-blur-md">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold tracking-tight text-slate-100 flex items-center gap-2">
              <FileText className="w-5 h-5 text-cyan-400" />
              Operational Analytics & Mission Reports
            </h2>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-semibold bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
              {analytics.algorithm}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Persisted schedule run <span className="font-mono text-slate-300">{analytics.run_id}</span> on scenario <span className="font-medium text-slate-200">{analytics.dataset_name}</span>
          </p>
        </div>

        {/* Action Controls & Provenance */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Provenance Pill */}
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-slate-300 font-medium">Live Backend Metrics</span>
          </div>

          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-400">
            <Server className="w-3.5 h-3.5 text-cyan-400" />
            <span>Telemetry: {analytics.has_manual_telemetry ? 'Manual Updates' : 'Simulated Updates'}</span>
          </div>

          {/* Export CSV Button */}
          <button
            onClick={() => handleExport('csv')}
            disabled={isExporting !== null}
            className="flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-semibold bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 transition disabled:opacity-50"
          >
            <Download className="w-3.5 h-3.5" />
            {isExporting === 'csv' ? 'Generating CSV...' : 'Download Report (CSV)'}
          </button>

          {/* Export JSON Button */}
          <button
            onClick={() => handleExport('json')}
            disabled={isExporting !== null}
            className="flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-semibold bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 transition disabled:opacity-50"
          >
            <Download className="w-3.5 h-3.5" />
            {isExporting === 'json' ? 'Generating JSON...' : 'Download Report (JSON)'}
          </button>
        </div>
      </div>

      {/* 2. Operational Metrics Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Planned vs Actual Volume */}
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 backdrop-blur-sm relative overflow-hidden group hover:border-slate-700 transition">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Delivered vs Planned Volume
            </span>
            <div className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <Download className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold tracking-tight text-slate-100">
              {analytics.actual_delivered_data_gb.toFixed(1)}
            </span>
            <span className="text-xs text-slate-400 font-mono">
              / {analytics.planned_data_volume_gb.toFixed(1)} GB
            </span>
          </div>
          <div className="mt-3 flex items-center justify-between text-xs">
            <span className="text-slate-400">Confirmed Delivery</span>
            <span className="font-semibold font-mono text-indigo-400">
              {analytics.confirmed_delivery_ratio_pct !== null && analytics.confirmed_delivery_ratio_pct !== undefined
                ? `${analytics.confirmed_delivery_ratio_pct.toFixed(1)}%`
                : '0.0%'}
            </span>
          </div>
          <div className="w-full bg-slate-800 rounded-full h-1.5 mt-1.5 overflow-hidden">
            <div
              className="bg-indigo-500 h-1.5 rounded-full transition-all duration-500"
              style={{
                width: `${Math.min(100, analytics.confirmed_delivery_ratio_pct ?? 0)}%`,
              }}
            />
          </div>
          <p className="text-[10px] text-slate-500 mt-2">Never substitutes planned data for actual delivery.</p>
        </div>

        {/* Card 2: Critical Service Rate */}
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 backdrop-blur-sm relative overflow-hidden group hover:border-slate-700 transition">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Critical Priority Rate
            </span>
            <div className="p-1.5 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <ShieldAlert className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold tracking-tight text-slate-100">
              {analytics.critical_service_rate_pct.toFixed(1)}%
            </span>
            <span className="text-xs text-slate-400 font-mono">
              ({analytics.critical_scheduled_count}/{analytics.critical_total_count} P1)
            </span>
          </div>
          <div className="mt-3 flex items-center justify-between text-xs">
            <span className="text-slate-400">Service Coverage</span>
            <span className="font-semibold font-mono text-amber-400">
              {analytics.critical_scheduled_count} satisfied
            </span>
          </div>
          <div className="w-full bg-slate-800 rounded-full h-1.5 mt-1.5 overflow-hidden">
            <div
              className="bg-amber-500 h-1.5 rounded-full transition-all duration-500"
              style={{ width: `${Math.min(100, analytics.critical_service_rate_pct)}%` }}
            />
          </div>
          <p className="text-[10px] text-slate-500 mt-2 truncate" title={analytics.critical_denominator_definition}>
            Denominator: {analytics.critical_total_count} total P1 opportunities
          </p>
        </div>

        {/* Card 3: Deadline Satisfaction Rate */}
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 backdrop-blur-sm relative overflow-hidden group hover:border-slate-700 transition">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Deadline Satisfaction
            </span>
            <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <CheckCircle2 className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold tracking-tight text-slate-100">
              {analytics.deadline_satisfaction_rate_pct.toFixed(1)}%
            </span>
            <span className="text-xs text-slate-400 font-mono">
              ({analytics.deadline_satisfied_count}/{analytics.total_evaluated_deadlines})
            </span>
          </div>
          <div className="mt-3 flex items-center justify-between text-xs">
            <span className="text-slate-400">Missed Deadlines</span>
            <span className="font-semibold font-mono text-red-400">
              {analytics.deadline_missed_count} missed
            </span>
          </div>
          <div className="w-full bg-slate-800 rounded-full h-1.5 mt-1.5 overflow-hidden">
            <div
              className="bg-emerald-500 h-1.5 rounded-full transition-all duration-500"
              style={{ width: `${Math.min(100, analytics.deadline_satisfaction_rate_pct)}%` }}
            />
          </div>
          <p className="text-[10px] text-slate-500 mt-2">Pass window completion within horizon.</p>
        </div>

        {/* Card 4: Post-Outage Ground Station Availability */}
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 backdrop-blur-sm relative overflow-hidden group hover:border-slate-700 transition">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Station Availability
            </span>
            <div className="p-1.5 rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
              <Radio className="w-3.5 h-3.5" />
            </div>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold tracking-tight text-slate-100">
              {analytics.overall_availability_pct.toFixed(1)}%
            </span>
            <span className="text-xs text-slate-400 font-mono">
              post-outage
            </span>
          </div>
          <div className="mt-3 flex items-center justify-between text-xs">
            <span className="text-slate-400">Active Outages</span>
            <span className="font-semibold font-mono text-cyan-400">
              {analytics.outage_count} active ({analytics.total_outage_hours.toFixed(1)}h)
            </span>
          </div>
          <div className="w-full bg-slate-800 rounded-full h-1.5 mt-1.5 overflow-hidden">
            <div
              className="bg-cyan-500 h-1.5 rounded-full transition-all duration-500"
              style={{ width: `${Math.min(100, analytics.overall_availability_pct)}%` }}
            />
          </div>
          <p className="text-[10px] text-slate-500 mt-2">Deducts active outage hours from total horizon.</p>
        </div>
      </div>

      {/* 3. Waiting Times and Time-Based Utilization Banner */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Waiting Times */}
        <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800">
          <div className="flex items-center gap-2 mb-3">
            <Clock className="w-4 h-4 text-purple-400" />
            <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
              Waiting Time Metrics (Seconds from Opportunity Availability)
            </h4>
          </div>
          <div className="grid grid-cols-4 gap-2 text-center">
            <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800/80">
              <span className="text-[10px] uppercase text-slate-400 font-medium block">Mean</span>
              <span className="text-base font-bold font-mono text-purple-300">
                {analytics.mean_wait_time_seconds !== null ? `${analytics.mean_wait_time_seconds}s` : 'N/A'}
              </span>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800/80">
              <span className="text-[10px] uppercase text-slate-400 font-medium block">Median (P50)</span>
              <span className="text-base font-bold font-mono text-purple-300">
                {analytics.median_wait_time_seconds !== null ? `${analytics.median_wait_time_seconds}s` : 'N/A'}
              </span>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800/80">
              <span className="text-[10px] uppercase text-slate-400 font-medium block">P90</span>
              <span className="text-base font-bold font-mono text-purple-300">
                {analytics.p90_wait_time_seconds !== null ? `${analytics.p90_wait_time_seconds}s` : 'N/A'}
              </span>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800/80">
              <span className="text-[10px] uppercase text-slate-400 font-medium block">P95</span>
              <span className="text-base font-bold font-mono text-purple-300">
                {analytics.p95_wait_time_seconds !== null ? `${analytics.p95_wait_time_seconds}s` : 'N/A'}
              </span>
            </div>
          </div>
          <p className="text-[10px] text-slate-500 mt-2">{analytics.wait_time_basis}</p>
        </div>

        {/* Time-Based Transmission Utilization vs Total Occupancy */}
        <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800">
          <div className="flex items-center gap-2 mb-3">
            <Radio className="w-4 h-4 text-emerald-400" />
            <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
              Time-Based Transmission Utilization vs Resource Occupancy
            </h4>
          </div>
          <div className="grid grid-cols-2 gap-3 text-center">
            <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800/80">
              <span className="text-[10px] uppercase text-slate-400 font-medium block">Active Transmission</span>
              <span className="text-xl font-bold font-mono text-emerald-300">
                {analytics.transmission_utilization_pct.toFixed(1)}%
              </span>
              <span className="text-[10px] text-slate-500 block mt-0.5">Time downlinking only</span>
            </div>
            <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800/80">
              <span className="text-[10px] uppercase text-slate-400 font-medium block">Total Occupancy (w/ Buffers)</span>
              <span className="text-xl font-bold font-mono text-cyan-300">
                {analytics.total_occupancy_pct.toFixed(1)}%
              </span>
              <span className="text-[10px] text-slate-500 block mt-0.5">Includes {analytics.setup_buffer_seconds_used}s antenna slew</span>
            </div>
          </div>
          <p className="text-[10px] text-slate-500 mt-2">Computed as active duration / total station horizon (never pass counts).</p>
        </div>
      </div>

      {/* 4. Sub-Navigation Tabs */}
      <div className="border-b border-slate-800 flex items-center gap-2">
        <button
          onClick={() => setActiveSubTab('risks')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold border-b-2 transition ${
            activeSubTab === 'risks'
              ? 'border-cyan-400 text-cyan-300 bg-cyan-500/5'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <AlertTriangle className="w-3.5 h-3.5" />
          Deterministic Deadline-Risk Analysis ({risks?.total_requests || 0})
        </button>

        <button
          onClick={() => setActiveSubTab('stations')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold border-b-2 transition ${
            activeSubTab === 'stations'
              ? 'border-cyan-400 text-cyan-300 bg-cyan-500/5'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Radio className="w-3.5 h-3.5" />
          Station Availability & Utilization ({analytics.station_availability.length})
        </button>

        <button
          onClick={() => setActiveSubTab('comparison')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold border-b-2 transition ${
            activeSubTab === 'comparison'
              ? 'border-cyan-400 text-cyan-300 bg-cyan-500/5'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <TrendingUp className="w-3.5 h-3.5" />
          FCFS vs CP-SAT Benchmark Audit
        </button>

        <button
          onClick={() => setActiveSubTab('docs')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold border-b-2 transition ${
            activeSubTab === 'docs'
              ? 'border-cyan-400 text-cyan-300 bg-cyan-500/5'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <HelpCircle className="w-3.5 h-3.5" />
          Metric Formulas & Denominators
        </button>
      </div>

      {/* 5. Sub-Tab Content */}

      {/* Sub-Tab A: Deterministic Deadline Risks */}
      {activeSubTab === 'risks' && (
        <div className="space-y-4">
          <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-200 flex items-start gap-2.5">
            <Info className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">{risks?.method_disclaimer}</p>
              <p className="text-[11px] text-amber-300/80 mt-0.5">
                Evaluates each opportunity against pass deadline, transmission duration, antenna slewing buffers, and ground station outages.
              </p>
            </div>
          </div>

          {/* Risk Level Filter Chips */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-slate-400 mr-2">Filter Risk Level:</span>
            {(['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] as const).map((lvl) => {
              const isSelected = selectedRiskFilter === lvl;
              let count = risks?.total_requests || 0;
              if (lvl === 'CRITICAL') count = risks?.critical_risk_count || 0;
              if (lvl === 'HIGH') count = risks?.high_risk_count || 0;
              if (lvl === 'MEDIUM') count = risks?.medium_risk_count || 0;
              if (lvl === 'LOW') count = risks?.low_risk_count || 0;

              return (
                <button
                  key={lvl}
                  onClick={() => setSelectedRiskFilter(lvl)}
                  className={`px-3 py-1 rounded-lg text-xs font-semibold transition ${
                    isSelected
                      ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                      : 'bg-slate-900 text-slate-400 border border-slate-800 hover:text-slate-200'
                  }`}
                >
                  {lvl} ({count})
                </button>
              );
            })}
          </div>

          {/* Risks Table */}
          <div className="rounded-xl border border-slate-800 overflow-hidden bg-slate-900/40">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/80 text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-800">
                <tr>
                  <th className="py-2.5 px-3">Pass ID</th>
                  <th className="py-2.5 px-3">Satellite & Station</th>
                  <th className="py-2.5 px-3">Priority</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Risk Level</th>
                  <th className="py-2.5 px-3">Slack / Outage</th>
                  <th className="py-2.5 px-3">Deterministic Explanation</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {filteredRisks.map((item) => {
                  let badgeColor = 'bg-slate-500/10 text-slate-400 border-slate-500/20';
                  if (item.risk_level === 'CRITICAL') badgeColor = 'bg-red-500/10 text-red-400 border-red-500/20';
                  if (item.risk_level === 'HIGH') badgeColor = 'bg-amber-500/10 text-amber-400 border-amber-500/20';
                  if (item.risk_level === 'MEDIUM') badgeColor = 'bg-yellow-500/10 text-yellow-300 border-yellow-500/20';
                  if (item.risk_level === 'LOW') badgeColor = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';

                  return (
                    <tr key={item.pass_id} className="hover:bg-slate-800/30 transition">
                      <td className="py-2 px-3 font-semibold text-slate-200">{item.pass_id}</td>
                      <td className="py-2 px-3 text-slate-300">
                        {item.satellite_id} <span className="text-slate-500">→</span> {item.ground_station_id}
                      </td>
                      <td className="py-2 px-3">
                        <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300 border border-slate-700">
                          P{item.priority}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-slate-300">{item.execution_status}</td>
                      <td className="py-2 px-3">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${badgeColor}`}>
                          {item.risk_level}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-slate-400">
                        {item.slack_seconds !== null && item.slack_seconds !== undefined
                          ? `${item.slack_seconds.toFixed(0)}s slack`
                          : 'N/A'}
                        {item.has_outage_conflict && (
                          <span className="ml-1.5 px-1.5 py-0.5 rounded text-[9px] bg-red-500/20 text-red-300 font-sans font-bold">
                            OUTAGE CONFLICT
                          </span>
                        )}
                      </td>
                      <td className="py-2 px-3 text-slate-300 font-sans">{item.explanation}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Sub-Tab B: Ground Station Availability & Utilization */}
      {activeSubTab === 'stations' && (
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-800 overflow-hidden bg-slate-900/40">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/80 text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-800">
                <tr>
                  <th className="py-2.5 px-3">Station ID</th>
                  <th className="py-2.5 px-3">Station Name</th>
                  <th className="py-2.5 px-3">Horizon Hours</th>
                  <th className="py-2.5 px-3">Outage Hours</th>
                  <th className="py-2.5 px-3">Available Hours</th>
                  <th className="py-2.5 px-3">Availability %</th>
                  <th className="py-2.5 px-3">Active Outages</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {analytics.station_availability.map((st) => (
                  <tr key={st.station_id} className="hover:bg-slate-800/30 transition">
                    <td className="py-2.5 px-3 font-semibold text-slate-200">{st.station_id}</td>
                    <td className="py-2.5 px-3 text-slate-300 font-sans">{st.station_name}</td>
                    <td className="py-2.5 px-3 text-slate-400">{st.horizon_hours.toFixed(1)}h</td>
                    <td className="py-2.5 px-3 text-red-400">{st.outage_hours.toFixed(1)}h</td>
                    <td className="py-2.5 px-3 text-emerald-400">{st.available_hours.toFixed(1)}h</td>
                    <td className="py-2.5 px-3 font-bold text-cyan-300">{st.availability_percentage.toFixed(1)}%</td>
                    <td className="py-2.5 px-3 text-slate-400 font-sans">
                      {st.active_outages_count > 0 ? (
                        <span className="text-amber-400 font-semibold">{st.active_outages_count} active</span>
                      ) : (
                        <span className="text-slate-500">None</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/50 border border-slate-800">
            <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">
              Time-Based Station Transmission Utilization Breakdown
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {analytics.station_utilizations.map((u) => (
                <div key={u.station_id} className="p-3 rounded-lg bg-slate-950 border border-slate-800">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="font-semibold text-slate-200 text-xs">{u.station_id}</span>
                    <span className="text-[10px] text-slate-400 font-sans">{u.station_name}</span>
                  </div>
                  <div className="flex items-baseline justify-between text-xs font-mono">
                    <span className="text-slate-400">Tx Utilization:</span>
                    <span className="text-emerald-400 font-bold">{u.transmission_utilization_pct.toFixed(1)}%</span>
                  </div>
                  <div className="flex items-baseline justify-between text-xs font-mono mt-1">
                    <span className="text-slate-400">Total Occupancy:</span>
                    <span className="text-cyan-400 font-bold">{u.total_occupancy_pct.toFixed(1)}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Sub-Tab C: FCFS vs CP-SAT Benchmark Comparison */}
      {activeSubTab === 'comparison' && (
        <div className="space-y-4">
          {analytics.benchmark_comparison ? (
            <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-cyan-400" />
                    Audited Benchmark: Baseline FCFS vs CP-SAT Optimizer
                  </h4>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Evaluated on identical scenario input data and antenna slewing margins
                  </p>
                </div>
                <span className="px-2.5 py-1 rounded-full text-xs font-mono bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                  {analytics.benchmark_comparison.runtime_ratio}x solver runtime ratio
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                  <span className="text-[10px] uppercase text-slate-400 block font-medium">Throughput Improvement</span>
                  <span className="text-xl font-bold font-mono text-emerald-400">
                    +{analytics.benchmark_comparison.volume_improvement_gb.toFixed(1)} GB
                  </span>
                  <span className="text-[11px] text-emerald-400/80 block mt-0.5">
                    (+{analytics.benchmark_comparison.volume_improvement_pct.toFixed(1)}% vs FCFS)
                  </span>
                </div>

                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                  <span className="text-[10px] uppercase text-slate-400 block font-medium">Objective Value Gain</span>
                  <span className="text-xl font-bold font-mono text-cyan-400">
                    +{analytics.benchmark_comparison.objective_improvement_pct.toFixed(1)}%
                  </span>
                  <span className="text-[11px] text-cyan-400/80 block mt-0.5">
                    {analytics.benchmark_comparison.optimized_objective} vs {analytics.benchmark_comparison.baseline_objective}
                  </span>
                </div>

                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                  <span className="text-[10px] uppercase text-slate-400 block font-medium">Critical Priority Delta</span>
                  <span className="text-xl font-bold font-mono text-amber-400">
                    {analytics.benchmark_comparison.critical_service_rate_delta_pct >= 0 ? '+' : ''}
                    {analytics.benchmark_comparison.critical_service_rate_delta_pct.toFixed(1)}%
                  </span>
                  <span className="text-[11px] text-amber-400/80 block mt-0.5">
                    {analytics.benchmark_comparison.optimized_critical_service_rate_pct}% vs {analytics.benchmark_comparison.baseline_critical_service_rate_pct}%
                  </span>
                </div>

                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                  <span className="text-[10px] uppercase text-slate-400 block font-medium">Scheduled Passes Delta</span>
                  <span className="text-xl font-bold font-mono text-purple-400">
                    {analytics.benchmark_comparison.scheduled_passes_delta >= 0 ? '+' : ''}
                    {analytics.benchmark_comparison.scheduled_passes_delta} passes
                  </span>
                  <span className="text-[11px] text-purple-400/80 block mt-0.5">
                    {analytics.benchmark_comparison.optimized_scheduled_passes} vs {analytics.benchmark_comparison.baseline_scheduled_passes}
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-8 text-center rounded-xl bg-slate-900/50 border border-slate-800 text-slate-400">
              <p className="text-sm">
                No matching counterpart baseline run found in database for this dataset scenario.
                Run both Baseline FCFS and CP-SAT to see the automated benchmark audit.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Sub-Tab D: Metric Documentation & Denominators */}
      {activeSubTab === 'docs' && (
        <div className="space-y-3">
          <p className="text-xs text-slate-400">
            Audit specifications for operational metrics, formulas, denominators, and missing data policies:
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {Object.entries(analytics.metric_documentation).map(([key, doc]) => (
              <div key={key} className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1.5 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-cyan-300">{doc.name}</span>
                  <span className="font-mono text-[10px] text-slate-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                    {doc.units}
                  </span>
                </div>
                <div className="font-mono text-slate-300 bg-slate-950 p-2 rounded text-[11px] border border-slate-800/80">
                  Formula: {doc.formula}
                </div>
                <p className="text-slate-400">
                  <span className="font-semibold text-slate-300">Denominator:</span> {doc.denominator}
                </p>
                <p className="text-slate-500 text-[11px]">
                  <span className="font-semibold text-slate-400">Missing Data:</span> {doc.handling_missing_data}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
