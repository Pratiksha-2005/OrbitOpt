import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface ErrorAlertProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export const ErrorAlert: React.FC<ErrorAlertProps> = ({
  title = 'API Communication Error',
  message,
  onRetry,
}) => {
  return (
    <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-800/60 text-rose-200 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
        <div>
          <h4 className="text-sm font-semibold text-rose-100">{title}</h4>
          <p className="text-xs text-rose-300 mt-0.5">{message}</p>
        </div>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-900/60 hover:bg-rose-800 text-xs font-medium text-rose-100 border border-rose-700/60 transition self-start sm:self-center"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Retry Connection
        </button>
      )}
    </div>
  );
};
