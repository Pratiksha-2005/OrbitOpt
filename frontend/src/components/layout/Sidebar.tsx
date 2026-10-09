import React from 'react';
import {
  LayoutDashboard,
  CalendarClock,
  Scale,
  Satellite,
  Radio,
  Layers,
  ChevronLeft,
  ChevronRight,
  Info,
} from 'lucide-react';
import type { Dataset } from '../../types/api';

export type NavTab = 'dashboard' | 'timeline' | 'comparison' | 'passes' | 'stations';

interface SidebarProps {
  activeTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  datasets: Dataset[];
  selectedDatasetId: string;
  onSelectDatasetId: (id: string) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onSelectTab,
  datasets,
  selectedDatasetId,
  onSelectDatasetId,
  isCollapsed,
  onToggleCollapse,
}) => {
  const navItems = [
    {
      id: 'dashboard' as NavTab,
      label: 'Mission Dashboard',
      icon: LayoutDashboard,
      badge: undefined,
    },
    {
      id: 'timeline' as NavTab,
      label: 'Schedule Timeline',
      icon: CalendarClock,
      badge: 'Gantt',
    },
    {
      id: 'comparison' as NavTab,
      label: 'FCFS vs CP-SAT',
      icon: Scale,
      badge: 'Benchmark',
    },
    {
      id: 'passes' as NavTab,
      label: 'Satellite Passes',
      icon: Satellite,
      badge: undefined,
    },
    {
      id: 'stations' as NavTab,
      label: 'Ground Stations',
      icon: Radio,
      badge: undefined,
    },
  ];

  return (
    <aside
      className={`relative shrink-0 border-r border-slate-800/80 bg-slate-950/70 backdrop-blur-md transition-all duration-300 flex flex-col justify-between ${
        isCollapsed ? 'w-16' : 'w-64'
      }`}
    >
      {/* Top: Nav list */}
      <div className="p-3">
        {/* Toggle Collapse Button */}
        <div className="flex justify-end mb-2">
          <button
            onClick={onToggleCollapse}
            aria-label={isCollapsed ? 'Expand navigation' : 'Collapse navigation'}
            className="p-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-800 transition"
          >
            {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
        </div>

        {/* Navigation buttons */}
        <nav className="space-y-1.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-gradient-to-r from-cyan-500/20 to-indigo-500/10 text-cyan-300 border border-cyan-500/30 shadow-sm shadow-cyan-500/5'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60 border border-transparent'
                }`}
                title={isCollapsed ? item.label : undefined}
              >
                <Icon
                  className={`w-5 h-5 shrink-0 ${
                    isActive ? 'text-cyan-400' : 'text-slate-400'
                  }`}
                />
                {!isCollapsed && (
                  <div className="flex items-center justify-between w-full overflow-hidden text-left">
                    <span className="truncate">{item.label}</span>
                    {item.badge && (
                      <span className="ml-2 px-1.5 py-0.5 text-[10px] uppercase font-semibold rounded bg-slate-800 text-slate-300 border border-slate-700/60">
                        {item.badge}
                      </span>
                    )}
                  </div>
                )}
              </button>
            );
          })}
        </nav>

        {/* Scenario selector section */}
        {!isCollapsed && (
          <div className="mt-6 pt-5 border-t border-slate-800/80">
            <div className="flex items-center gap-1.5 px-2 mb-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
              <Layers className="w-3.5 h-3.5 text-cyan-400" />
              <span>Scenario Dataset</span>
            </div>
            <div className="space-y-1">
              {datasets.map((ds) => {
                const isSelected = ds.dataset_id === selectedDatasetId;
                return (
                  <button
                    key={ds.dataset_id}
                    onClick={() => onSelectDatasetId(ds.dataset_id)}
                    className={`w-full text-left p-2.5 rounded-lg border text-xs transition ${
                      isSelected
                        ? 'bg-slate-900 border-indigo-500/40 text-slate-100 font-medium'
                        : 'bg-slate-950/40 border-slate-800/60 text-slate-400 hover:bg-slate-900/40 hover:text-slate-200'
                    }`}
                  >
                    <div className="font-semibold text-slate-200 truncate">{ds.name}</div>
                    <div className="text-[11px] text-slate-400 mt-0.5 flex items-center justify-between">
                      <span>{ds.satellite_pass_count} Passes</span>
                      <span>{ds.ground_station_count} Stations</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Bottom info widget */}
      {!isCollapsed && (
        <div className="p-3 border-t border-slate-800/80">
          <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-[11px] text-slate-400 leading-relaxed">
            <div className="flex items-center gap-1.5 font-semibold text-slate-300 mb-1">
              <Info className="w-3.5 h-3.5 text-cyan-400" />
              <span>Objective Function</span>
            </div>
            <span>
              Maximizes <code className="text-cyan-300 font-mono">w_p × data_volume</code> while enforcing 60s antenna slew setup times.
            </span>
          </div>
        </div>
      )}
    </aside>
  );
};
