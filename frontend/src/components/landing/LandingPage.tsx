import React from 'react';
import { LandingHero } from './LandingHero';
import { LandingHowItWorks } from './LandingHowItWorks';
import { LandingFeatures } from './LandingFeatures';
import { Satellite } from 'lucide-react';

const CURRENT_YEAR = new Date().getFullYear();

interface LandingPageProps {
  onNavigateToAuth: () => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({ onNavigateToAuth }) => {
  return (
    <div className="min-h-screen bg-[#070a13] text-slate-100 flex flex-col font-sans overflow-x-hidden">
      {/* Top Navbar */}
      <header className="fixed top-0 z-50 w-full border-b border-slate-800/80 bg-slate-950/60 backdrop-blur-md px-4 sm:px-6 py-3">
        <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-600 via-indigo-600 to-purple-600 p-0.5 shadow-lg shadow-cyan-500/10">
              <div className="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center">
                <Satellite className="w-5 h-5 text-cyan-400" />
              </div>
            </div>
            <span className="font-bold text-lg tracking-tight bg-gradient-to-r from-cyan-400 via-sky-300 to-indigo-300 bg-clip-text text-transparent">
              OrbitOpt
            </span>
          </div>
          <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-slate-300">
            <a href="#hero" className="hover:text-cyan-400 focus:outline-none focus:text-cyan-400 transition-colors">Home</a>
            <a href="#how-it-works" className="hover:text-cyan-400 focus:outline-none focus:text-cyan-400 transition-colors">How It Works</a>
            <a href="#features" className="hover:text-cyan-400 focus:outline-none focus:text-cyan-400 transition-colors">Features</a>
          </nav>
          <div className="flex items-center gap-4">
            <button
              onClick={onNavigateToAuth}
              className="text-sm font-medium text-slate-300 hover:text-white focus:outline-none focus:text-white transition-colors"
            >
              Sign In
            </button>
            <button
              onClick={onNavigateToAuth}
              className="hidden sm:inline-flex items-center justify-center px-4 py-2 text-sm font-medium text-slate-900 bg-cyan-400 rounded-md hover:bg-cyan-300 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-slate-950 focus:ring-cyan-400 transition-all shadow-[0_0_15px_rgba(34,211,238,0.3)] hover:shadow-[0_0_25px_rgba(34,211,238,0.5)]"
            >
              Launch Mission Control
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1">
        <LandingHero onNavigateToAuth={onNavigateToAuth} />
        <LandingHowItWorks />
        <LandingFeatures />
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800 bg-[#04060b] py-8 text-center text-sm text-slate-500">
        <div className="max-w-7xl mx-auto px-4">
          <p>&copy; {CURRENT_YEAR} OrbitOpt. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
};
