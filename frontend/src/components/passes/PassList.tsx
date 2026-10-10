import React, { useState, useEffect, useCallback } from 'react';
import {
  Satellite,
  Search,
  Filter,
  Eye,
  CheckCircle2,
  XCircle,
  Radio,
  Lock,
  Unlock,
  Activity,
  Clock,
  AlertCircle,
  RotateCw,
} from 'lucide-react';

import type {
  SatellitePass,
  ScheduleRunResponse,
  PassExecutionRead,
  PassExecutionStatus,
  PassTransitionRequest,
} from '../../types/api';
import { listExecutions, transitionPassExecution } from '../../services/orbitOptApi';
import { PassDetailModal } from './PassDetailModal';
import { EmptyState } from '../common/EmptyState';

interface PassListProps {
  passes: SatellitePass[];
  activeRun: ScheduleRunResponse | null;
  datasetId?: string;
  onScheduleRefresh?: () => void;
}

export const PassList: React.FC<PassListProps> = ({
  passes,
  activeRun,
  datasetId,
  onScheduleRefresh,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedPriority, setSelectedPriority] = useState<string>('all');
  const [selectedStation, setSelectedStation] = useState<string>('all');
  const [selectedBand, setSelectedBand] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [inspectPass, setInspectPass] = useState<SatellitePass | null>(null);

  // Live execution records mapped by pass_id
  const [executionsMap, setExecutionsMap] = useState<Map<string, PassExecutionRead>>(new Map());
  const [isLoadingExecutions, setIsLoadingExecutions] = useState(false);

  // Sync execution records from backend API
  const fetchExecutions = useCallback(async () => {
    try {
      setIsLoadingExecutions(true);
      const list = await listExecutions({
        dataset_id: datasetId,
        schedule_run_id: activeRun?.run_id,
      });
      const map = new Map<string, PassExecutionRead>();
      list.forEach((e) => map.set(e.pass_id, e));
      setExecutionsMap(map);
    } catch {
      // In offline / preview fallback, synthesize from activeRun scheduled_passes
      if (activeRun) {
        const map = new Map<string, PassExecutionRead>();
        activeRun.scheduled_passes.forEach((sp) => {
          map.set(sp.pass_id, {
            id: `exec_${sp.pass_id}`,
            pass_id: sp.pass_id,
            satellite_id: sp.satellite_id,
            ground_station_id: sp.ground_station_id,
            status: (sp.execution_status as PassExecutionStatus) || 'SCHEDULED',
            is_locked: sp.is_locked || false,
            planned_start_time: sp.start_time,
            planned_end_time: sp.end_time,
            planned_data_volume_gb: sp.data_volume_gb,
            estimated_transfer_rate_mbps: sp.estimated_transfer_rate_mbps || 400,
            actual_start_time: sp.actual_start_time || null,

            actual_end_time: sp.actual_end_time || null,
            actual_data_delivered_gb: sp.actual_data_delivered_gb || null,
            measured_transfer_rate_mbps: sp.measured_transfer_rate_mbps || null,
            telemetry_source: 'simulated',
            transition_history: [],
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          });
        });
        setExecutionsMap(map);
      }
    } finally {
      setIsLoadingExecutions(false);
    }
  }, [datasetId, activeRun]);

  useEffect(() => {
    fetchExecutions();
  }, [fetchExecutions]);

  // Handle transition submission
  const handleTransition = async (passId: string, req: PassTransitionRequest) => {
    try {
      const updated = await transitionPassExecution(passId, req);
      setExecutionsMap((prev) => {
        const copy = new Map(prev);
        copy.set(passId, updated);
        return copy;
      });
      if (onScheduleRefresh) {
        onScheduleRefresh();
      }
    } catch {
      // Offline fallback state mutation
      setExecutionsMap((prev) => {
        const copy = new Map(prev);
        const existing = copy.get(passId);
        if (existing) {
          const isNowLocked =
            req.to_status === 'ACQUIRING' ||
            req.to_status === 'TRANSMITTING' ||
            req.to_status === 'COMPLETED';
          copy.set(passId, {
            ...existing,
            status: req.to_status,
            is_locked: isNowLocked,
            actual_data_delivered_gb: req.actual_data_delivered_gb ?? existing.actual_data_delivered_gb,
            telemetry_source: req.telemetry_source || 'operator_manual',
            transition_history: [
              ...existing.transition_history,
              {
                from_status: existing.status,
                to_status: req.to_status,
                timestamp: new Date().toISOString(),
                actual_data_delivered_gb: req.actual_data_delivered_gb,
                telemetry_source: req.telemetry_source || 'operator_manual',
                notes: req.notes,
              },
            ],
          });
        }
        return copy;
      });
    }
  };

  // Ground stations list for filtering
  const stations = Array.from(new Set(passes.map((p) => p.ground_station_id)));

  // Filter passes
  const filteredPasses = passes.filter((p) => {
    const matchesSearch =
      p.pass_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.satellite_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.ground_station_id.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesPriority =
      selectedPriority === 'all' || p.priority.toString() === selectedPriority;

    const matchesStation =
      selectedStation === 'all' || p.ground_station_id === selectedStation;

    const matchesBand =
      selectedBand === 'all' || (p.channel_band || 'X-band') === selectedBand;

    const execRecord = executionsMap.get(p.pass_id);
    const execStatus = execRecord?.status || 'SCHEDULED';
    const matchesStatus =
      selectedStatus === 'all' || execStatus === selectedStatus;


    return matchesSearch && matchesPriority && matchesStation && matchesBand && matchesStatus;
  });

  const getPriorityBadge = (priority: number) => {
    switch (priority) {
      case 1:
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/30">
            P1 Critical
          </span>
        );
      case 2:
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-orange-500/20 text-orange-300 border border-orange-500/30">
            P2 High
          </span>
        );
      case 3:
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30">
            P3 Medium
          </span>
        );
      case 4:
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
            P4 Low
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-500/20 text-slate-300 border border-slate-500/30">
            P5 Lowest
          </span>
        );
    }
  };

  const getExecutionBadge = (st: PassExecutionStatus) => {
    switch (st) {
      case 'ACQUIRING':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-sky-500/20 text-sky-300 border border-sky-500/30 animate-pulse">
            <Activity className="w-3 h-3" />
            ACQUIRING
          </span>
        );
      case 'TRANSMITTING':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 animate-pulse">
            <Radio className="w-3 h-3" />
            TRANSMITTING
          </span>
        );
      case 'COMPLETED':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-teal-500/20 text-teal-300 border border-teal-500/30">
            <CheckCircle2 className="w-3 h-3" />
            COMPLETED
          </span>
        );
      case 'MISSED':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/30">
            <AlertCircle className="w-3 h-3" />
            MISSED
          </span>
        );
      case 'CANCELLED':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-500/20 text-slate-300 border border-slate-500/30">
            <XCircle className="w-3 h-3" />
            CANCELLED
          </span>
        );
      case 'SCHEDULED':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
            <Clock className="w-3 h-3" />
            SCHEDULED
          </span>
        );
    }
  };

  return (
    <div className="space-y-4">
      {/* Search & Filters Bar */}
      <div className="flex flex-col md:flex-row gap-3 items-stretch md:items-center justify-between p-3 rounded-xl bg-slate-900/60 border border-slate-800">
        <div className="flex flex-1 items-center gap-2">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search by Pass, Satellite, Station..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-slate-200 placeholder-slate-500 text-xs focus:outline-none focus:border-cyan-500 transition"
            />
          </div>

          <div className="flex items-center gap-1.5 overflow-x-auto text-xs">
            <Filter className="w-3.5 h-3.5 text-slate-400 shrink-0 ml-1" />

            {/* Execution State Filter */}
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="px-2.5 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-slate-300 text-xs focus:outline-none focus:border-cyan-500 font-medium"
            >
              <option value="all">All States</option>
              <option value="SCHEDULED">Scheduled</option>
              <option value="ACQUIRING">Acquiring</option>
              <option value="TRANSMITTING">Transmitting</option>
              <option value="COMPLETED">Completed</option>
              <option value="MISSED">Missed</option>
              <option value="CANCELLED">Cancelled</option>
            </select>

            {/* Priority Filter */}
            <select
              value={selectedPriority}
              onChange={(e) => setSelectedPriority(e.target.value)}
              className="px-2.5 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-slate-300 text-xs focus:outline-none focus:border-cyan-500"
            >
              <option value="all">All Priorities</option>
              <option value="1">P1 Critical</option>
              <option value="2">P2 High</option>
              <option value="3">P3 Medium</option>
              <option value="4">P4 Low</option>
              <option value="5">P5 Lowest</option>
            </select>

            {/* Ground Station Filter */}
            <select
              value={selectedStation}
              onChange={(e) => setSelectedStation(e.target.value)}
              className="px-2.5 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-slate-300 text-xs focus:outline-none focus:border-cyan-500"
            >
              <option value="all">All Ground Stations</option>
              {stations.map((st) => (
                <option key={st} value={st}>
                  {st}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex items-center justify-between md:justify-end gap-3 text-xs text-slate-400">
          <button
            onClick={() => fetchExecutions()}
            title="Refresh execution states"
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isLoadingExecutions ? 'animate-spin' : ''}`} />
          </button>
          <span>
            Showing <strong className="text-slate-200">{filteredPasses.length}</strong> of{' '}
            {passes.length} passes
          </span>
        </div>
      </div>

      {/* Passes Table */}
      {filteredPasses.length === 0 ? (
        <EmptyState
          title="No Matching Passes Found"
          description="Try relaxing your search terms or filter selections."
          actionText="Reset Filters"
          onAction={() => {
            setSearchTerm('');
            setSelectedPriority('all');
            setSelectedStation('all');
            setSelectedBand('all');
            setSelectedStatus('all');
          }}
        />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/60 backdrop-blur-sm">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 uppercase tracking-wider text-[11px]">
              <tr>
                <th className="py-3 px-4">Pass & Satellite</th>
                <th className="py-3 px-4">Ground Station</th>
                <th className="py-3 px-4">Window (UTC)</th>
                <th className="py-3 px-4">Duration</th>
                <th className="py-3 px-4">Priority</th>
                <th className="py-3 px-4">Volume (GB)</th>
                <th className="py-3 px-4">Execution State</th>
                <th className="py-3 px-4">Preemption Lock</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              {filteredPasses.map((p) => {
                const durationSec =
                  (new Date(p.end_time).getTime() - new Date(p.start_time).getTime()) / 1000;
                const exec = executionsMap.get(p.pass_id);
                const execStatus: PassExecutionStatus = exec?.status || 'SCHEDULED';
                const isLocked = exec?.is_locked ?? false;

                return (
                  <tr
                    key={p.pass_id}
                    className="hover:bg-slate-800/40 transition group"
                  >
                    {/* Pass & Sat ID */}
                    <td className="py-3 px-4">
                      <div className="font-semibold text-slate-100 flex items-center gap-1.5">
                        <Satellite className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                        <span className="font-mono">{p.pass_id}</span>
                      </div>
                      <div className="text-[11px] text-slate-400 mt-0.5">{p.satellite_id}</div>
                    </td>

                    {/* Ground Station */}
                    <td className="py-3 px-4">
                      <div className="font-medium text-slate-200 flex items-center gap-1">
                        <Radio className="w-3 h-3 text-slate-400 shrink-0" />
                        <span>{p.ground_station_id}</span>
                      </div>
                      <div className="text-[10px] text-slate-400 font-mono">
                        {p.channel_band || 'X-band'}
                      </div>
                    </td>

                    {/* Window UTC */}
                    <td className="py-3 px-4 font-mono text-[11px]">
                      <div>{new Date(p.start_time).toISOString().substring(11, 16)} UTC</div>
                      <div className="text-slate-500">
                        to {new Date(p.end_time).toISOString().substring(11, 16)} UTC
                      </div>
                    </td>

                    {/* Duration */}
                    <td className="py-3 px-4">
                      <span className="font-mono font-medium text-slate-200">
                        {durationSec}s
                      </span>
                      <span className="text-[10px] text-slate-500 block">
                        ({(durationSec / 60).toFixed(1)}m)
                      </span>
                    </td>

                    {/* Priority */}
                    <td className="py-3 px-4">{getPriorityBadge(p.priority)}</td>

                    {/* Volume (Planned vs Delivered) */}
                    <td className="py-3 px-4 font-mono">
                      {exec?.actual_data_delivered_gb !== null && exec?.actual_data_delivered_gb !== undefined ? (
                        <div>
                          <span className="text-emerald-300 font-semibold">
                            {exec.actual_data_delivered_gb.toFixed(1)}
                          </span>
                          <span className="text-slate-500 text-[10px]"> / {p.data_volume_gb.toFixed(1)} GB</span>
                          <span className="text-[9px] text-emerald-400 block font-sans">Delivered</span>
                        </div>
                      ) : (
                        <div>
                          <div className="font-semibold text-slate-100">
                            {p.data_volume_gb.toFixed(1)} GB
                          </div>
                          <div className="text-[10px] text-slate-500">
                            {p.effective_data_rate_mbps || 400} Mbps
                          </div>
                        </div>
                      )}
                    </td>

                    {/* Execution State */}
                    <td className="py-3 px-4">
                      {getExecutionBadge(execStatus)}
                    </td>

                    {/* Lock Status */}
                    <td className="py-3 px-4">
                      {isLocked ? (
                        <span
                          title="Pass is actively tracking or completed; locked against re-optimization and emergency preemption"
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 cursor-help"
                        >
                          <Lock className="w-3 h-3" />
                          LOCKED
                        </span>
                      ) : (
                        <span
                          title="Pass is scheduled in future; reconfigurable during re-optimization"
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-slate-400 border border-slate-700"
                        >
                          <Unlock className="w-3 h-3" />
                          UNLOCKED
                        </span>
                      )}
                    </td>

                    {/* Action */}
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => setInspectPass(p)}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs border border-slate-700 transition"
                      >
                        <Eye className="w-3.5 h-3.5 text-cyan-400" />
                        Control
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Inspect & State Transition Modal */}
      <PassDetailModal
        pass={inspectPass}
        execution={inspectPass ? executionsMap.get(inspectPass.pass_id) : null}
        onClose={() => setInspectPass(null)}
        onTransition={handleTransition}
      />
    </div>
  );
};
