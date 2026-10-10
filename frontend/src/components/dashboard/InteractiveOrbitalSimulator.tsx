import React, { useState, useEffect, useMemo } from 'react';
import { 
  Play, Pause, RotateCcw, FastForward, 
  AlertTriangle, Satellite, Activity, ShieldCheck,
  Radio, Compass, Signal
} from 'lucide-react';
import type { Dataset, ScheduleRunResponse } from '../../types/api';

interface SimulatorProps {
  activeDataset: Dataset;
  activeRun: ScheduleRunResponse | null;
  onRunOptimizer?: () => void;
}

export const InteractiveOrbitalSimulator: React.FC<SimulatorProps> = ({ 
  activeDataset, 
  activeRun,
  onRunOptimizer 
}) => {
  const passes = useMemo(() => activeDataset.satellite_passes || [], [activeDataset]);
  const groundStations = useMemo(() => activeDataset.ground_stations || [], [activeDataset]);
  
  // Set of scheduled pass IDs in the active run
  const scheduledPassIds = useMemo(
    () => new Set(activeRun?.scheduled_passes.map(p => p.pass_id) || []),
    [activeRun]
  );

  // Time boundaries of the dataset
  const { minTime, maxTime } = useMemo(() => {
    if (passes.length === 0) {
      const now = Date.now();
      return { minTime: now, maxTime: now + 3600000 };
    }
    const starts = passes.map(p => new Date(p.start_time).getTime());
    const ends = passes.map(p => new Date(p.end_time).getTime());
    return {
      minTime: Math.min(...starts),
      maxTime: Math.max(...ends),
    };
  }, [passes]);

  // Simulation Clock state
  const [simTimeMs, setSimTimeMs] = useState<number>(minTime);
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const [speedMultiplier, setSpeedMultiplier] = useState<number>(120); // 1 real sec = 120 sim sec
  const [showEmergencyModal, setShowEmergencyModal] = useState<boolean>(false);
  
  // Selected entity for interactive telemetry inspection
  const [selectedSatId, setSelectedSatId] = useState<string | null>(null);
  const [selectedStationId, setSelectedStationId] = useState<string | null>(null);

  // Unique satellites and stations derived strictly from dataset
  const uniqueSatellites = useMemo(() => {
    return Array.from(new Set(passes.map(p => p.satellite_id)));
  }, [passes]);

  const uniqueStations = useMemo(() => {
    if (groundStations.length > 0) {
      return groundStations.map(gs => gs.station_id);
    }
    return Array.from(new Set(passes.map(p => p.ground_station_id)));
  }, [groundStations, passes]);

  // Reset clock whenever selected dataset changes
  useEffect(() => {
    if (passes.length > 0) {
      // Start 1 minute before the first pass for smooth lead-in
      setSimTimeMs(minTime - 60 * 1000);
      setSelectedSatId(uniqueSatellites[0] || null);
      setSelectedStationId(uniqueStations[0] || null);
    }
  }, [activeDataset.dataset_id, minTime, passes.length, uniqueSatellites, uniqueStations]);

  // Animation Loop
  useEffect(() => {
    let animationFrame: number;
    let lastTime = performance.now();

    const loop = (time: number) => {
      const delta = time - lastTime;
      lastTime = time;

      if (isPlaying && maxTime > minTime) {
        setSimTimeMs(prev => {
          let next = prev + (delta * speedMultiplier);
          if (next > maxTime + 60 * 1000) {
            next = minTime - 60 * 1000;
          }
          return next;
        });
      }
      animationFrame = requestAnimationFrame(loop);
    };

    animationFrame = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(animationFrame);
  }, [isPlaying, speedMultiplier, minTime, maxTime]);

  const togglePlay = () => setIsPlaying(!isPlaying);
  const restart = () => setSimTimeMs(minTime - 60 * 1000);

  // Active opportunities at current sim time
  const activeOpportunities = useMemo(() => {
    return passes.filter(p => {
      const s = new Date(p.start_time).getTime();
      const e = new Date(p.end_time).getTime();
      return simTimeMs >= s && simTimeMs <= e;
    });
  }, [passes, simTimeMs]);

  // Upcoming passes within next 30 minutes of sim clock
  const upcomingOpportunities = useMemo(() => {
    return passes
      .filter(p => {
        const s = new Date(p.start_time).getTime();
        return s > simTimeMs && s <= simTimeMs + 30 * 60 * 1000;
      })
      .sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime());
  }, [passes, simTimeMs]);

  const getPriorityBgColor = (prio: number) => {
    switch (prio) {
      case 1: return 'bg-rose-500';
      case 2: return 'bg-orange-500';
      case 3: return 'bg-amber-500';
      default: return 'bg-cyan-500';
    }
  };

  // Station geometric positioning based on dataset coordinates or uniform globe distribution
  const getStationPosition = (gsId: string, index: number, total: number) => {
    const gs = groundStations.find(s => s.station_id === gsId);
    const r = 160; // Earth globe surface radius in canvas coords
    if (gs && typeof gs.latitude_deg === 'number' && typeof gs.longitude_deg === 'number') {
      // Cylindrical projection onto 2D circular globe profile
      const latRad = (gs.latitude_deg * Math.PI) / 180;
      const lonRad = (gs.longitude_deg * Math.PI) / 180;
      const x = Math.sin(lonRad) * Math.cos(latRad) * r * 0.95;
      const y = -Math.sin(latRad) * r * 0.85 + 20; // slight perspective tilt
      return { x, y };
    }
    // Fallback: Uniform distribution on lower globe arc
    const angle = (Math.PI / 4) + (Math.PI / 2) * (index / Math.max(1, total - 1));
    return { x: Math.cos(angle) * r, y: Math.sin(angle) * r };
  };

  // Orbit parameters for each satellite
  const getSatellitePosition = (index: number, total: number) => {
    const r = 240 + (index * 32); // Orbital altitude radii
    const speed = 0.000002 + (index * 0.0000004);
    const baseAngle = (index * Math.PI * 2) / Math.max(1, total);
    const currentAngle = baseAngle + ((simTimeMs - minTime) * speed);
    return { 
      x: Math.cos(currentAngle) * r, 
      y: Math.sin(currentAngle) * r * 0.85, // slight elliptical inclination
      radius: r 
    };
  };

  // Currently selected satellite's telemetry details
  const activeSatData = useMemo(() => {
    if (!selectedSatId) return null;
    const satPasses = passes.filter(p => p.satellite_id === selectedSatId);
    const nextPass = satPasses.find(p => new Date(p.end_time).getTime() >= simTimeMs) || satPasses[0];
    const totalSatVolume = satPasses.reduce((sum, p) => sum + p.data_volume_gb, 0);
    const highestPriority = satPasses.length ? Math.min(...satPasses.map(p => p.priority)) : 3;
    const isCurrentlyDownlinking = activeOpportunities.some(p => p.satellite_id === selectedSatId);
    const scheduledInRun = satPasses.filter(p => scheduledPassIds.has(p.pass_id));

    return {
      satId: selectedSatId,
      passCount: satPasses.length,
      totalVolumeGb: totalSatVolume,
      highestPriority,
      nextPass,
      isCurrentlyDownlinking,
      scheduledCount: scheduledInRun.length,
      channelBand: nextPass?.channel_band || 'X-band',
      dataRateMbps: nextPass?.effective_data_rate_mbps || 350,
      maxElevationDeg: nextPass?.max_elevation_deg || 65.0,
    };
  }, [selectedSatId, passes, simTimeMs, activeOpportunities, scheduledPassIds]);

  // Currently selected ground station details
  const activeStationData = useMemo(() => {
    if (!selectedStationId) return null;
    const gs = groundStations.find(s => s.station_id === selectedStationId);
    const stationPasses = passes.filter(p => p.ground_station_id === selectedStationId);
    const stationScheduled = stationPasses.filter(p => scheduledPassIds.has(p.pass_id));
    const activePass = activeOpportunities.find(p => p.ground_station_id === selectedStationId);

    return {
      stationId: selectedStationId,
      name: gs?.name || selectedStationId,
      lat: gs?.latitude_deg ?? 0,
      lon: gs?.longitude_deg ?? 0,
      elevationMask: gs?.elevation_mask_deg ?? 5.0,
      supportedBands: gs?.supported_bands || ['S-band', 'X-band'],
      totalPasses: stationPasses.length,
      scheduledPasses: stationScheduled.length,
      isActive: Boolean(activePass),
      activePass,
    };
  }, [selectedStationId, groundStations, passes, scheduledPassIds, activeOpportunities]);

  if (passes.length === 0) {
    return (
      <div className="w-full p-8 rounded-2xl bg-slate-900/60 border border-slate-800 text-center">
        <Activity className="w-8 h-8 text-indigo-400 mx-auto mb-2 animate-pulse" />
        <h3 className="text-sm font-bold text-slate-200">No Orbital Passes in Scenario</h3>
        <p className="text-xs text-slate-400 mt-1">Select a benchmark dataset to visualize satellite orbits and real-time antenna links.</p>
      </div>
    );
  }

  return (
    <div className="w-full flex flex-col gap-4 mb-6">
      {/* Simulator Mission Header */}
      <div className="p-4 rounded-2xl bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 border border-indigo-500/30 backdrop-blur-md flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-indigo-500/10 border border-indigo-500/30 text-indigo-400">
            <Activity className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-slate-100">{activeDataset.name}</h2>
              <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-[10px] font-mono font-semibold">
                {uniqueSatellites.length} SATS · {uniqueStations.length} STATIONS · {passes.length} PASSES
              </span>
            </div>
            <p className="text-xs text-slate-300 mt-0.5 max-w-2xl">
              Real-time dynamic visualization of orbital visibility windows and OR-Tools CP-SAT antenna allocations.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button 
            onClick={() => setShowEmergencyModal(true)}
            className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 border border-rose-500/40 text-xs font-semibold shadow-lg shadow-rose-950/30 transition"
          >
            <AlertTriangle className="w-4 h-4 text-rose-400" />
            <span>Inject P1 Emergency Task</span>
          </button>
        </div>
      </div>

      {/* Main Canvas & HUD Container */}
      <div className="relative w-full h-[640px] rounded-3xl overflow-hidden border border-indigo-500/30 shadow-2xl bg-[#020617] flex flex-col lg:flex-row">
        {/* Deep space starfield canvas bg */}
        <div className="absolute inset-0 z-0 pointer-events-none">
          <div className="stars absolute inset-0 opacity-60"></div>
          <div className="twinkling absolute inset-0 opacity-40"></div>
          <div className="absolute top-0 -left-1/4 w-[150%] h-[150%] bg-gradient-radial from-indigo-950/30 via-slate-950/10 to-transparent blur-3xl opacity-70"></div>
        </div>

        {/* Left Panel: Active Contact Opportunities & Priority Evaluation */}
        <div className="relative z-30 w-full lg:w-[310px] h-auto lg:h-full bg-slate-950/70 backdrop-blur-md border-b lg:border-b-0 lg:border-r border-slate-800/80 p-4 flex flex-col overflow-y-auto custom-scrollbar">
          <div className="flex items-center justify-between mb-3 border-b border-slate-800 pb-2">
            <div className="flex items-center gap-1.5 text-xs font-bold text-slate-200 uppercase tracking-wider">
              <Signal className="w-3.5 h-3.5 text-indigo-400" />
              <span>Contact Windows</span>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300">
              {activeOpportunities.length} Active
            </span>
          </div>

          <div className="space-y-2.5 flex-1">
            {activeOpportunities.length === 0 && (
              <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800 text-center space-y-1 my-2">
                <Compass className="w-5 h-5 text-slate-500 mx-auto animate-spin" style={{ animationDuration: '8s' }} />
                <div className="text-xs text-slate-400 font-semibold">No active downlinks at this second</div>
                <div className="text-[10px] text-slate-500">Fast-forward clock to next window</div>
              </div>
            )}

            {/* List Active Passes */}
            {activeOpportunities.map(pass => {
              const isScheduled = scheduledPassIds.has(pass.pass_id);
              const isSelected = selectedSatId === pass.satellite_id;

              return (
                <div 
                  key={`act-${pass.pass_id}`}
                  onClick={() => {
                    setSelectedSatId(pass.satellite_id);
                    setSelectedStationId(pass.ground_station_id);
                  }}
                  className={`p-3 rounded-xl border transition-all cursor-pointer ${
                    isSelected ? 'ring-2 ring-indigo-500 shadow-lg' : ''
                  } ${
                    isScheduled 
                      ? 'bg-emerald-950/20 border-emerald-500/40 text-emerald-200' 
                      : 'bg-amber-950/20 border-amber-500/40 text-amber-200'
                  }`}
                >
                  <div className="flex justify-between items-center mb-1.5">
                    <span className="font-mono text-xs font-bold text-slate-100 flex items-center gap-1">
                      <Satellite className="w-3.5 h-3.5 text-indigo-400" />
                      {pass.satellite_id}
                    </span>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold text-white shadow-sm ${getPriorityBgColor(pass.priority)}`}>
                      P{pass.priority}
                    </span>
                  </div>

                  <div className="text-[11px] text-slate-300 space-y-1 mb-2">
                    <div className="flex justify-between">
                      <span className="text-slate-400">Target Station:</span>
                      <span className="font-mono text-slate-200">{pass.ground_station_id}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Data Payload:</span>
                      <span className="font-mono font-semibold text-cyan-300">{pass.data_volume_gb.toFixed(1)} GB</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Bandwidth:</span>
                      <span className="font-mono text-slate-300">{pass.effective_data_rate_mbps || 350} Mbps</span>
                    </div>
                  </div>

                  <div className="pt-1.5 border-t border-slate-800 flex items-center justify-between text-[10px] font-semibold">
                    <span className="text-slate-400">Allocation:</span>
                    {isScheduled ? (
                      <span className="inline-flex items-center gap-1 text-emerald-400 font-mono">
                        <ShieldCheck className="w-3.5 h-3.5" /> CP-SAT SCHEDULED
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-amber-400 font-mono">
                        <AlertTriangle className="w-3.5 h-3.5" /> CONTENTION PREEMPTED
                      </span>
                    )}
                  </div>
                </div>
              );
            })}

            {/* Upcoming Timeline Feed */}
            {upcomingOpportunities.length > 0 && (
              <div className="pt-3">
                <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">
                  Upcoming Passes (Next 30m)
                </div>
                <div className="space-y-1.5">
                  {upcomingOpportunities.slice(0, 3).map(p => (
                    <div 
                      key={`up-${p.pass_id}`}
                      onClick={() => setSelectedSatId(p.satellite_id)}
                      className="p-2 rounded-lg bg-slate-900/60 border border-slate-800 hover:border-slate-700 text-[11px] text-slate-300 flex items-center justify-between cursor-pointer transition"
                    >
                      <div>
                        <div className="font-mono font-semibold text-slate-200">{p.satellite_id}</div>
                        <div className="text-[10px] text-slate-400">{p.ground_station_id} · P{p.priority}</div>
                      </div>
                      <span className="text-[10px] font-mono text-indigo-300">
                        {new Date(p.start_time).toISOString().substring(11, 16)} UTC
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Central Visualization Canvas */}
        <div className="relative flex-1 h-[400px] lg:h-full flex items-center justify-center overflow-hidden">
          <div className="relative w-[560px] h-[560px] flex items-center justify-center">
            {/* SVG Layer for Orbits and Downlink Beams */}
            <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox="-280 -280 560 560">
              <defs>
                <linearGradient id="beamScheduled" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#22d3ee" stopOpacity="0.9" />
                  <stop offset="100%" stopColor="#10b981" stopOpacity="0.9" />
                </linearGradient>
                <linearGradient id="beamEmergency" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#f43f5e" stopOpacity="1" />
                  <stop offset="100%" stopColor="#fb7185" stopOpacity="0.8" />
                </linearGradient>
              </defs>

              {/* Orbit Rings */}
              {uniqueSatellites.map((sat, i) => {
                const pos = getSatellitePosition(i, uniqueSatellites.length);
                const isSelected = selectedSatId === sat;
                return (
                  <ellipse 
                    key={`orbit-${sat}`} 
                    cx="0" 
                    cy="0" 
                    rx={pos.radius} 
                    ry={pos.radius * 0.85} 
                    fill="none" 
                    stroke={isSelected ? "rgba(99, 102, 241, 0.5)" : "rgba(99, 102, 241, 0.18)"} 
                    strokeWidth={isSelected ? "1.5" : "1"} 
                    strokeDasharray={isSelected ? "6 3" : "4 4"} 
                  />
                );
              })}

              {/* Active Downlink Beams */}
              {activeOpportunities.map(pass => {
                const isScheduled = scheduledPassIds.has(pass.pass_id);
                const satIdx = uniqueSatellites.indexOf(pass.satellite_id);
                const gsIdx = uniqueStations.indexOf(pass.ground_station_id);
                
                if (satIdx === -1 || gsIdx === -1) return null;

                const satPos = getSatellitePosition(satIdx, uniqueSatellites.length);
                const gsPos = getStationPosition(pass.ground_station_id, gsIdx, uniqueStations.length);

                return (
                  <g key={`beam-${pass.pass_id}`}>
                    {/* Pulsing beam line */}
                    <line 
                      x1={satPos.x} y1={satPos.y} 
                      x2={gsPos.x} y2={gsPos.y} 
                      stroke={
                        isScheduled 
                          ? (pass.priority === 1 ? 'url(#beamEmergency)' : 'url(#beamScheduled)')
                          : '#f59e0b'
                      } 
                      strokeWidth={isScheduled ? (pass.priority === 1 ? "3" : "2.5") : "1.5"}
                      strokeDasharray={isScheduled ? "8 4" : "4 4"}
                      opacity={isScheduled ? 0.95 : 0.5}
                      className={isScheduled ? "animate-[scanline_1s_linear_infinite]" : ""}
                    />

                    {/* Ground station signal ping */}
                    {isScheduled && (
                      <circle 
                        cx={gsPos.x} 
                        cy={gsPos.y} 
                        r="18" 
                        fill="none" 
                        stroke={pass.priority === 1 ? '#f43f5e' : '#10b981'} 
                        className="animate-ping opacity-60" 
                      />
                    )}
                  </g>
                );
              })}
            </svg>

            {/* Central Earth Globe */}
            <div className="absolute w-[320px] h-[320px] rounded-full overflow-hidden shadow-[0_0_90px_rgba(6,182,212,0.25)] flex items-center justify-center bg-black/60 z-10 border border-cyan-500/20">
              <img 
                src="/earth_globe.png" 
                alt="Earth Globe" 
                className="w-full h-full object-cover opacity-90 drop-shadow-[0_0_20px_rgba(6,182,212,0.7)]" 
              />
              <div className="absolute inset-0 bg-gradient-to-t from-slate-950/40 via-transparent to-cyan-500/10 pointer-events-none"></div>
            </div>

            {/* Ground Stations Pins */}
            {uniqueStations.map((gsId, i) => {
              const pos = getStationPosition(gsId, i, uniqueStations.length);
              const activePass = activeOpportunities.find(p => p.ground_station_id === gsId);
              const isScheduled = activePass && scheduledPassIds.has(activePass.pass_id);
              const isSelected = selectedStationId === gsId;
              const gs = groundStations.find(s => s.station_id === gsId);

              return (
                <div 
                  key={gsId} 
                  onClick={() => setSelectedStationId(gsId)}
                  className="absolute z-20 cursor-pointer group" 
                  style={{ transform: `translate(${pos.x}px, ${pos.y}px)` }}
                >
                  <div className="relative -left-1/2 -top-1/2 flex flex-col items-center">
                    <div className={`w-4 h-4 rounded-full border-2 transition-transform duration-300 group-hover:scale-125 ${
                      isSelected 
                        ? 'ring-2 ring-indigo-400 scale-110' 
                        : ''
                    } ${
                      isScheduled 
                        ? 'bg-emerald-400 border-white shadow-[0_0_16px_#10b981]' 
                        : activePass 
                          ? 'bg-amber-400 border-white shadow-[0_0_12px_#f59e0b]' 
                          : 'bg-slate-800 border-slate-400'
                    }`}>
                      <div className="w-full h-full flex items-center justify-center">
                        <Radio className="w-2.5 h-2.5 text-slate-900" />
                      </div>
                    </div>
                    
                    <div className="mt-1 text-[9px] font-mono whitespace-nowrap bg-slate-950/90 border border-slate-800 px-1.5 py-0.5 rounded shadow-md text-slate-200">
                      {gs?.name ? gs.name.replace(' Station', '').replace(' Facility', '') : gsId}
                    </div>
                  </div>
                </div>
              );
            })}

            {/* Satellites in Orbit */}
            {uniqueSatellites.map((satId, i) => {
              const pos = getSatellitePosition(i, uniqueSatellites.length);
              const activePass = activeOpportunities.find(p => p.satellite_id === satId);
              const isScheduled = activePass && scheduledPassIds.has(activePass.pass_id);
              const isSelected = selectedSatId === satId;

              return (
                <div 
                  key={satId} 
                  onClick={() => setSelectedSatId(satId)}
                  className="absolute z-30 transition-transform duration-75 cursor-pointer group" 
                  style={{ transform: `translate(${pos.x}px, ${pos.y}px)` }}
                >
                  <div className="relative -left-1/2 -top-1/2">
                    <div className={`w-7 h-7 rounded-lg bg-slate-900 border flex items-center justify-center transition-all ${
                      isSelected 
                        ? 'ring-2 ring-indigo-400 border-indigo-400 shadow-[0_0_20px_rgba(99,102,241,0.8)] scale-110' 
                        : isScheduled 
                          ? 'border-emerald-400 shadow-[0_0_18px_rgba(16,185,129,0.7)]' 
                          : 'border-slate-600 group-hover:border-slate-400'
                    }`}>
                      <Satellite className={`w-4 h-4 ${
                        isScheduled 
                          ? 'text-emerald-400' 
                          : activePass 
                            ? 'text-amber-400' 
                            : 'text-slate-300'
                      }`} />
                    </div>

                    {/* Photovoltaic Solar Panels */}
                    <div className="absolute top-1/2 -translate-y-1/2 -left-3 w-2.5 h-6 bg-blue-600/90 border border-blue-400/80 rounded-sm"></div>
                    <div className="absolute top-1/2 -translate-y-1/2 -right-3 w-2.5 h-6 bg-blue-600/90 border border-blue-400/80 rounded-sm"></div>
                    
                    <div className="absolute top-8 left-1/2 -translate-x-1/2 text-[10px] font-mono whitespace-nowrap bg-slate-950/90 px-1.5 py-0.5 rounded border border-slate-800 text-slate-200 shadow-lg">
                      {satId}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Panel: Telemetry Inspector & Constellation Telemetry */}
        <div className="relative z-30 w-full lg:w-[310px] h-auto lg:h-full bg-slate-950/70 backdrop-blur-md border-t lg:border-t-0 lg:border-l border-slate-800/80 p-4 flex flex-col justify-between overflow-y-auto custom-scrollbar">
          <div>
            <div className="flex items-center justify-between mb-3 border-b border-slate-800 pb-2">
              <div className="flex items-center gap-1.5 text-xs font-bold text-slate-200 uppercase tracking-wider">
                <Compass className="w-3.5 h-3.5 text-cyan-400" />
                <span>Telemetry Inspector</span>
              </div>
              <span className="text-[10px] font-mono text-cyan-400">
                LIVE METRICS
              </span>
            </div>

            {/* Satellite Specific Telemetry */}
            {activeSatData && (
              <div className="space-y-3 mb-4">
                <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-xs font-bold text-slate-100 font-mono">{activeSatData.satId}</span>
                    <span className={`px-2 py-0.5 rounded text-[9px] font-bold text-white ${getPriorityBgColor(activeSatData.highestPriority)}`}>
                      P{activeSatData.highestPriority} TIER
                    </span>
                  </div>

                  <div className="space-y-1.5 text-[11px] text-slate-300">
                    <div className="flex justify-between border-b border-slate-800/60 pb-1">
                      <span className="text-slate-400">Scenario Passes:</span>
                      <span className="font-mono text-slate-100">{activeSatData.passCount} passes</span>
                    </div>
                    <div className="flex justify-between border-b border-slate-800/60 pb-1">
                      <span className="text-slate-400">Total Payload:</span>
                      <span className="font-mono font-semibold text-cyan-300">{activeSatData.totalVolumeGb.toFixed(1)} GB</span>
                    </div>
                    <div className="flex justify-between border-b border-slate-800/60 pb-1">
                      <span className="text-slate-400">RF Channel:</span>
                      <span className="font-mono text-slate-200">{activeSatData.channelBand}</span>
                    </div>
                    <div className="flex justify-between border-b border-slate-800/60 pb-1">
                      <span className="text-slate-400">Data Link Rate:</span>
                      <span className="font-mono text-slate-200">{activeSatData.dataRateMbps} Mbps</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Max Elevation:</span>
                      <span className="font-mono text-slate-200">{activeSatData.maxElevationDeg.toFixed(1)}°</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Station Specific Telemetry */}
            {activeStationData && (
              <div className="space-y-3">
                <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-xs font-bold text-slate-100">{activeStationData.name}</span>
                    <span className="px-2 py-0.5 rounded text-[9px] font-mono font-semibold bg-indigo-500/20 text-indigo-300">
                      {activeStationData.stationId}
                    </span>
                  </div>

                  <div className="space-y-1.5 text-[11px] text-slate-300">
                    <div className="flex justify-between border-b border-slate-800/60 pb-1">
                      <span className="text-slate-400">Coordinates:</span>
                      <span className="font-mono text-slate-200">
                        {activeStationData.lat.toFixed(1)}°, {activeStationData.lon.toFixed(1)}°
                      </span>
                    </div>
                    <div className="flex justify-between border-b border-slate-800/60 pb-1">
                      <span className="text-slate-400">Supported Bands:</span>
                      <span className="font-mono text-slate-200">{activeStationData.supportedBands.join(', ')}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Elevation Mask:</span>
                      <span className="font-mono text-slate-200">{activeStationData.elevationMask.toFixed(1)}°</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Simulation Clock Bar in Telemetry Panel */}
          <div className="mt-4 p-3 rounded-xl bg-slate-900/90 border border-slate-700/80 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Mission Clock</span>
              <span className="font-mono text-cyan-400 text-xs font-bold">
                {new Date(simTimeMs).toISOString().substring(11, 19)} UTC
              </span>
            </div>

            {/* Clock Scrubber */}
            <div className="space-y-1">
              <input 
                type="range"
                min={minTime - 60 * 1000}
                max={maxTime + 60 * 1000}
                value={simTimeMs}
                onChange={(e) => setSimTimeMs(Number(e.target.value))}
                className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400"
              />
              <div className="flex justify-between text-[9px] text-slate-500 font-mono">
                <span>{new Date(minTime).toISOString().substring(11, 16)} UTC</span>
                <span>{new Date(maxTime).toISOString().substring(11, 16)} UTC</span>
              </div>
            </div>

            {/* Controls */}
            <div className="flex items-center gap-2 pt-1">
              <button 
                onClick={restart} 
                title="Restart Simulation"
                className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>
              
              <button 
                onClick={togglePlay} 
                className="flex-1 py-1.5 flex items-center justify-center gap-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs shadow-md transition"
              >
                {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                <span>{isPlaying ? 'PAUSE' : 'PLAY'}</span>
              </button>

              <button 
                onClick={() => setSpeedMultiplier(s => s === 120 ? 300 : s === 300 ? 600 : 120)} 
                className="px-2 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-cyan-400 font-mono text-[10px] font-bold transition flex items-center gap-1"
              >
                <FastForward className="w-3 h-3" />
                <span>{speedMultiplier}x</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Emergency Injection Modal */}
      {showEmergencyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-rose-500/50 rounded-2xl max-w-lg w-full p-6 shadow-2xl relative space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-rose-500/20 text-rose-400 border border-rose-500/40">
                <AlertTriangle className="w-6 h-6 animate-pulse" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-100">Disaster Emergency Task Injection</h3>
                <p className="text-xs text-rose-300">Evaluate Preemption & Constraint Optimization</p>
              </div>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              Injecting an emergency Priority 1 downlink request simulates urgent wildfire/flood satellite telemetry competing with routine passes. 
              The Google OR-Tools CP-SAT solver will compute a mathematically optimal schedule that preempts lower-priority passes while maximizing overall throughput.
            </p>

            <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 text-xs space-y-1.5 font-mono text-slate-300">
              <div className="flex justify-between">
                <span className="text-slate-400">Target Scenario:</span>
                <span className="text-slate-100 font-bold">{activeDataset.name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Injected Task:</span>
                <span className="text-rose-400 font-bold">EMERGENCY-RAPIDSCAN-P1</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Solver Engine:</span>
                <span className="text-cyan-300 font-bold">OR-Tools CP-SAT (Time limit: 30s)</span>
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => setShowEmergencyModal(false)}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setShowEmergencyModal(false);
                  if (onRunOptimizer) onRunOptimizer();
                }}
                className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold shadow-lg shadow-rose-950/50 transition flex items-center gap-2"
              >
                <ShieldCheck className="w-4 h-4" />
                <span>Execute Optimization Reschedule</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
