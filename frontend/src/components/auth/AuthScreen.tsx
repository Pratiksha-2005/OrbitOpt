import React, { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { Satellite, Mail, Lock, AlertCircle, Loader2 } from 'lucide-react';
import { Starfield } from '../common/Starfield';

type AuthMode = 'login' | 'register' | 'forgot_password';

export const AuthScreen: React.FC = () => {
  const { 
    signInWithGoogle, 
    loginWithEmail, 
    registerWithEmail, 
    resetPassword, 
    error, 
    clearError 
  } = useAuth();
  
  const [mode, setMode] = useState<AuthMode>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();
    setSuccessMessage(null);
    setIsLoading(true);

    try {
      if (mode === 'login') {
        await loginWithEmail(email, password);
      } else if (mode === 'register') {
        await registerWithEmail(email, password);
        setSuccessMessage('Registration successful! Please check your email for verification.');
      } else if (mode === 'forgot_password') {
        await resetPassword(email);
        setSuccessMessage('Password reset email sent! Check your inbox.');
      }
    } catch (err) {
      console.error(err);
      // Error is handled in AuthContext
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    clearError();
    setIsLoading(true);
    try {
      await signInWithGoogle();
    } catch (err) {
      console.error(err);
      // Error is handled in AuthContext
    } finally {
      setIsLoading(false);
    }
  };

  const switchMode = (newMode: AuthMode) => {
    setMode(newMode);
    clearError();
    setSuccessMessage(null);
    setPassword(''); // Clear password when switching modes
  };

  return (
    <div className="min-h-screen flex flex-col justify-center py-12 sm:px-6 lg:px-8 font-sans relative overflow-hidden bg-[#070a13]">
      <Starfield />

      {/* Subtle radial gradient overlay to focus center */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_0%,#070a13_100%)] z-0"></div>

      <div className="relative z-10 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="flex justify-center text-cyan-400">
          <Satellite size={48} strokeWidth={1.5} className="drop-shadow-[0_0_15px_rgba(34,211,238,0.5)]" />
        </div>
        <h2 className="mt-6 text-center text-3xl font-extrabold text-white drop-shadow-md">
          OrbitOpt
        </h2>
        <p className="mt-2 text-center text-sm text-cyan-100/70 font-medium">
          {mode === 'login' && 'Sign in to access mission control'}
          {mode === 'register' && 'Create a new mission control account'}
          {mode === 'forgot_password' && 'Reset your password'}
        </p>
      </div>

      <div className="relative z-10 mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-slate-900/40 backdrop-blur-xl py-8 px-4 shadow-2xl border border-white/10 sm:rounded-2xl sm:px-10">
          
          {(error || successMessage) && (
            <div className={`mb-4 p-4 rounded-md flex items-start gap-3 ${error ? 'bg-red-900/30 border border-red-500/30 text-red-200' : 'bg-emerald-900/30 border border-emerald-500/30 text-emerald-200'}`}>
              <AlertCircle size={20} className="mt-0.5 flex-shrink-0" />
              <div className="text-sm font-medium">{error || successMessage}</div>
            </div>
          )}

          <form className="space-y-6" onSubmit={handleSubmit}>
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-slate-300">
                Email address
              </label>
              <div className="mt-1 relative rounded-md shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
                  <Mail size={18} />
                </div>
                <input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="block w-full pl-10 bg-slate-900 border border-slate-700 rounded-md py-2 text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-cyan-500 focus:border-cyan-500 sm:text-sm"
                  placeholder="commander@orbitopt.space"
                />
              </div>
            </div>

            {mode !== 'forgot_password' && (
              <div>
                <label htmlFor="password" className="block text-sm font-medium text-slate-300">
                  Password
                </label>
                <div className="mt-1 relative rounded-md shadow-sm">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
                    <Lock size={18} />
                  </div>
                  <input
                    id="password"
                    name="password"
                    type="password"
                    autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="block w-full pl-10 bg-slate-900 border border-slate-700 rounded-md py-2 text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-cyan-500 focus:border-cyan-500 sm:text-sm"
                    placeholder="••••••••"
                  />
                </div>
              </div>
            )}

            {mode === 'login' && (
              <div className="flex items-center justify-end">
                <div className="text-sm">
                  <button
                    type="button"
                    onClick={() => switchMode('forgot_password')}
                    className="font-medium text-cyan-400 hover:text-cyan-300"
                  >
                    Forgot your password?
                  </button>
                </div>
              </div>
            )}

            <div>
              <button
                type="submit"
                disabled={isLoading}
                className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-slate-900 bg-cyan-400 hover:bg-cyan-300 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500 focus:ring-offset-slate-900 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isLoading ? (
                  <Loader2 className="animate-spin" size={20} />
                ) : mode === 'login' ? (
                  'Sign in'
                ) : mode === 'register' ? (
                  'Create account'
                ) : (
                  'Send reset link'
                )}
              </button>
            </div>
          </form>

          {mode !== 'forgot_password' && (
            <div className="mt-6">
              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-slate-700" />
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="px-2 bg-[#0f172a] text-slate-400">Or continue with</span>
                </div>
              </div>

              <div className="mt-6">
                <button
                  type="button"
                  disabled={isLoading}
                  onClick={handleGoogleSignIn}
                  className="w-full flex justify-center items-center gap-3 py-2 px-4 border border-slate-700 rounded-md shadow-sm text-sm font-medium text-slate-200 bg-slate-800 hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500 focus:ring-offset-slate-900 disabled:opacity-50 transition-colors"
                >
                  <svg className="w-5 h-5" viewBox="0 0 24 24">
                    <path
                      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                      fill="#4285F4"
                    />
                    <path
                      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                      fill="#34A853"
                    />
                    <path
                      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                      fill="#FBBC05"
                    />
                    <path
                      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                      fill="#EA4335"
                    />
                  </svg>
                  <span>Google</span>
                </button>
              </div>
            </div>
          )}

          <div className="mt-6 flex justify-center gap-2 text-sm text-slate-400">
            {mode === 'login' ? (
              <>
                <span>New to OrbitOpt?</span>
                <button type="button" onClick={() => switchMode('register')} className="text-cyan-400 hover:text-cyan-300 font-medium">Sign up</button>
              </>
            ) : mode === 'register' ? (
              <>
                <span>Already have an account?</span>
                <button type="button" onClick={() => switchMode('login')} className="text-cyan-400 hover:text-cyan-300 font-medium">Sign in</button>
              </>
            ) : (
              <button type="button" onClick={() => switchMode('login')} className="text-cyan-400 hover:text-cyan-300 font-medium">Back to sign in</button>
            )}
          </div>

        </div>
      </div>
    </div>
  );
};
