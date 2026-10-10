import React from 'react';
import { Radio } from 'lucide-react';

interface LoadingStateProps {
  message?: string;
  submessage?: string;
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  message = 'Calculating Optimal Orbit Schedule...',
  submessage = 'Executing solver constraints and antenna repointing matrices',
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center rounded-xl bg-slate-900/60 border border-slate-800">
      <div className="relative mb-6">
        <div className="w-16 h-16 rounded-full border-4 border-cyan-500/20 border-t-cyan-400 animate-spin flex items-center justify-center" />
        <div className="absolute inset-0 flex items-center justify-center">
          <Radio className="w-6 h-6 text-cyan-400 animate-pulse" />
        </div>
      </div>
      <h3 className="text-lg font-semibold text-slate-100 mb-1">{message}</h3>
      <p className="text-sm text-slate-400 max-w-md">{submessage}</p>
    </div>
  );
};
