import React from 'react';
import { Satellite } from 'lucide-react';

interface NavbarProps {
  activeScenarioName: string;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeScenarioName,
}) => {
  return (
    <header className="sticky top-0 z-30 w-full border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md px-4 sm:px-6 py-3">
      <div className="flex items-center justify-between gap-4">
        {/* Brand identity */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-600 via-indigo-600 to-purple-600 p-0.5 shadow-lg shadow-cyan-500/10">
            <div className="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center">
              <Satellite className="w-5 h-5 text-cyan-400" />
            </div>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-lg tracking-tight bg-gradient-to-r from-cyan-400 via-sky-300 to-indigo-300 bg-clip-text text-transparent">
                OrbitOpt
              </span>
              <span className="px-1.5 py-0.5 text-[10px] font-semibold tracking-wider uppercase rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                v1.0 Hackathon
              </span>
            </div>
            <p className="hidden md:block text-xs text-slate-400 font-normal">
              Autonomous Ground Station Scheduling for Multi-Satellite Downlink
            </p>
          </div>
        </div>

        {/* Center / Scenario tag */}
        <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900/80 border border-slate-800 text-xs">
          <span className="text-slate-400">Active Scenario:</span>
          <span className="font-medium text-cyan-300 truncate max-w-xs">{activeScenarioName}</span>
        </div>

      </div>
    </header>
  );
};
