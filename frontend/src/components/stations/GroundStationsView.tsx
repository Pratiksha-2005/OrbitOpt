import React, { useState } from 'react';
import { Radio } from 'lucide-react';
import type { GroundStation, ScheduleRunResponse } from '../../types/api';
import { WorldCoverageMap } from './WorldCoverageMap';

interface GroundStationsViewProps {
  stations: GroundStation[];
  activeRun: ScheduleRunResponse | null;
}

export const GroundStationsView: React.FC<GroundStationsViewProps> = ({
  stations,
  activeRun,
}) => {
  const [selectedStationId, setSelectedStationId] = useState<string | undefined>(
    stations[0]?.station_id
  );

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

      {/* Ground Station Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {stations.map((station) => {
          const isSelected = selectedStationId === station.station_id;
          const utilization = utilMap[station.station_id] ?? 0;
          const scheduledCount = stationPassCountMap[station.station_id] ?? 0;

          return (
            <div
              key={station.station_id}
              onClick={() => setSelectedStationId(station.station_id)}
              className={`p-5 rounded-2xl border transition-all cursor-pointer backdrop-blur-sm relative overflow-hidden flex flex-col justify-between ${
                isSelected
                  ? 'bg-slate-900 border-cyan-500/60 shadow-lg shadow-cyan-500/5'
                  : 'bg-slate-950/60 border-slate-800/80 hover:border-slate-700 hover:bg-slate-900/40'
              }`}
            >
              <div>
                {/* Station Header */}
                <div className="flex items-start justify-between gap-2 mb-3">
                  <div className="flex items-center gap-2">
                    <div className="p-2 rounded-xl bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                      <Radio className="w-4 h-4" />
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
    </div>
  );
};
