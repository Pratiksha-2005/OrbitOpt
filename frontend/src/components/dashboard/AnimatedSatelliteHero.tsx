import React from 'react';
import { Sparkles, Map, Radio } from 'lucide-react';

export const AnimatedSatelliteHero: React.FC = () => {
  return (
    <div className="relative w-full h-[650px] rounded-3xl overflow-hidden mb-6 border border-indigo-500/20 shadow-2xl shadow-cyan-900/10 bg-[#020617] flex">
      {/* Dynamic Starfield Background */}
      <div className="absolute inset-0 z-0 overflow-hidden opacity-50">
        <div className="stars absolute inset-0"></div>
        <div className="twinkling absolute inset-0"></div>
      </div>
      
      {/* Nebula Gradients */}
      <div className="absolute top-0 -left-1/4 w-[150%] h-[150%] bg-gradient-radial from-indigo-900/20 via-slate-900/10 to-transparent blur-3xl opacity-60 mix-blend-screen animate-pulse-slow"></div>

      {/* Main Central View - Earth Map */}
      <div className="absolute inset-0 z-10 flex items-center justify-center pointer-events-none">
        <div className="relative w-[500px] h-[500px] flex items-center justify-center">
          {/* Earth Image */}
          <div className="absolute w-[400px] h-[400px] rounded-full overflow-hidden shadow-[0_0_80px_rgba(6,182,212,0.15)] flex items-center justify-center bg-black/50">
            <img 
              src="/earth_globe.png" 
              alt="Planet Earth" 
              className="w-full h-full object-cover opacity-90 drop-shadow-[0_0_15px_rgba(6,182,212,0.8)]"
            />
          </div>

          {/* Orbit Rings */}
          <div className="absolute w-[500px] h-[500px] rounded-full border border-indigo-500/30 rotate-[60deg] skew-x-12 animate-[spin_40s_linear_infinite]"></div>
          <div className="absolute w-[550px] h-[550px] rounded-full border-[1px] border-cyan-500/20 rotate-[-30deg] skew-y-12 animate-[spin_60s_linear_infinite_reverse]"></div>

          {/* Satellite 1 */}
          <div className="absolute w-[500px] h-[500px] rotate-[60deg] animate-[spin_15s_linear_infinite]">
            <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 flex items-center justify-center -rotate-45">
              <div className="relative">
                <div className="w-8 h-8 rounded-md bg-gradient-to-br from-slate-200 to-slate-400 border border-slate-100 shadow-[0_0_25px_rgba(255,255,255,0.8)] flex items-center justify-center">
                  <div className="w-3 h-3 bg-cyan-400 rounded-sm shadow-[0_0_10px_#22d3ee] animate-pulse"></div>
                </div>
                {/* Solar Panels */}
                <div className="absolute top-1/2 -translate-y-1/2 -left-8 w-7 h-10 bg-blue-500/80 border border-blue-300 rounded-[2px] grid grid-cols-2 gap-0.5 p-0.5">
                  <div className="bg-blue-600"></div><div className="bg-blue-600"></div>
                  <div className="bg-blue-600"></div><div className="bg-blue-600"></div>
                </div>
                <div className="absolute top-1/2 -translate-y-1/2 -right-8 w-7 h-10 bg-blue-500/80 border border-blue-300 rounded-[2px] grid grid-cols-2 gap-0.5 p-0.5">
                  <div className="bg-blue-600"></div><div className="bg-blue-600"></div>
                  <div className="bg-blue-600"></div><div className="bg-blue-600"></div>
                </div>
              </div>
            </div>
          </div>

          {/* Crosshair / Radar Center overlay */}
          <div className="absolute w-[450px] h-[450px] border-[0.5px] border-cyan-500/20 rounded-full pointer-events-none flex items-center justify-center">
            <div className="w-full h-[1px] bg-cyan-500/10"></div>
            <div className="absolute h-full w-[1px] bg-cyan-500/10"></div>
          </div>
        </div>
      </div>

      {/* Left Sidebar Info (Telemetry style) */}
      <div className="relative z-20 flex flex-col justify-start items-start p-6 w-[300px] border-r border-slate-800/60 bg-slate-950/40 backdrop-blur-md">
        <div className="flex items-center gap-3 mb-8">
          <div className="p-2 rounded-lg bg-cyan-500/10 border border-cyan-500/30">
            <Radio className="w-6 h-6 text-cyan-400" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-100 tracking-wider">ORBIT-02</h2>
            <div className="text-[10px] text-emerald-400 font-mono tracking-widest flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
              OPERATIONAL
            </div>
          </div>
        </div>

        <div className="w-full space-y-4 mb-8">
          <div className="flex justify-between items-end border-b border-slate-800 pb-2">
            <span className="text-[11px] text-slate-400">Next Pass (HRS)</span>
            <span className="text-xs font-mono text-slate-200">in 12m 43s</span>
          </div>
          <div className="flex justify-between items-end border-b border-slate-800 pb-2">
            <span className="text-[11px] text-slate-400">AOS</span>
            <span className="text-xs font-mono text-slate-200">08:37:19 UTC</span>
          </div>
          <div className="flex justify-between items-end border-b border-slate-800 pb-2">
            <span className="text-[11px] text-slate-400">LOS</span>
            <span className="text-xs font-mono text-slate-200">08:48:02 UTC</span>
          </div>
          <div className="flex justify-between items-end border-b border-slate-800 pb-2">
            <span className="text-[11px] text-slate-400">Max Elevation</span>
            <span className="text-xs font-mono text-cyan-300">78.3°</span>
          </div>
        </div>

        <div className="mt-auto p-4 rounded-xl bg-slate-900/60 border border-slate-800 w-full">
          <div className="text-[10px] text-slate-400 uppercase tracking-widest mb-2 flex items-center gap-2">
            <Map className="w-3.5 h-3.5 text-indigo-400" /> Current Position
          </div>
          <div className="text-sm font-mono text-slate-200">Lat 12.634° N</div>
          <div className="text-sm font-mono text-slate-200">Lon 45.218° E</div>
        </div>
      </div>

      {/* Floating Center Overlay Text */}
      <div className="relative z-30 flex-1 flex flex-col justify-between p-6 pointer-events-none">
        <div className="flex justify-between items-start">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-900/80 border border-slate-700 backdrop-blur-md shadow-lg pointer-events-auto">
            <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-[10px] font-bold tracking-widest text-slate-200 uppercase">Mission Control</span>
          </div>
          <div className="text-right">
            <div className="text-[11px] text-slate-400 font-mono mb-1">NORAD ID 43218</div>
            <div className="text-[11px] text-slate-400 font-mono">COSPAR 2022-056A</div>
          </div>
        </div>

        {/* Live Imagery Panel at Bottom Right */}
        <div className="self-end mt-auto w-80 rounded-xl overflow-hidden border border-slate-700 bg-slate-900/80 backdrop-blur-md pointer-events-auto shadow-2xl">
          <div className="px-3 py-2 border-b border-slate-700 flex justify-between items-center bg-slate-950/50">
            <span className="text-[10px] font-semibold text-slate-300 uppercase tracking-wider">Live Imagery</span>
            <span className="text-[9px] text-emerald-400 font-mono px-1.5 py-0.5 rounded border border-emerald-500/30 bg-emerald-500/10 animate-pulse">CAPTURING</span>
          </div>
          <div className="h-48 relative">
            <img src="/satellite_imagery.png" alt="Live Satellite Feed" className="w-full h-full object-cover" />
            <div className="absolute inset-0 bg-cyan-900/10 mix-blend-screen pointer-events-none"></div>
            <div className="absolute inset-0 border border-cyan-400/20 m-2 rounded pointer-events-none"></div>
            <div className="absolute bottom-2 left-2 text-[9px] font-mono text-white/80 bg-black/50 px-1 rounded">
              Res 1.2m / px
            </div>
            <div className="absolute top-0 left-0 w-full h-[2px] bg-cyan-400/50 animate-[scanline_4s_linear_infinite] shadow-[0_0_8px_#22d3ee]"></div>
          </div>
        </div>
      </div>

      {/* Right Sidebar Info */}
      <div className="relative z-20 flex flex-col justify-start items-start p-6 w-[300px] border-l border-slate-800/60 bg-slate-950/40 backdrop-blur-md text-xs font-mono">
        <h3 className="font-sans font-semibold text-slate-300 uppercase tracking-widest text-[10px] mb-4 border-b border-slate-800 pb-2 w-full">Telemetry</h3>
        
        <div className="w-full space-y-3 mb-6">
          <div className="flex justify-between items-center text-slate-300">
            <span className="text-slate-400">Altitude</span>
            <span>542.6 km</span>
          </div>
          <div className="flex justify-between items-center text-slate-300">
            <span className="text-slate-400">Velocity</span>
            <span>7.61 km/s</span>
          </div>
          <div className="flex justify-between items-center text-slate-300">
            <span className="text-slate-400">Inclination</span>
            <span>98.7°</span>
          </div>
          <div className="flex justify-between items-center text-slate-300">
            <span className="text-slate-400">Eccentricity</span>
            <span>0.0012</span>
          </div>
        </div>

        <h3 className="font-sans font-semibold text-slate-300 uppercase tracking-widest text-[10px] mb-4 border-b border-slate-800 pb-2 w-full mt-4">Communication</h3>
        
        <div className="w-full space-y-3">
          <div className="flex justify-between items-center">
            <span className="text-slate-400">Uplink</span>
            <div className="flex items-center gap-2">
              <span className="text-slate-300">8.402 GHz</span>
              <span className="px-1.5 py-0.5 text-[8px] bg-emerald-500/20 text-emerald-400 rounded">LOCKED</span>
            </div>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-slate-400">Downlink</span>
            <div className="flex items-center gap-2">
              <span className="text-slate-300">8.255 GHz</span>
              <span className="px-1.5 py-0.5 text-[8px] bg-emerald-500/20 text-emerald-400 rounded">LOCKED</span>
            </div>
          </div>
          <div className="flex justify-between items-center text-slate-300">
            <span className="text-slate-400">Data Rate</span>
            <span className="text-cyan-300 font-bold">12.6 Mbps</span>
          </div>
        </div>
      </div>
    </div>
  );
};
