import React from 'react';
import { Cpu, Zap, ShieldAlert, WifiOff, Clock, RefreshCcw, Activity, ShieldCheck } from 'lucide-react';

export const LandingFeatures: React.FC = () => {
  const features = [
    {
      icon: <Cpu className="w-5 h-5 text-cyan-400" />,
      title: 'CP-SAT Optimization',
      description: 'Uses Google OR-Tools to solve complex multi-satellite constraint models.'
    },
    {
      icon: <Zap className="w-5 h-5 text-indigo-400" />,
      title: 'Dynamic Request Prioritization',
      description: 'Automatically weighs high-value targets and urgent data downlinks.'
    },
    {
      icon: <ShieldAlert className="w-5 h-5 text-rose-400" />,
      title: 'Verified Emergency Precedence',
      description: 'Injects P1 emergency tasks that bypass standard queue constraints safely.'
    },
    {
      icon: <WifiOff className="w-5 h-5 text-amber-400" />,
      title: 'Ground-Station Outage Handling',
      description: 'Reroutes passes automatically when a station goes offline unexpectedly.'
    },
    {
      icon: <Clock className="w-5 h-5 text-emerald-400" />,
      title: 'Dynamic Scheduling',
      description: 'Ensures data reaches the ground before mission-critical deadlines expire.'
    },
    {
      icon: <RefreshCcw className="w-5 h-5 text-sky-400" />,
      title: 'Safe Automatic Rescheduling',
      description: 'Recalculates overlapping passes without breaking existing locked commitments.'
    },
    {
      icon: <Activity className="w-5 h-5 text-purple-400" />,
      title: 'FCFS Baseline Comparison',
      description: 'Built-in benchmarking against First-Come-First-Served legacy scheduling.'
    },
    {
      icon: <ShieldCheck className="w-5 h-5 text-blue-400" />,
      title: 'Schedule Validation',
      description: 'Mathematically guarantees zero overlapping conflicts on limited antennas.'
    }
  ];

  return (
    <section id="features" className="py-24 bg-[#070a13]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="text-center mb-16">
          <h2 className="text-3xl font-extrabold text-white mb-4">Core Technology Features</h2>
          <p className="text-slate-400 max-w-2xl mx-auto">
            Everything you need to manage a growing constellation of Earth observation satellites.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {features.map((feature, index) => (
            <div 
              key={index} 
              className="group p-6 rounded-2xl bg-slate-900/50 border border-slate-800 hover:border-cyan-500/30 hover:bg-slate-800/80 transition-all duration-300"
            >
              <div className="w-10 h-10 rounded-lg bg-slate-800 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                {feature.icon}
              </div>
              <h3 className="text-lg font-semibold text-slate-200 mb-2">{feature.title}</h3>
              <p className="text-sm text-slate-400 leading-relaxed">{feature.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};
