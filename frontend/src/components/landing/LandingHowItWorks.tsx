import React from 'react';
import { DownloadCloud, CheckCircle, Cpu, RefreshCw, BarChart2 } from 'lucide-react';

export const LandingHowItWorks: React.FC = () => {
  const steps = [
    {
      icon: <DownloadCloud className="w-6 h-6 text-cyan-400" />,
      title: '1. Receive Downlink Requests',
      description: 'Satellite requests contain data volume, priority, deadlines, and visibility windows.',
    },
    {
      icon: <CheckCircle className="w-6 h-6 text-indigo-400" />,
      title: '2. Evaluate Constraints',
      description: 'Check satellite availability, ground-station availability, transmission rates, outages, and timing.',
    },
    {
      icon: <Cpu className="w-6 h-6 text-purple-400" />,
      title: '3. Optimize the Schedule',
      description: 'The CP-SAT optimizer searches for a high-value feasible schedule across all assets.',
    },
    {
      icon: <RefreshCw className="w-6 h-6 text-emerald-400" />,
      title: '4. Handle Changing Conditions',
      description: 'New requests and operational changes can trigger safe, automated rescheduling.',
    },
    {
      icon: <BarChart2 className="w-6 h-6 text-sky-400" />,
      title: '5. Visualize the Results',
      description: 'Display assigned passes, delivered data, station utilization, and solver status.',
    },
  ];

  return (
    <section id="how-it-works" className="py-24 bg-[#0a0e1a] border-t border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="text-center mb-16">
          <h2 className="text-3xl font-extrabold text-white mb-4">How OrbitOpt Actually Works</h2>
        </div>

        <div className="relative">
          {/* Connecting line */}
          <div className="hidden lg:block absolute top-1/2 left-0 w-full h-0.5 bg-slate-800 -translate-y-1/2"></div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-8">
            {steps.map((step, index) => (
              <div key={index} className="relative z-10 flex flex-col items-center text-center">
                <div className="w-16 h-16 rounded-2xl bg-slate-900 border border-slate-700 flex items-center justify-center mb-6 shadow-lg">
                  {step.icon}
                </div>
                <h3 className="text-lg font-bold text-slate-200 mb-2">{step.title}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{step.description}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
};
