import React, { useState } from 'react';
import {
  X,
  Satellite,
  Radio,
  Clock,
  Database,
  Gauge,
  Zap,
  Lock,
  Unlock,
  Activity,
  CheckCircle2,
  AlertCircle,
  Play,
  XCircle,
} from 'lucide-react';

import type {
  SatellitePass,
  PassExecutionRead,
  PassExecutionStatus,
  PassTransitionRequest,
} from '../../types/api';

interface PassDetailModalProps {
  pass: SatellitePass | null;
  execution?: PassExecutionRead | null;
  onClose: () => void;
  onTransition?: (passId: string, req: PassTransitionRequest) => Promise<void>;
}

export const PassDetailModal: React.FC<PassDetailModalProps> = ({
  pass,
  execution,
  onClose,
  onTransition,
}) => {
  if (!pass) return null;

  const [isTransitioning, setIsTransitioning] = useState(false);
  const [transitionError, setTransitionError] = useState<string | null>(null);
  const [actualVolumeInput, setActualVolumeInput] = useState<string>(
    execution?.actual_data_delivered_gb !== null && execution?.actual_data_delivered_gb !== undefined
      ? String(execution.actual_data_delivered_gb)
      : String(pass.data_volume_gb)
  );
  const [operatorNotes, setOperatorNotes] = useState<string>('');

  const durationSec =
    (new Date(pass.end_time).getTime() - new Date(pass.start_time).getTime()) / 1000;

  const rateMbps = pass.effective_data_rate_mbps || 400;
  const channelCapacityGb = (rateMbps * durationSec) / 8000.0;
  const transferableGb = Math.min(pass.data_volume_gb, channelCapacityGb);

  const status: PassExecutionStatus = execution?.status || 'SCHEDULED';
  const isLocked = execution?.is_locked ?? false;

  const priorityLabels: Record<number, { text: string; bg: string; color: string }> = {
    1: { text: 'P1 - Critical Priority', bg: 'bg-rose-500/20', color: 'text-rose-300' },
    2: { text: 'P2 - High Priority', bg: 'bg-orange-500/20', color: 'text-orange-300' },
    3: { text: 'P3 - Medium Priority', bg: 'bg-amber-500/20', color: 'text-amber-300' },
    4: { text: 'P4 - Low Priority', bg: 'bg-cyan-500/20', color: 'text-cyan-300' },
    5: { text: 'P5 - Lowest Priority', bg: 'bg-slate-500/20', color: 'text-slate-300' },
  };
  const priorityMeta = priorityLabels[pass.priority] || priorityLabels[3];

  const getStatusBadge = (st: PassExecutionStatus) => {
    switch (st) {
      case 'ACQUIRING':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold bg-sky-500/20 text-sky-300 border border-sky-500/30 animate-pulse">
            <Activity className="w-3.5 h-3.5" />
            ACQUIRING CARRIER
          </span>
        );
      case 'TRANSMITTING':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 animate-pulse">
            <Radio className="w-3.5 h-3.5" />
            TRANSMITTING DOWNLINK
          </span>
        );
      case 'COMPLETED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold bg-teal-500/20 text-teal-300 border border-teal-500/30">
            <CheckCircle2 className="w-3.5 h-3.5" />
            COMPLETED
          </span>
        );
      case 'MISSED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/30">
            <AlertCircle className="w-3.5 h-3.5" />
            MISSED CONTACT
          </span>
        );
      case 'CANCELLED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold bg-slate-500/20 text-slate-300 border border-slate-500/30">
            <XCircle className="w-3.5 h-3.5" />
            CANCELLED
          </span>
        );
      case 'SCHEDULED':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
            <Clock className="w-3.5 h-3.5" />
            SCHEDULED
          </span>
        );
    }
  };

  const handleAction = async (targetStatus: PassExecutionStatus) => {
    if (!onTransition) return;
    setIsTransitioning(true);
    setTransitionError(null);
    try {
      const delivered =
        targetStatus === 'COMPLETED' ? parseFloat(actualVolumeInput) || pass.data_volume_gb : undefined;
      await onTransition(pass.pass_id, {
        to_status: targetStatus,
        actual_data_delivered_gb: delivered,
        telemetry_source: 'operator_manual',
        notes: operatorNotes || `Operator manual transition to ${targetStatus}`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Transition failed';
      setTransitionError(msg);
    } finally {
      setIsTransitioning(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-xl max-h-[90vh] overflow-y-auto rounded-2xl bg-slate-900 border border-slate-700 p-6 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
              <Satellite className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-slate-100 font-mono">{pass.pass_id}</h3>
                {isLocked ? (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                    <Lock className="w-3 h-3" />
                    LOCKED
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-slate-400 border border-slate-700">
                    <Unlock className="w-3 h-3" />
                    RECONFIGURABLE
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400">{pass.satellite_id} • {pass.ground_station_id}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Status & Priority Row */}
        <div className="my-4 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            {getStatusBadge(status)}
            <span
              className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold ${priorityMeta.bg} ${priorityMeta.color} border border-current`}
            >
              <Zap className="w-3 h-3" />
              {priorityMeta.text}
            </span>
          </div>

          <div className="text-[11px] text-slate-400 font-mono">
            Source: <span className="text-cyan-300">{execution?.telemetry_source || 'Simulated'}</span>
          </div>
        </div>

        {/* Telemetry Comparison: Planned vs Actual */}
        <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800 space-y-2 mb-4">
          <div className="flex items-center justify-between border-b border-slate-800/80 pb-1.5">
            <span className="text-[11px] font-bold text-slate-300 uppercase tracking-wider">
              Telemetry & Data Distinction
            </span>
            <span className="text-[10px] text-slate-500">Manual / Simulated Updates</span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs pt-1">
            <div className="bg-slate-900/60 p-2 rounded-lg border border-slate-800/60">
              <span className="text-[10px] text-slate-400 block">Planned Data Vol.</span>
              <span className="font-mono font-bold text-slate-100">{pass.data_volume_gb.toFixed(1)} GB</span>
            </div>
            <div className="bg-slate-900/60 p-2 rounded-lg border border-slate-800/60">
              <span className="text-[10px] text-emerald-400 block">Actual Delivered Vol.</span>
              <span className="font-mono font-bold text-emerald-300">
                {execution?.actual_data_delivered_gb !== null && execution?.actual_data_delivered_gb !== undefined
                  ? `${execution.actual_data_delivered_gb.toFixed(1)} GB`
                  : 'Pending'}
              </span>
            </div>
            <div className="bg-slate-900/60 p-2 rounded-lg border border-slate-800/60">
              <span className="text-[10px] text-slate-400 block">Est. Downlink Rate</span>
              <span className="font-mono font-bold text-slate-100">{rateMbps} Mbps</span>
            </div>
            <div className="bg-slate-900/60 p-2 rounded-lg border border-slate-800/60">
              <span className="text-[10px] text-cyan-400 block">Measured Rate</span>
              <span className="font-mono font-bold text-cyan-300">
                {execution?.measured_transfer_rate_mbps !== null && execution?.measured_transfer_rate_mbps !== undefined
                  ? `${execution.measured_transfer_rate_mbps.toFixed(1)} Mbps`
                  : 'Pending'}
              </span>
            </div>
          </div>
        </div>

        {/* Operational Grid */}
        <div className="grid grid-cols-2 gap-3 text-xs mb-4">
          <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
            <div className="flex items-center gap-1.5 text-slate-400 mb-1">
              <Radio className="w-3.5 h-3.5 text-cyan-400" />
              <span>Station & Band</span>
            </div>
            <div className="font-semibold text-slate-200">{pass.ground_station_id}</div>
            <div className="text-[11px] text-slate-400 font-mono mt-0.5">
              Band: {pass.channel_band || 'X-band'}
            </div>
          </div>

          <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
            <div className="flex items-center gap-1.5 text-slate-400 mb-1">
              <Gauge className="w-3.5 h-3.5 text-emerald-400" />
              <span>Elevation & Quality</span>
            </div>
            <div className="font-semibold text-slate-200">{pass.max_elevation_deg}° Peak</div>
            <div className="text-[11px] text-emerald-400 mt-0.5">
              {pass.max_elevation_deg >= 45 ? 'Optimal Elevation' : 'Low Horizon Pass'}
            </div>
          </div>

          <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
            <div className="flex items-center gap-1.5 text-slate-400 mb-1">
              <Clock className="w-3.5 h-3.5 text-indigo-400" />
              <span>Planned Contact Window</span>
            </div>
            <div className="font-mono text-slate-200">
              {new Date(pass.start_time).toISOString().substring(11, 19)} -{' '}
              {new Date(pass.end_time).toISOString().substring(11, 19)} UTC
            </div>
            <div className="text-[11px] text-slate-400 mt-0.5">
              Duration: {durationSec}s ({(durationSec / 60).toFixed(1)}m)
            </div>
          </div>

          <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
            <div className="flex items-center gap-1.5 text-slate-400 mb-1">
              <Database className="w-3.5 h-3.5 text-purple-400" />
              <span>Transfer Feasibility</span>
            </div>
            <div className="font-semibold text-slate-200">
              {transferableGb.toFixed(1)} GB Max Cap.
            </div>
            <div className="text-[11px] text-purple-300 mt-0.5">
              Cap: {channelCapacityGb.toFixed(1)} GB
            </div>
          </div>
        </div>

        {/* State Transition Controls */}
        {onTransition && (
          <div className="p-4 rounded-xl bg-slate-950/80 border border-cyan-800/40 mb-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-cyan-300 uppercase tracking-wider flex items-center gap-1.5">
                <Play className="w-3.5 h-3.5" />
                Execution Lifecycle Actions
              </span>
              <span className="text-[11px] text-slate-400">
                Current: <strong className="text-slate-200">{status}</strong>
              </span>
            </div>

            {transitionError && (
              <div className="p-2 rounded bg-rose-500/20 border border-rose-500/40 text-rose-300 text-xs">
                {transitionError}
              </div>
            )}

            {/* Transition Controls depending on state */}
            {status === 'SCHEDULED' && (
              <div className="space-y-2">
                <p className="text-[11px] text-slate-400">
                  Antenna is ready. Transition to <strong>ACQUIRING</strong> to lock this pass against rescheduling.
                </p>
                <div className="flex flex-wrap gap-2">
                  <button
                    disabled={isTransitioning}
                    onClick={() => handleAction('ACQUIRING')}
                    className="px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-medium text-xs transition disabled:opacity-50"
                  >
                    Acquire Carrier →
                  </button>
                  <button
                    disabled={isTransitioning}
                    onClick={() => handleAction('MISSED')}
                    className="px-3 py-1.5 rounded-lg bg-rose-900/60 hover:bg-rose-800 text-rose-200 font-medium text-xs transition disabled:opacity-50"
                  >
                    Mark Missed
                  </button>
                  <button
                    disabled={isTransitioning}
                    onClick={() => handleAction('CANCELLED')}
                    className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs transition disabled:opacity-50"
                  >
                    Cancel Pass
                  </button>
                </div>
              </div>
            )}

            {status === 'ACQUIRING' && (
              <div className="space-y-2">
                <p className="text-[11px] text-sky-300">
                  Carrier tracking active (🔒 Locked). Start downlink transmission when bit sync is established.
                </p>
                <div className="flex flex-wrap gap-2">
                  <button
                    disabled={isTransitioning}
                    onClick={() => handleAction('TRANSMITTING')}
                    className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs transition disabled:opacity-50"
                  >
                    Start Transmitting Downlink →
                  </button>
                  <button
                    disabled={isTransitioning}
                    onClick={() => handleAction('MISSED')}
                    className="px-3 py-1.5 rounded-lg bg-rose-900/60 hover:bg-rose-800 text-rose-200 font-medium text-xs transition disabled:opacity-50"
                  >
                    Signal Loss (Missed)
                  </button>
                  <button
                    disabled={isTransitioning}
                    onClick={() => handleAction('CANCELLED')}
                    className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs transition disabled:opacity-50"
                  >
                    Abort Pass
                  </button>
                </div>
              </div>
            )}

            {status === 'TRANSMITTING' && (
              <div className="space-y-2">
                <p className="text-[11px] text-emerald-300">
                  Downlink stream in progress (🔒 Locked). Specify actual delivered volume on completion.
                </p>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <label className="text-[10px] text-slate-400 block mb-0.5">
                      Actual Delivered Volume (GB)
                    </label>
                    <input
                      type="number"
                      step="0.1"
                      value={actualVolumeInput}
                      onChange={(e) => setActualVolumeInput(e.target.value)}
                      className="w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-slate-100 font-mono text-xs"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-slate-400 block mb-0.5">
                      Operator Notes
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. Signal quality nominal"
                      value={operatorNotes}
                      onChange={(e) => setOperatorNotes(e.target.value)}
                      className="w-full px-2 py-1 rounded bg-slate-900 border border-slate-700 text-slate-100 text-xs"
                    />
                  </div>
                </div>
                <div className="flex flex-wrap gap-2 pt-1">
                  <button
                    disabled={isTransitioning}
                    onClick={() => handleAction('COMPLETED')}
                    className="px-3 py-1.5 rounded-lg bg-teal-600 hover:bg-teal-500 text-white font-medium text-xs transition disabled:opacity-50"
                  >
                    Complete Pass (Mark Successful) ✓
                  </button>
                  <button
                    disabled={isTransitioning}
                    onClick={() => handleAction('MISSED')}
                    className="px-3 py-1.5 rounded-lg bg-rose-900/60 hover:bg-rose-800 text-rose-200 font-medium text-xs transition disabled:opacity-50"
                  >
                    Carrier Lost (Missed)
                  </button>
                  <button
                    disabled={isTransitioning}
                    onClick={() => handleAction('CANCELLED')}
                    className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs transition disabled:opacity-50"
                  >
                    Emergency Abort
                  </button>
                </div>
              </div>
            )}

            {(status === 'COMPLETED' || status === 'MISSED' || status === 'CANCELLED') && (
              <p className="text-[11px] text-slate-400">
                This pass is in a terminal state ({status}) and is immutable.
              </p>
            )}
          </div>
        )}

        {/* Transition Audit Log */}
        {execution && execution.transition_history && execution.transition_history.length > 0 && (
          <div className="p-3 rounded-xl bg-slate-950/40 border border-slate-800/80 mb-4">
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-2">
              Execution Transition History
            </span>
            <div className="space-y-1.5 max-h-32 overflow-y-auto font-mono text-[11px]">
              {execution.transition_history.map((ev, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-1.5 rounded bg-slate-900/60 border border-slate-800/50"
                >
                  <div>
                    <span className="text-slate-400">{ev.from_status || 'INIT'}</span> →{' '}
                    <span className="font-bold text-cyan-300">{ev.to_status}</span>
                    {ev.notes && <span className="text-slate-500 ml-2">({ev.notes})</span>}
                  </div>
                  <span className="text-[10px] text-slate-500">
                    {new Date(ev.timestamp).toISOString().substring(11, 19)} UTC
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

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
