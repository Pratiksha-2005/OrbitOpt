import React from 'react';
import { EarthScene } from './EarthScene';
import { Rocket, ShieldAlert, Cpu } from 'lucide-react';
import { Starfield } from '../common/Starfield';

interface LandingHeroProps {
  onNavigateToAuth: () => void;
}

export const LandingHero: React.FC<LandingHeroProps> = ({ onNavigateToAuth }) => {
  return (
    <section id="hero" className="relative min-h-[90vh] lg:min-h-screen flex flex-col justify-start pt-24 lg:pt-32 overflow-hidden bg-[#070a13]">
      {/* Dynamic Starfield Background */}
      <Starfield />
      
      {/* Subtle radial gradient overlay */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,transparent_0%,#070a13_100%)] z-0 pointer-events-none"></div>

      <div className="max-w-7xl mx-auto w-full px-4 sm:px-6 relative z-10 flex-grow flex flex-col justify-start">
        <div className="flex flex-col items-center text-center">
          
          {/* Centered Hero Content */}
          <div className="max-w-3xl flex flex-col items-center">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 text-xs font-semibold uppercase tracking-wider mb-6 shadow-[0_0_15px_rgba(34,211,238,0.2)]">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-500"></span>
              </span>
              OrbitOpt Mission Control
            </div>
            
            <h1 className="text-4xl sm:text-5xl lg:text-7xl font-extrabold text-white tracking-tight mb-6 leading-tight drop-shadow-lg">
              Intelligent Scheduling. <br className="hidden sm:block" />
              <span className="bg-gradient-to-r from-cyan-400 to-indigo-400 bg-clip-text text-transparent">
                Smarter Satellite Missions.
              </span>
            </h1>
            
            <p className="text-lg text-slate-300 mb-8 max-w-2xl leading-relaxed">
              Optimize satellite downlinks with constraint-aware scheduling, dynamic request priorities, and intelligent ground-station allocation.
            </p>
            
            <div className="flex flex-wrap items-center justify-center gap-4 mb-12 relative z-20">
              <button
                onClick={onNavigateToAuth}
                className="px-6 py-3 rounded-md bg-cyan-400 text-slate-950 font-bold hover:bg-cyan-300 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-[#070a13] focus:ring-cyan-400 transition-all shadow-[0_0_20px_rgba(34,211,238,0.4)] hover:shadow-[0_0_30px_rgba(34,211,238,0.6)]"
              >
                Launch Mission Control
              </button>
              <a
                href="#how-it-works"
                className="px-6 py-3 rounded-md bg-slate-800/80 text-white font-medium hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-[#070a13] focus:ring-slate-400 transition-all border border-slate-700 backdrop-blur-sm"
              >
                Explore How It Works
              </a>
            </div>
            
            {/* Value Metrics */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 pt-8 border-t border-slate-800/50 w-full">
              <div className="flex flex-col items-center text-center gap-3">
                <div className="p-2 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
                  <Rocket className="w-5 h-5" />
                </div>
                <div className="text-sm font-medium text-slate-300">Multi-satellite<br/>scheduling</div>
              </div>
              <div className="flex flex-col items-center text-center gap-3">
                <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                  <ShieldAlert className="w-5 h-5" />
                </div>
                <div className="text-sm font-medium text-slate-300">Ground-station<br/>conflict prevention</div>
              </div>
              <div className="flex flex-col items-center text-center gap-3">
                <div className="p-2 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400">
                  <Cpu className="w-5 h-5" />
                </div>
                <div className="text-sm font-medium text-slate-300">Emergency-aware<br/>optimization</div>
              </div>
            </div>
          </div>
          
        </div>
      </div>
      
      {/* 3D Earth Container (Absolute Right) */}
      <EarthScene />
    </section>
  );
};
