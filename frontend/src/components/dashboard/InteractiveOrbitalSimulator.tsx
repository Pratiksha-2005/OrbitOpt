import React, { useState, useEffect } from 'react';
import { 
  Play, Pause, RotateCcw, FastForward, 
  AlertTriangle, Satellite, Activity, ShieldCheck 
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
  const passes = activeDataset.satellite_passes || [];
  const scheduledPassIds = new Set(activeRun?.scheduled_passes.map(p => p.pass_id) || []);
  
  const minTime = passes.length ? Math.min(...passes.map(p => new Date(p.start_time).getTime())) : Date.now();
  const maxTime = passes.length ? Math.max(...passes.map(p => new Date(p.end_time).getTime())) : Date.now() + 3600000;
  
  const [simTimeMs, setSimTimeMs] = useState(minTime - 5 * 60 * 1000);
  const [isPlaying, setIsPlaying] = useState(true);
  const [speedMultiplier, setSpeedMultiplier] = useState(120); // 1 real sec = 120 sim sec
  
  const [showEmergency, setShowEmergency] = useState(false);

  useEffect(() => {
    let animationFrame: number;
    let lastTime = performance.now();

    const loop = (time: number) => {
      const delta = time - lastTime;
      lastTime = time;

      if (isPlaying) {
        setSimTimeMs(prev => {
          let next = prev + (delta * speedMultiplier);
          if (next > maxTime + 5 * 60 * 1000) {
            next = minTime - 5 * 60 * 1000;
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
  const restart = () => setSimTimeMs(minTime - 5 * 60 * 1000);

  // Active opportunities at current sim time
  const activeOpportunities = passes.filter(p => {
    const s = new Date(p.start_time).getTime();
    const e = new Date(p.end_time).getTime();
    return simTimeMs >= s && simTimeMs <= e;
  });

  const getPriorityColor = (prio: number) => {
    if (prio === 1) return 'text-rose-400 border-rose-500/50 bg-rose-500/10';
    if (prio === 2) return 'text-orange-400 border-orange-500/50 bg-orange-500/10';
    if (prio === 3) return 'text-amber-400 border-amber-500/50 bg-amber-500/10';
    return 'text-cyan-400 border-cyan-500/50 bg-cyan-500/10';
  };

  const getPriorityBgColor = (prio: number) => {
    if (prio === 1) return 'bg-rose-500';
    if (prio === 2) return 'bg-orange-500';
    if (prio === 3) return 'bg-amber-500';
    return 'bg-cyan-500';
  };

  const uniqueSatellites = Array.from(new Set(passes.map(p => p.satellite_id)));
  const uniqueStations = Array.from(new Set(passes.map(p => p.ground_station_id)));

  // Deterministic illustrative positioning
  const getStationPosition = (index: number, total: number) => {
    // Distribute around lower hemisphere
    const angle = (Math.PI / 4) + (Math.PI / 2) * (index / Math.max(1, total - 1));
    const r = 180; // Earth radius
    return { x: Math.cos(angle) * r, y: Math.sin(angle) * r };
  };

  const getSatellitePosition = (index: number, total: number) => {
    // Illustrative orbit parameters scaled to realistic LEO periods (~90 minutes)
    const r = 280 + (index * 40); // varied orbit heights
    const speed = 0.0000015 + (index * 0.0000003);
    const baseAngle = (index * Math.PI * 2) / total;
    const currentAngle = baseAngle + (simTimeMs * speed);
    return { x: Math.cos(currentAngle) * r, y: Math.sin(currentAngle) * r };
  };

  return (
    <div className="w-full flex flex-col gap-4 mb-6">
      <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 backdrop-blur-sm flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Activity className="w-5 h-5 text-indigo-400" />
          <h2 className="text-sm font-bold text-slate-100">Live Simulation: {activeDataset.name}</h2>
          <span className="px-2 py-0.5 rounded-full bg-slate-800 text-[10px] text-slate-400 font-mono">
            ILLUSTRATIVE ORBITAL MODEL
          </span>
        </div>
        {!showEmergency && (
          <button 
            onClick={() => setShowEmergency(true)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-rose-500/20 text-rose-300 border border-rose-500/30 text-xs font-semibold hover:bg-rose-500/30 transition"
          >
            <AlertTriangle className="w-4 h-4" /> Inject P1 Emergency Task
          </button>
        )}
      </div>

      <div className="relative w-full h-[600px] rounded-3xl overflow-hidden border border-indigo-500/20 shadow-2xl bg-[#020617] flex">
        {/* Deep space bg */}
        <div className="absolute inset-0 z-0">
          <div className="stars absolute inset-0 opacity-60"></div>
          <div className="twinkling absolute inset-0 opacity-40"></div>
          <div className="absolute top-0 -left-1/4 w-[150%] h-[150%] bg-gradient-radial from-indigo-900/20 via-slate-900/10 to-transparent blur-3xl opacity-60"></div>
        </div>

        {/* Central Visualization Canvas */}
        <div className="absolute inset-0 z-10 flex items-center justify-center pointer-events-none">
          <div className="relative w-[800px] h-[800px] flex items-center justify-center">
            
            {/* SVG Layer for Beams and Orbits */}
            <svg className="absolute inset-0 w-full h-full" viewBox="-400 -400 800 800">
              {/* Orbit Paths */}
              {uniqueSatellites.map((sat, i) => {
                const r = 280 + (i * 40);
                return (
                  <circle key={`orbit-${sat}`} cx="0" cy="0" r={r} fill="none" stroke="rgba(99, 102, 241, 0.15)" strokeWidth="1" strokeDasharray="4 4" />
                );
              })}

              {/* Data Beams */}
              {activeOpportunities.map(pass => {
                const isScheduled = scheduledPassIds.has(pass.pass_id);
                const satIdx = uniqueSatellites.indexOf(pass.satellite_id);
                const gsIdx = uniqueStations.indexOf(pass.ground_station_id);
                
                if (satIdx === -1 || gsIdx === -1) return null;

                const satPos = getSatellitePosition(satIdx, uniqueSatellites.length);
                const gsPos = getStationPosition(gsIdx, uniqueStations.length);

                return (
                  <g key={`beam-${pass.pass_id}`}>
                    <line 
                      x1={satPos.x} y1={satPos.y} 
                      x2={gsPos.x} y2={gsPos.y} 
                      stroke={isScheduled ? (pass.priority === 1 ? '#f43f5e' : '#10b981') : '#64748b'} 
                      strokeWidth={isScheduled ? "2" : "1"}
                      strokeDasharray={isScheduled ? "8 4" : "4 4"}
                      className={isScheduled ? "animate-[scanline_1s_linear_infinite]" : ""}
                      opacity={isScheduled ? 0.8 : 0.3}
                    />
                    {isScheduled && (
                      <circle cx={gsPos.x} cy={gsPos.y} r="20" fill="none" stroke={pass.priority === 1 ? '#f43f5e' : '#10b981'} className="animate-ping opacity-50" />
                    )}
                  </g>
                );
              })}
            </svg>

            {/* Earth */}
            <div className="absolute w-[360px] h-[360px] rounded-full overflow-hidden shadow-[0_0_80px_rgba(6,182,212,0.15)] flex items-center justify-center bg-black/50 z-10">
              <img src="/earth_globe.png" alt="Earth" className="w-full h-full object-cover opacity-90 drop-shadow-[0_0_15px_rgba(6,182,212,0.8)]" />
            </div>

            {/* Ground Stations */}
            {uniqueStations.map((gs, i) => {
              const pos = getStationPosition(i, uniqueStations.length);
              // Check if any active pass targets this station
              const activePass = activeOpportunities.find(p => p.ground_station_id === gs);
              const isScheduled = activePass && scheduledPassIds.has(activePass.pass_id);

              return (
                <div key={gs} className="absolute z-20" style={{ transform: `translate(${pos.x}px, ${pos.y}px)` }}>
                  <div className={`relative -left-1/2 -top-1/2 w-4 h-4 rounded-full border-2 ${isScheduled ? 'bg-emerald-500 border-white shadow-[0_0_15px_#10b981]' : 'bg-slate-700 border-slate-400'}`}>
                    <div className="absolute top-5 left-1/2 -translate-x-1/2 text-[9px] font-mono whitespace-nowrap bg-slate-900/80 px-1 rounded text-slate-300">
                      {gs}
                    </div>
                  </div>
                </div>
              );
            })}

            {/* Satellites */}
            {uniqueSatellites.map((sat, i) => {
              const pos = getSatellitePosition(i, uniqueSatellites.length);
              const activePass = activeOpportunities.find(p => p.satellite_id === sat);
              const isScheduled = activePass && scheduledPassIds.has(activePass.pass_id);

              return (
                <div key={sat} className="absolute z-30 transition-transform duration-75" style={{ transform: `translate(${pos.x}px, ${pos.y}px)` }}>
                  <div className="relative -left-1/2 -top-1/2">
                    <div className={`w-6 h-6 rounded bg-slate-800 border ${isScheduled ? 'border-cyan-400 shadow-[0_0_15px_rgba(34,211,238,0.6)]' : 'border-slate-500'} flex items-center justify-center`}>
                      <Satellite className={`w-3.5 h-3.5 ${isScheduled ? 'text-cyan-400' : 'text-slate-400'}`} />
                    </div>
                    {/* Solar panels */}
                    <div className="absolute top-1/2 -translate-y-1/2 -left-5 w-4 h-8 bg-blue-600/80 border border-blue-400 rounded-sm"></div>
                    <div className="absolute top-1/2 -translate-y-1/2 -right-5 w-4 h-8 bg-blue-600/80 border border-blue-400 rounded-sm"></div>
                    
                    <div className="absolute top-8 left-1/2 -translate-x-1/2 text-[10px] font-mono whitespace-nowrap bg-slate-900/90 px-1.5 py-0.5 rounded border border-slate-700 text-slate-200">
                      {sat}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Left Priority Panel */}
        <div className="relative z-40 w-[320px] h-full bg-slate-950/60 backdrop-blur-md border-r border-slate-800/60 p-4 flex flex-col overflow-y-auto custom-scrollbar">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-4">Priority Evaluation</div>
          
          {showEmergency && (
            <div className="mb-4 p-3 rounded-lg bg-rose-500/10 border border-rose-500/50 animate-pulse-slow">
              <div className="flex items-center gap-2 text-rose-400 font-bold text-xs mb-2">
                <AlertTriangle className="w-4 h-4" /> DISASTER RESPONSE
              </div>
              <p className="text-[10px] text-rose-200/80 leading-relaxed mb-3">
                Emergency P1 task injected into simulation. CP-SAT engine evaluating priority inversion vectors to preempt lower priority downlink.
              </p>
              <button 
                onClick={() => {
                  setShowEmergency(false);
                  if (onRunOptimizer) onRunOptimizer();
                }}
                className="w-full py-1.5 bg-rose-600 hover:bg-rose-500 text-white text-[11px] font-bold rounded transition"
              >
                EXECUTE CP-SAT RESCHEDULE
              </button>
            </div>
          )}

          <div className="space-y-3">
            {activeOpportunities.length === 0 && (
              <div className="text-[11px] text-slate-500 text-center py-4">No visibility windows active</div>
            )}
            {activeOpportunities.map(pass => {
              const isScheduled = scheduledPassIds.has(pass.pass_id);
              const statusLabel = isScheduled ? "DOWNLINKING" : "DROPPED (CONFLICT)";
              
              return (
                <div key={`eval-${pass.pass_id}`} className={`p-3 rounded-lg border bg-slate-900/80 backdrop-blur-sm ${getPriorityColor(pass.priority)}`}>
                  <div className="flex justify-between items-start mb-2">
                    <span className="font-mono text-[10px] font-bold">{pass.satellite_id}</span>
                    <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold text-white ${getPriorityBgColor(pass.priority)}`}>
                      P{pass.priority}
                    </span>
                  </div>
                  <div className="space-y-1 mb-2">
                    <div className="text-[10px] opacity-80 flex justify-between">
                      <span>Volume:</span> <span className="font-mono">{pass.data_volume_gb.toFixed(1)} GB</span>
                    </div>
                    <div className="text-[10px] opacity-80 flex justify-between">
                      <span>Station:</span> <span className="truncate ml-2">{pass.ground_station_id}</span>
                    </div>
                  </div>
                  <div className={`text-[10px] font-bold ${isScheduled ? 'text-emerald-400' : 'text-slate-500'}`}>
                    {isScheduled ? <span className="flex items-center gap-1"><ShieldCheck className="w-3 h-3" /> {statusLabel}</span> : statusLabel}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Timeline Control Panel (Bottom right) */}
        <div className="absolute bottom-6 right-6 z-40 bg-slate-900/90 backdrop-blur-md border border-slate-700 rounded-xl p-4 w-[400px] shadow-2xl">
          <div className="flex items-center justify-between mb-3 border-b border-slate-800 pb-2">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Simulation Clock</span>
            <span className="font-mono text-cyan-400 text-sm font-bold">
              {new Date(simTimeMs).toISOString().substring(11, 19)} UTC
            </span>
          </div>

          <div className="flex items-center gap-3 mb-4">
            <button onClick={restart} className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition">
              <RotateCcw className="w-4 h-4" />
            </button>
            <button onClick={togglePlay} className="flex-1 py-2 flex items-center justify-center gap-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-bold transition">
              {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
              {isPlaying ? 'PAUSE' : 'PLAY'}
            </button>
            <button onClick={() => setSpeedMultiplier(s => s === 120 ? 600 : 120)} className={`p-2 rounded-lg transition ${speedMultiplier > 120 ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30' : 'bg-slate-800 hover:bg-slate-700 text-slate-300'}`}>
              <FastForward className="w-4 h-4" />
            </button>
          </div>

          <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden mb-2">
            <div 
              className="h-full bg-cyan-400" 
              style={{ width: `${Math.max(0, Math.min(100, ((simTimeMs - minTime) / (maxTime - minTime)) * 100))}%` }}
            />
          </div>
          <div className="flex justify-between text-[9px] text-slate-500 font-mono">
            <span>{new Date(minTime).toISOString().substring(11, 16)}</span>
            <span>{new Date(maxTime).toISOString().substring(11, 16)}</span>
          </div>
        </div>
      </div>
    </div>
  );
};
