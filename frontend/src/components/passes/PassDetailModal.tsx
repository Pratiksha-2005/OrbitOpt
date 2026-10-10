import React from 'react';
import { X, Satellite, Radio, Clock, Database, Gauge, Zap } from 'lucide-react';
import type { SatellitePass } from '../../types/api';

interface PassDetailModalProps {
  pass: SatellitePass | null;
  onClose: () => void;
}

export const PassDetailModal: React.FC<PassDetailModalProps> = ({ pass, onClose }) => {
  if (!pass) return null;

  const durationSec =
    (new Date(pass.end_time).getTime() - new Date(pass.start_time).getTime()) / 1000;
  
  // Calculate Theoretical Capacity (GB) = (rate * duration) / 8000.0 (API_CONTRACT formula)
  const rateMbps = pass.effective_data_rate_mbps || 400;
  const channelCapacityGb = (rateMbps * durationSec) / 8000.0;
  const transferableGb = Math.min(pass.data_volume_gb, channelCapacityGb);

  const priorityLabels: Record<number, { text: string; bg: string; color: string }> = {
    1: { text: 'P1 - Critical Priority', bg: 'bg-rose-500/20', color: 'text-rose-300' },
    2: { text: 'P2 - High Priority', bg: 'bg-orange-500/20', color: 'text-orange-300' },
    3: { text: 'P3 - Medium Priority', bg: 'bg-amber-500/20', color: 'text-amber-300' },
    4: { text: 'P4 - Low Priority', bg: 'bg-cyan-500/20', color: 'text-cyan-300' },
    5: { text: 'P5 - Lowest Priority', bg: 'bg-slate-500/20', color: 'text-slate-300' },
  };

  const priorityMeta = priorityLabels[pass.priority] || priorityLabels[3];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg rounded-2xl bg-slate-900 border border-slate-700 p-6 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
              <Satellite className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-100">{pass.pass_id}</h3>
              <p className="text-xs text-slate-400">{pass.satellite_id}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Priority Badge */}
        <div className="my-4">
          <span
            className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${priorityMeta.bg} ${priorityMeta.color} border border-current`}
          >
            <Zap className="w-3.5 h-3.5" />
            {priorityMeta.text}
          </span>
        </div>

        {/* Details Grid */}
        <div className="grid grid-cols-2 gap-3 text-xs mb-5">
          <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
            <div className="flex items-center gap-1.5 text-slate-400 mb-1">
              <Radio className="w-3.5 h-3.5 text-cyan-400" />
              <span>Target Station</span>
            </div>
            <div className="font-semibold text-slate-200">{pass.ground_station_id}</div>
            <div className="text-[11px] text-slate-400 mt-0.5">
              Band: {pass.channel_band || 'X-band'}
            </div>
          </div>

          <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
            <div className="flex items-center gap-1.5 text-slate-400 mb-1">
              <Gauge className="w-3.5 h-3.5 text-emerald-400" />
              <span>Max Elevation</span>
            </div>
            <div className="font-semibold text-slate-200">{pass.max_elevation_deg}° above horizon</div>
            <div className="text-[11px] text-emerald-400 mt-0.5">
              {pass.max_elevation_deg >= 45 ? 'Optimal High Pass' : 'Low Horizon Pass'}
            </div>
          </div>

          <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
            <div className="flex items-center gap-1.5 text-slate-400 mb-1">
              <Clock className="w-3.5 h-3.5 text-indigo-400" />
              <span>Pass Window</span>
            </div>
            <div className="font-mono text-slate-200">{new Date(pass.start_time).toISOString().substring(11, 19)} - {new Date(pass.end_time).toISOString().substring(11, 19)} UTC</div>
            <div className="text-[11px] text-slate-400 mt-0.5">
              Duration: {durationSec}s ({(durationSec / 60).toFixed(1)} min)
            </div>
          </div>

          <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
            <div className="flex items-center gap-1.5 text-slate-400 mb-1">
              <Database className="w-3.5 h-3.5 text-purple-400" />
              <span>Data Volumes</span>
            </div>
            <div className="font-semibold text-slate-200">{pass.data_volume_gb.toFixed(1)} GB pending</div>
            <div className="text-[11px] text-purple-300 mt-0.5">
              Rate: {rateMbps} Mbps
            </div>
          </div>
        </div>

        {/* Capacity Formula Breakdown Box */}
        <div className="p-3.5 rounded-xl bg-cyan-950/30 border border-cyan-800/40 text-[11px] text-cyan-200 leading-relaxed mb-4">
          <div className="font-semibold text-cyan-300 mb-1">Channel Capacity Formulation:</div>
          <p className="font-mono text-[10px] text-cyan-300/80 mb-1">
            Capacity = ({rateMbps} Mbps × {durationSec}s) / 8000 = {channelCapacityGb.toFixed(2)} GB
          </p>
          <p className="text-slate-300">
            Transferable Volume: <strong className="text-cyan-300">{transferableGb.toFixed(2)} GB</strong>{' '}
            (bounded by pending payload volume).
          </p>
        </div>

        {/* Footer */}
        <div className="flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
