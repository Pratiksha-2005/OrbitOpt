/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useEffect, useState } from 'react';
import {
  GoogleAuthProvider,
  signInWithPopup,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut,
  onAuthStateChanged,
  sendPasswordResetEmail,
  sendEmailVerification,
} from 'firebase/auth';
import type { User } from 'firebase/auth';
import { auth } from '../lib/firebase';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  error: string | null;
  signInWithGoogle: () => Promise<void>;
  loginWithEmail: (email: string, password: string) => Promise<void>;
  registerWithEmail: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  resetPassword: (email: string) => Promise<void>;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (currentUser) => {
      setUser(currentUser);
      setLoading(false);
    });
    return () => unsubscribe();
  }, []);

  const clearError = () => setError(null);

  const getFriendlyErrorMessage = (code: string) => {
    switch (code) {
      case 'auth/user-not-found':
      case 'auth/invalid-credential':
        return 'Invalid email or password.';
      case 'auth/email-already-in-use':
        return 'An account with this email already exists.';
      case 'auth/weak-password':
        return 'Password is too weak. Please use at least 6 characters.';
      case 'auth/popup-closed-by-user':
        return 'Sign-in popup was closed before completing.';
      case 'auth/network-request-failed':
        return 'Network error. Please check your connection.';
      default:
        return 'An unexpected authentication error occurred.';
    }
  };

  const handleAuthError = (err: any) => {
    console.error('Auth error:', err);
    if (err.code) {
      setError(getFriendlyErrorMessage(err.code));
    } else {
      setError('An error occurred during authentication.');
    }
    throw err; // Re-throw to allow component to stop loading state
  };

  const signInWithGoogle = async () => {
    try {
      clearError();
      const provider = new GoogleAuthProvider();
      await signInWithPopup(auth, provider);
    } catch (err: any) {
      handleAuthError(err);
    }
  };

  const loginWithEmail = async (email: string, password: string) => {
    try {
      clearError();
      await signInWithEmailAndPassword(auth, email, password);
    } catch (err: any) {
      handleAuthError(err);
    }
  };

  const registerWithEmail = async (email: string, password: string) => {
    try {
      clearError();
      const userCredential = await createUserWithEmailAndPassword(auth, email, password);
      // Optional: send email verification
      if (userCredential.user) {
        await sendEmailVerification(userCredential.user);
      }
    } catch (err: any) {
      handleAuthError(err);
    }
  };

  const logout = async () => {
    try {
      clearError();
      await signOut(auth);
    } catch (err: any) {
      handleAuthError(err);
    }
  };

  const resetPassword = async (email: string) => {
    try {
      clearError();
      await sendPasswordResetEmail(auth, email);
    } catch (err: any) {
      handleAuthError(err);
    }
  };

  const value = {
    user,
    loading,
    error,
    signInWithGoogle,
    loginWithEmail,
    registerWithEmail,
    logout,
    resetPassword,
    clearError,
  };

  return (
    <AuthContext.Provider value={value}>
      {!loading && children}
    </AuthContext.Provider>
  );
}
