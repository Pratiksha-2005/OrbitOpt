import React from 'react';
import { Satellite, RefreshCw } from 'lucide-react';

interface EmptyStateProps {
  title?: string;
  description?: string;
  actionText?: string;
  onAction?: () => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title = 'No Schedule Opportunities Found',
  description = 'No satellite passes or ground stations match the current filter criteria.',
  actionText,
  onAction,
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center rounded-xl bg-slate-900/40 border border-slate-800/80">
      <div className="w-14 h-14 rounded-2xl bg-slate-800/80 border border-slate-700/50 flex items-center justify-center text-slate-400 mb-4">
        <Satellite className="w-7 h-7" />
      </div>
      <h3 className="text-base font-semibold text-slate-200 mb-1">{title}</h3>
      <p className="text-sm text-slate-400 max-w-sm mb-6">{description}</p>
      {actionText && onAction && (
        <button
          onClick={onAction}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-sm font-medium text-slate-200 border border-slate-700 transition"
        >
          <RefreshCw className="w-4 h-4" />
          {actionText}
        </button>
      )}
    </div>
  );
};
