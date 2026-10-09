import React, { useState } from 'react';
import {
  Satellite,
  Search,
  Filter,
  Eye,
  CheckCircle2,
  XCircle,
  Radio,
} from 'lucide-react';
import type { SatellitePass, ScheduleRunResponse } from '../../types/api';
import { PassDetailModal } from './PassDetailModal';
import { EmptyState } from '../common/EmptyState';

interface PassListProps {
  passes: SatellitePass[];
  activeRun: ScheduleRunResponse | null;
}

export const PassList: React.FC<PassListProps> = ({ passes, activeRun }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedPriority, setSelectedPriority] = useState<string>('all');
  const [selectedStation, setSelectedStation] = useState<string>('all');
  const [selectedBand, setSelectedBand] = useState<string>('all');
  const [inspectPass, setInspectPass] = useState<SatellitePass | null>(null);

  // Set of scheduled pass IDs in the active run
  const scheduledPassIds = new Set(
    activeRun?.scheduled_passes.map((p) => p.pass_id) || []
  );

  // Set of unassigned pass IDs in the active run
  const unassignedMap = new Map<string, string>(
    activeRun?.unassigned_passes.map((p) => [p.pass_id, p.reason]) || []
  );

  // Ground stations list for filtering
  const stations = Array.from(new Set(passes.map((p) => p.ground_station_id)));
  // Bands for filtering
  const bands = Array.from(
    new Set(passes.map((p) => p.channel_band || 'X-band'))
  );

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

    return matchesSearch && matchesPriority && matchesStation && matchesBand;
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

  return (
    <div className="space-y-4">
      {/* Search & Filters Bar */}
      <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 backdrop-blur-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        {/* Search Input */}
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by Satellite, Pass ID, or Ground Station..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-slate-950/80 border border-slate-700/80 rounded-lg pl-9 pr-4 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition"
          />
        </div>

        {/* Filters dropdowns */}
        <div className="flex flex-wrap items-center gap-2.5 text-xs">
          <div className="flex items-center gap-1.5 text-slate-400">
            <Filter className="w-3.5 h-3.5" />
            <span>Filters:</span>
          </div>

          {/* Priority filter */}
          <select
            value={selectedPriority}
            onChange={(e) => setSelectedPriority(e.target.value)}
            className="bg-slate-950/80 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-500"
          >
            <option value="all">All Priorities</option>
            <option value="1">P1 - Critical</option>
            <option value="2">P2 - High</option>
            <option value="3">P3 - Medium</option>
            <option value="4">P4 - Low</option>
            <option value="5">P5 - Lowest</option>
          </select>

          {/* Station filter */}
          <select
            value={selectedStation}
            onChange={(e) => setSelectedStation(e.target.value)}
            className="bg-slate-950/80 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-500"
          >
            <option value="all">All Stations</option>
            {stations.map((st) => (
              <option key={st} value={st}>
                {st}
              </option>
            ))}
          </select>

          {/* Band filter */}
          <select
            value={selectedBand}
            onChange={(e) => setSelectedBand(e.target.value)}
            className="bg-slate-950/80 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-500"
          >
            <option value="all">All Bands</option>
            {bands.map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Passes Count Summary */}
      <div className="flex items-center justify-between px-1 text-xs text-slate-400">
        <div>
          Showing <span className="font-semibold text-slate-200">{filteredPasses.length}</span> of{' '}
          <span className="font-semibold text-slate-200">{passes.length}</span> pass opportunities
        </div>
        {activeRun && (
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center gap-1 text-emerald-400">
              <CheckCircle2 className="w-3.5 h-3.5" />
              {activeRun.metrics.scheduled_passes_count} Scheduled
            </span>
            <span className="inline-flex items-center gap-1 text-rose-400">
              <XCircle className="w-3.5 h-3.5" />
              {activeRun.metrics.unassigned_passes_count} Unassigned
            </span>
          </div>
        )}
      </div>

      {/* Passes Table / Card View */}
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
                <th className="py-3 px-4">Max Elev.</th>
                <th className="py-3 px-4">Priority</th>
                <th className="py-3 px-4">Volume</th>
                <th className="py-3 px-4">Schedule Status</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              {filteredPasses.map((p) => {
                const durationSec =
                  (new Date(p.end_time).getTime() - new Date(p.start_time).getTime()) / 1000;
                const isScheduled = scheduledPassIds.has(p.pass_id);
                const unassignedReason = unassignedMap.get(p.pass_id);

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

                    {/* Elevation */}
                    <td className="py-3 px-4">
                      <span
                        className={`font-semibold font-mono ${
                          p.max_elevation_deg >= 60
                            ? 'text-emerald-400'
                            : p.max_elevation_deg >= 35
                            ? 'text-cyan-400'
                            : 'text-amber-400'
                        }`}
                      >
                        {p.max_elevation_deg}°
                      </span>
                    </td>

                    {/* Priority */}
                    <td className="py-3 px-4">{getPriorityBadge(p.priority)}</td>

                    {/* Volume */}
                    <td className="py-3 px-4 font-mono">
                      <div className="font-semibold text-slate-100">
                        {p.data_volume_gb.toFixed(1)} GB
                      </div>
                      <div className="text-[10px] text-slate-500">
                        {p.effective_data_rate_mbps || 400} Mbps
                      </div>
                    </td>

                    {/* Status in Active Run */}
                    <td className="py-3 px-4">
                      {activeRun ? (
                        isScheduled ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                            Allocated
                          </span>
                        ) : (
                          <span
                            title={unassignedReason || 'Unassigned due to conflict'}
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-rose-500/15 text-rose-300 border border-rose-500/30 cursor-help"
                          >
                            <XCircle className="w-3 h-3 text-rose-400" />
                            Unassigned
                          </span>
                        )
                      ) : (
                        <span className="text-slate-500 font-mono text-[11px]">Unscheduled</span>
                      )}
                    </td>

                    {/* Action */}
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => setInspectPass(p)}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs border border-slate-700 transition"
                      >
                        <Eye className="w-3.5 h-3.5 text-cyan-400" />
                        Inspect
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Inspect Modal */}
      <PassDetailModal pass={inspectPass} onClose={() => setInspectPass(null)} />
    </div>
  );
};
