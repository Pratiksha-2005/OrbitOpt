import React, { useState, useEffect, useCallback } from 'react';
import { Radio, AlertTriangle, CheckCircle2, RefreshCw, Wrench, ShieldAlert } from 'lucide-react';
import type { GroundStation, ScheduleRunResponse, OutageRead } from '../../types/api';
import { createOutage, listOutages, resolveOutage, getApiErrorMessage } from '../../services/orbitOptApi';
import { WorldCoverageMap } from './WorldCoverageMap';

interface GroundStationsViewProps {
  stations: GroundStation[];
  activeRun: ScheduleRunResponse | null;
  datasetId?: string;
  onScheduleUpdate?: (updatedRun: ScheduleRunResponse) => void;
}

export const GroundStationsView: React.FC<GroundStationsViewProps> = ({
  stations,
  activeRun,
  datasetId,
  onScheduleUpdate,
}) => {
  const [selectedStationId, setSelectedStationId] = useState<string | undefined>(
    stations[0]?.station_id
  );
  const [outages, setOutages] = useState<OutageRead[]>([]);
  const [isLoadingOutages, setIsLoadingOutages] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [outageReason, setOutageReason] = useState<string>('Antenna Azimuth Motor Maintenance');
  const [outageDurationHours, setOutageDurationHours] = useState<number>(4);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Fetch outages from backend
  const fetchOutages = useCallback(async () => {
    try {
      setIsLoadingOutages(true);
      const data = await listOutages({ dataset_id: datasetId });
      setOutages(data);
    } catch {
      // Backend may not have outages or in mock mode
    } finally {
      setIsLoadingOutages(false);
    }
  }, [datasetId]);

  useEffect(() => {
    fetchOutages();
  }, [fetchOutages]);

  const activeOutagesMap = outages.reduce<Record<string, OutageRead>>((acc, o) => {
    if (o.status === 'active') {
      acc[o.station_id] = o;
    }
    return acc;
  }, {});

  const handleDeclareOutage = async () => {
    if (!selectedStationId) return;
    try {
      setIsSubmitting(true);
      setActionError(null);
      setActionMessage(null);

      const now = new Date();
      const end = new Date(now.getTime() + outageDurationHours * 60 * 60 * 1000);

      const res = await createOutage({
        station_id: selectedStationId,
        dataset_id: datasetId,
        start_time: now.toISOString(),
        end_time: end.toISOString(),
        reason: outageReason,
        auto_reoptimize: true,
      });

      setActionMessage(res.message);
      await fetchOutages();

      if (res.reoptimized_schedule && onScheduleUpdate) {
        onScheduleUpdate(res.reoptimized_schedule);
      }
    } catch (err) {
      setActionError(getApiErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResolveOutage = async (outageId: string) => {
    try {
      setIsSubmitting(true);
      setActionError(null);
      setActionMessage(null);

      const res = await resolveOutage(outageId, true);
      setActionMessage(res.message);
      await fetchOutages();

      if (res.reoptimized_schedule && onScheduleUpdate) {
        onScheduleUpdate(res.reoptimized_schedule);
      }
    } catch (err) {
      setActionError(getApiErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  // Utilization map from active run
  const utilMap = activeRun?.metrics.ground_station_utilization || {};

  // Count scheduled passes per station
  const stationPassCountMap: Record<string, number> = {};
  activeRun?.scheduled_passes.forEach((p) => {
    stationPassCountMap[p.ground_station_id] =
      (stationPassCountMap[p.ground_station_id] || 0) + 1;
  });

  return (
    <div className="space-y-6">
      {/* World Coverage Radar Projection Map */}
      <WorldCoverageMap
        stations={stations}
        activeStationId={selectedStationId}
        onSelectStation={(id) => setSelectedStationId(id)}
      />

      {/* Outage Action Feedback Banner */}
      {actionMessage && (
        <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-between text-xs text-emerald-300">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{actionMessage}</span>
          </div>
          <button
            onClick={() => setActionMessage(null)}
            className="text-emerald-400 hover:text-emerald-200 font-bold"
          >
            ✕
          </button>
        </div>
      )}

      {actionError && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-center justify-between text-xs text-rose-300">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{actionError}</span>
          </div>
          <button
            onClick={() => setActionError(null)}
            className="text-rose-400 hover:text-rose-200 font-bold"
          >
            ✕
          </button>
        </div>
      )}

      {/* Ground Station Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {stations.map((station) => {
          const isSelected = selectedStationId === station.station_id;
          const utilization = utilMap[station.station_id] ?? 0;
          const scheduledCount = stationPassCountMap[station.station_id] ?? 0;
          const activeOutage = activeOutagesMap[station.station_id];

          return (
            <div
              key={station.station_id}
              onClick={() => setSelectedStationId(station.station_id)}
              className={`p-5 rounded-2xl border transition-all cursor-pointer backdrop-blur-sm relative overflow-hidden flex flex-col justify-between ${
                activeOutage
                  ? 'bg-rose-950/20 border-rose-500/50 shadow-lg shadow-rose-500/5'
                  : isSelected
                  ? 'bg-slate-900 border-cyan-500/60 shadow-lg shadow-cyan-500/5'
                  : 'bg-slate-950/60 border-slate-800/80 hover:border-slate-700 hover:bg-slate-900/40'
              }`}
            >
              <div>
                {/* Station Header */}
                <div className="flex items-start justify-between gap-2 mb-3">
                  <div className="flex items-center gap-2">
                    <div
                      className={`p-2 rounded-xl border ${
                        activeOutage
                          ? 'bg-rose-500/20 text-rose-400 border-rose-500/40'
                          : 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20'
                      }`}
                    >
                      {activeOutage ? <AlertTriangle className="w-4 h-4" /> : <Radio className="w-4 h-4" />}
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-slate-100 leading-tight">
                        {station.name}
                      </h4>
                      <p className="text-[11px] font-mono text-cyan-300 mt-0.5">
                        {station.station_id}
                      </p>
                    </div>
                  </div>

                  {activeOutage && (
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase bg-rose-500/20 text-rose-400 border border-rose-500/40 animate-pulse">
                      Outage
                    </span>
                  )}
                </div>

                {/* Coordinates & Elevation */}
                <div className="space-y-2 text-xs py-2 border-y border-slate-800/80 text-slate-300">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Coordinates:</span>
                    <span className="font-mono text-slate-200">
                      {station.latitude_deg > 0 ? `${station.latitude_deg.toFixed(2)}°N` : `${Math.abs(station.latitude_deg).toFixed(2)}°S`},{' '}
                      {station.longitude_deg > 0 ? `${station.longitude_deg.toFixed(2)}°E` : `${Math.abs(station.longitude_deg).toFixed(2)}°W`}
                    </span>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Elevation Mask:</span>
                    <span className="font-mono font-medium text-emerald-400">
                      {station.elevation_mask_deg || 5.0}° min
                    </span>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Max Concurrent:</span>
                    <span className="font-mono text-slate-200">
                      {station.max_concurrent_passes || 1} antenna
                    </span>
                  </div>
                </div>

                {/* Outage Details if Active */}
                {activeOutage && (
                  <div className="mt-3 p-2 rounded-lg bg-rose-950/40 border border-rose-800/40 text-[11px] text-rose-300 space-y-1">
                    <div className="font-semibold flex items-center gap-1 text-rose-200">
                      <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
                      <span>{activeOutage.reason}</span>
                    </div>
                    <div className="text-[10px] text-slate-400">
                      Ends: {new Date(activeOutage.end_time).toLocaleTimeString()}
                    </div>
                  </div>
                )}

                {/* Supported Bands */}
                <div className="my-3">
                  <span className="text-[10px] text-slate-400 uppercase tracking-wider block mb-1.5 font-semibold">
                    Supported Frequency Bands
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {(station.supported_bands || ['S-band', 'X-band']).map((band) => (
                      <span
                        key={band}
                        className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-slate-900 text-cyan-300 border border-slate-700/80"
                      >
                        {band}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Station Utilization Gauge */}
              <div className="mt-4 pt-3 border-t border-slate-800/80">
                <div className="flex items-center justify-between text-xs mb-1.5">
                  <span className="text-slate-400">Station Active Duty</span>
                  <span className="font-mono font-bold text-cyan-400">
                    {utilization.toFixed(1)}%
                  </span>
                </div>
                <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                  <div
                    className="bg-gradient-to-r from-cyan-500 to-indigo-500 h-1.5 rounded-full transition-all duration-500"
                    style={{ width: `${Math.min(100, utilization)}%` }}
                  />
                </div>
                <div className="mt-2 text-[11px] text-slate-400 flex items-center justify-between">
                  <span>Assigned Downlinks</span>
                  <span className="font-semibold text-slate-200">{scheduledCount} passes</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Outage Management & Event-Driven Re-optimization Panel */}
      <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 backdrop-blur-sm space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <Wrench className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-100">
                Ground Station Outage & Event-Driven Rescheduling Control
              </h3>
              <p className="text-xs text-slate-400">
                Simulate antenna hardware failure, maintenance, or severe weather to trigger automatic safe re-optimization.
              </p>
            </div>
          </div>
          <button
            onClick={fetchOutages}
            disabled={isLoadingOutages}
            className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition text-xs flex items-center gap-1.5"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoadingOutages ? 'animate-spin' : ''}`} />
            <span>Refresh Outages</span>
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
          <div>
            <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
              Target Ground Station
            </label>
            <select
              value={selectedStationId}
              onChange={(e) => setSelectedStationId(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
            >
              {stations.map((s) => (
                <option key={s.station_id} value={s.station_id}>
                  {s.name} ({s.station_id})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
              Outage Reason / Type
            </label>
            <input
              type="text"
              value={outageReason}
              onChange={(e) => setOutageReason(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
              placeholder="e.g. Dish Gearbox Maintenance"
            />
          </div>

          <div>
            <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
              Duration (Hours)
            </label>
            <div className="flex items-center gap-2">
              <select
                value={outageDurationHours}
                onChange={(e) => setOutageDurationHours(Number(e.target.value))}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
              >
                <option value={1}>1 Hour</option>
                <option value={2}>2 Hours</option>
                <option value={4}>4 Hours</option>
                <option value={8}>8 Hours</option>
                <option value={24}>24 Hours</option>
              </select>
              <button
                onClick={handleDeclareOutage}
                disabled={isSubmitting || !selectedStationId}
                className="px-4 py-2 rounded-xl bg-gradient-to-r from-amber-500 to-rose-600 hover:from-amber-400 hover:to-rose-500 text-slate-950 font-bold text-xs whitespace-nowrap transition shadow-lg shadow-amber-500/10 disabled:opacity-50"
              >
                {isSubmitting ? 'Optimizing...' : 'Trigger Outage'}
              </button>
            </div>
          </div>
        </div>

        {/* Active Outages Table */}
        {outages.length > 0 && (
          <div className="mt-4 pt-4 border-t border-slate-800/80">
            <h4 className="text-xs font-bold text-slate-300 mb-2">Registered Outages</h4>
            <div className="space-y-2">
              {outages.map((o) => (
                <div
                  key={o.id}
                  className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between text-xs"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                        o.status === 'active'
                          ? 'bg-rose-500/20 text-rose-400 border border-rose-500/40'
                          : 'bg-slate-800 text-slate-400'
                      }`}
                    >
                      {o.status}
                    </span>
                    <div>
                      <span className="font-semibold text-slate-200">{o.station_id}</span>
                      <span className="text-slate-400 ml-2">— {o.reason}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <span className="text-[11px] text-slate-400 font-mono">
                      {new Date(o.start_time).toLocaleTimeString()} – {new Date(o.end_time).toLocaleTimeString()}
                    </span>
                    {o.status === 'active' && (
                      <button
                        onClick={() => handleResolveOutage(o.id)}
                        disabled={isSubmitting}
                        className="px-3 py-1 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 text-[11px] font-semibold transition"
                      >
                        Resolve & Restore
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
