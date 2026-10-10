import React, { useState } from 'react';
import {
  CalendarClock,
  Radio,
  Satellite,
} from 'lucide-react';
import type { ScheduleRunResponse, GroundStation } from '../../types/api';
import { EmptyState } from '../common/EmptyState';

interface ScheduleTimelineProps {
  activeRun: ScheduleRunResponse | null;
  groundStations: GroundStation[];
  setupTimeSeconds?: number;
}

export const ScheduleTimeline: React.FC<ScheduleTimelineProps> = ({
  activeRun,
  groundStations,
  setupTimeSeconds = 60,
}) => {
  const [hoveredPassId, setHoveredPassId] = useState<string | null>(null);

  if (!activeRun || activeRun.scheduled_passes.length === 0) {
    return (
      <EmptyState
        title="No Timeline Passes Scheduled"
        description="Run the CP-SAT Optimizer or FCFS Baseline to generate an orbital contact timeline."
      />
    );
  }

  const scheduledPasses = activeRun.scheduled_passes;

  // Determine global time span (minStart and maxEnd) in ms
  const timeTimestamps = scheduledPasses.flatMap((p) => [
    new Date(p.start_time).getTime(),
    new Date(p.end_time).getTime(),
  ]);

  const minTime = Math.min(...timeTimestamps);
  const maxTime = Math.max(...timeTimestamps);
  // Add 10-minute padding on each side for aesthetic spacing
  const paddingMs = 10 * 60 * 1000;
  const timelineStart = minTime - paddingMs;
  const timelineEnd = maxTime + paddingMs;
  const totalDurationMs = Math.max(1, timelineEnd - timelineStart);

  // Dynamically determine tick interval based on total duration to keep marks neat
  let tickIntervalMs = 30 * 60 * 1000; // default 30 min
  const hoursDuration = totalDurationMs / (1000 * 60 * 60);
  
  if (hoursDuration > 24 * 3) {
    tickIntervalMs = 24 * 60 * 60 * 1000; // 1 day
  } else if (hoursDuration > 24) {
    tickIntervalMs = 12 * 60 * 60 * 1000; // 12 hours
  } else if (hoursDuration > 12) {
    tickIntervalMs = 2 * 60 * 60 * 1000; // 2 hours
  } else if (hoursDuration > 6) {
    tickIntervalMs = 60 * 60 * 1000; // 1 hour
  } else if (hoursDuration < 2) {
    tickIntervalMs = 15 * 60 * 1000; // 15 mins
  }

  const ticks: number[] = [];
  let currentTick = Math.ceil(timelineStart / tickIntervalMs) * tickIntervalMs;
  while (currentTick <= timelineEnd) {
    ticks.push(currentTick);
    currentTick += tickIntervalMs;
  }

  // Group passes by ground station
  const stationIds = Array.from(
    new Set([
      ...groundStations.map((gs) => gs.station_id),
      ...scheduledPasses.map((p) => p.ground_station_id),
    ])
  );

  const getPriorityColor = (priority: number) => {
    switch (priority) {
      case 1:
        return 'from-rose-500/80 to-rose-600/80 border-rose-400 text-rose-100 shadow-rose-900/30';
      case 2:
        return 'from-orange-500/80 to-orange-600/80 border-orange-400 text-orange-100 shadow-orange-900/30';
      case 3:
        return 'from-amber-500/80 to-amber-600/80 border-amber-400 text-amber-100 shadow-amber-900/30';
      case 4:
        return 'from-cyan-500/80 to-cyan-600/80 border-cyan-400 text-cyan-100 shadow-cyan-900/30';
      default:
        return 'from-slate-600/80 to-slate-700/80 border-slate-500 text-slate-200 shadow-slate-900/30';
    }
  };

  return (
    <div className="space-y-4">
      {/* Timeline Controls & Legend */}
      <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 backdrop-blur-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <CalendarClock className="w-4 h-4 text-cyan-400" />
            <h3 className="text-sm font-bold text-slate-100">
              Ground Station Contact Schedule (Gantt Projection)
            </h3>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Active Algorithm: <strong className="text-cyan-300 font-mono">{activeRun.algorithm}</strong>{' '}
            ({scheduledPasses.length} contact windows, {setupTimeSeconds}s antenna slew constraint)
          </p>
        </div>

        {/* Priority Color Legend */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="text-slate-400 text-[11px] font-semibold uppercase">Priority:</span>
          <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30 text-[11px]">
            P1 Critical
          </span>
          <span className="px-2 py-0.5 rounded bg-orange-500/20 text-orange-300 border border-orange-500/30 text-[11px]">
            P2 High
          </span>
          <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[11px]">
            P3 Medium
          </span>
          <span className="px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 text-[11px]">
            P4/P5 Low
          </span>
        </div>
      </div>

      {/* Gantt Interactive Chart Container */}
      <div className="rounded-xl border border-slate-800 bg-slate-950/80 backdrop-blur-sm overflow-x-auto p-4">
        <div className="min-w-[760px]">
          {/* Time scale header */}
          <div className="flex border-b border-slate-800 pb-2 mb-4 text-xs font-mono text-slate-400">
            <div className="w-48 shrink-0 font-sans font-semibold text-slate-300 flex items-center gap-1.5">
              <Radio className="w-3.5 h-3.5 text-cyan-400" />
              <span>Ground Station</span>
            </div>
            <div className="relative flex-1 h-6">
              {ticks.map((tick) => {
                const leftPercent = ((tick - timelineStart) / totalDurationMs) * 100;
                return (
                  <div
                    key={tick}
                    className="absolute -translate-x-1/2 flex flex-col items-center"
                    style={{ left: `${leftPercent}%` }}
                  >
                    <span className="text-[10px] text-slate-400 bg-slate-950/80 px-1 rounded backdrop-blur-sm z-10 whitespace-nowrap">
                      {hoursDuration > 24 ? new Date(tick).toISOString().substring(5, 16).replace('T', ' ') : new Date(tick).toISOString().substring(11, 16)} UTC
                    </span>
                    <div className="w-px h-2 bg-slate-700 mt-1" />
                  </div>
                );
              })}
            </div>
          </div>

          {/* Station Rows */}
          <div className="space-y-4">
            {stationIds.map((stationId) => {
              const stationPasses = scheduledPasses.filter(
                (p) => p.ground_station_id === stationId
              );

              return (
                <div key={stationId} className="flex items-center group">
                  {/* Station Label */}
                  <div className="w-48 shrink-0 pr-4">
                    <div className="font-semibold text-xs text-slate-200 truncate">
                      {stationId}
                    </div>
                    <div className="text-[11px] text-slate-500">
                      {stationPasses.length} scheduled pass{stationPasses.length === 1 ? '' : 'es'}
                    </div>
                  </div>

                  {/* Track Bar with passes */}
                  <div className="relative flex-1 h-14 bg-slate-900/80 rounded-xl border border-slate-800/80 p-1 flex items-center">
                    {/* Background grid line markers */}
                    {ticks.map((tick) => {
                      const leftPercent = ((tick - timelineStart) / totalDurationMs) * 100;
                      return (
                        <div
                          key={tick}
                          className="absolute top-0 bottom-0 w-px bg-slate-800/50 pointer-events-none"
                          style={{ left: `${leftPercent}%` }}
                        />
                      );
                    })}

                    {/* Scheduled Pass Blocks */}
                    {stationPasses.map((p) => {
                      const startMs = new Date(p.start_time).getTime();
                      const endMs = new Date(p.end_time).getTime();
                      const leftPercent = ((startMs - timelineStart) / totalDurationMs) * 100;
                      const widthPercent = Math.max(
                        3.5,
                        ((endMs - startMs) / totalDurationMs) * 100
                      );

                      const isHovered = hoveredPassId === p.pass_id;

                      return (
                        <div
                          key={p.pass_id}
                          onMouseEnter={() => setHoveredPassId(p.pass_id)}
                          onMouseLeave={() => setHoveredPassId(null)}
                          className={`absolute h-10 rounded-lg border bg-gradient-to-r ${getPriorityColor(
                            p.priority
                          )} px-2 py-1 text-[11px] font-mono cursor-pointer transition-all flex flex-col justify-center shadow-md select-none ${isHovered ? 'ring-2 ring-cyan-300 z-20 scale-[1.02]' : 'z-10'
                            }`}
                          style={{
                            left: `${leftPercent}%`,
                            width: `${widthPercent}%`,
                          }}
                        >
                          <div className="truncate font-bold flex items-center gap-1">
                            <span>{p.satellite_id}</span>
                          </div>
                          <div className="text-[10px] opacity-90 truncate">
                            {p.transferable_data_gb.toFixed(1)} GB · {p.duration_seconds}s
                          </div>

                          {/* Hover Tooltip Popup */}
                          {isHovered && (
                            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-56 rounded-xl bg-slate-900 border border-slate-700 p-3 shadow-2xl z-30 pointer-events-none text-left font-sans text-xs">
                              <div className="font-bold text-slate-100 flex items-center gap-1.5 mb-1">
                                <Satellite className="w-3.5 h-3.5 text-cyan-400" />
                                <span>{p.pass_id}</span>
                              </div>
                              <div className="space-y-1 text-[11px] text-slate-300">
                                <div>Sat: <span className="font-semibold text-slate-100">{p.satellite_id}</span></div>
                                <div>Window: {new Date(p.start_time).toISOString().substring(11, 16)} - {new Date(p.end_time).toISOString().substring(11, 16)} UTC</div>
                                <div>Duration: <span className="font-mono">{p.duration_seconds}s</span></div>
                                <div>Transfer: <span className="font-mono text-cyan-300 font-semibold">{p.transferable_data_gb.toFixed(1)} GB</span></div>
                                <div className="text-emerald-400 font-medium">Priority P{p.priority} Scheduled</div>
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
