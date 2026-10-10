import React, { useEffect, useState } from 'react';
import {
  LayoutDashboard,
  CalendarClock,
  Scale,
  Satellite,
  Radio,
  Layers,
  ChevronLeft,
  ChevronRight,
  Activity,
  Database,
  RefreshCw,
  LogOut,
  User as UserIcon
} from 'lucide-react';
import type { Dataset, HealthCheckResponse } from '../../types/api';
import { useAuth } from '../../contexts/AuthContext';

export type NavTab = 'dashboard' | 'timeline' | 'comparison' | 'passes' | 'stations';

interface SidebarProps {
  activeTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  datasets: Dataset[];
  selectedDatasetId: string;
  onSelectDatasetId: (id: string) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  health: HealthCheckResponse | null;
  isBackendConnected: boolean;
  isCheckingHealth: boolean;
  onRefreshHealth: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onSelectTab,
  datasets,
  selectedDatasetId,
  onSelectDatasetId,
  isCollapsed,
  onToggleCollapse,
  health,
  isBackendConnected,
  isCheckingHealth,
  onRefreshHealth,
}) => {
  const [currentUtc, setCurrentUtc] = useState<string>('');
  const { user, logout } = useAuth();

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setCurrentUtc(now.toISOString().replace('.000', '').replace('T', ' ') + ' UTC');
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

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
        isCollapsed ? 'w-16' : 'w-72'
      }`}
    >
      {/* Top: Nav list */}
      <div className="p-3 overflow-y-auto">
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

      {/* Status & Profile block */}
      {!isCollapsed && (
        <div className="p-4 border-t border-slate-800/80 bg-slate-950/50 flex flex-col gap-3">
          {/* UTC Clock */}
          <div className="flex items-center justify-center gap-2 px-2.5 py-1.5 rounded-lg bg-slate-900/80 border border-slate-800 text-[11px] font-mono text-slate-300">
            <Activity className="w-3.5 h-3.5 text-cyan-400" />
            <span>{currentUtc || '2026-10-10 12:00:00 UTC'}</span>
          </div>

          {/* Backend Connection Pill */}
          <div
            className={`flex items-center justify-between px-3 py-2 rounded-lg border text-xs font-medium transition ${
              isBackendConnected
                ? 'bg-emerald-950/30 border-emerald-500/30 text-emerald-300'
                : 'bg-amber-950/30 border-amber-500/30 text-amber-300'
            }`}
          >
            <div className="flex items-center gap-2">
              <span
                className={`w-2 h-2 rounded-full ${
                  isBackendConnected
                    ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]'
                    : 'bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.8)]'
                }`}
              />
              <span>
                {isBackendConnected ? 'Backend Live' : 'Demo Mode'}
              </span>
            </div>

            <div className="flex items-center gap-2">
              {health?.database_connected && (
                <span className="flex items-center gap-1 text-[11px] text-emerald-400 pr-2 border-r border-emerald-500/30">
                  <Database className="w-3 h-3" />
                  DB
                </span>
              )}
              <button
                onClick={onRefreshHealth}
                disabled={isCheckingHealth}
                title="Refresh connection status"
                className="p-1 hover:text-white transition disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isCheckingHealth ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>
          
          {/* User profile & logout */}
          {user && (
            <div className="flex items-center justify-between mt-1 pt-3 border-t border-slate-800/80">
              <div className="flex items-center gap-2 text-sm text-slate-300 overflow-hidden">
                {user.photoURL ? (
                  <img src={user.photoURL} alt="User" className="w-8 h-8 rounded-full border-2 border-slate-700 object-cover" />
                ) : (
                  <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center border-2 border-slate-700 shrink-0">
                    <UserIcon className="w-4 h-4 text-slate-400" />
                  </div>
                )}
                <div className="flex flex-col overflow-hidden">
                  <span className="truncate text-xs font-bold text-slate-200">{user.displayName || user.email?.split('@')[0] || 'Operator'}</span>
                  <span className="truncate text-[9px] font-mono font-medium text-cyan-400 uppercase tracking-widest mt-0.5">Mission Controller</span>
                </div>
              </div>
              <button 
                onClick={() => logout()}
                title="Log out"
                className="p-1.5 text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 rounded-md transition-colors shrink-0"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      )}
    </aside>
  );
};
