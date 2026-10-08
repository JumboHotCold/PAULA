/**
 * LoginPage — Dual-Entry Landing Page
 * ======================================
 * Entry point for PauliBot with two access modes:
 * 1. Student Portal: Login with Student ID / Password
 * 2. Guest Access: Continue without an account
 *
 * Tracks user type (STUDENT | GUEST) in React state via onLogin callback.
 */

import { useState } from 'react';
import { getCookie, ensureCsrfToken } from '../api/chatApi';
import MaterialIcon from './MaterialIcon';

export default function LoginPage({ onLogin }) {
  const [studentId, setStudentId] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  /**
   * Handle Student Login via Django session auth
   */
  const handleStudentLogin = async (e) => {
    e.preventDefault();
    if (!studentId.trim() || !password.trim()) {
      setError('Please enter both Student ID and Password.');
      return;
    }

    setIsLoading(true);
    setError('');

    try {
      await ensureCsrfToken();
      const csrfToken = getCookie('csrftoken');
      const res = await fetch('/api/login', {
        method: 'POST',
        credentials: 'include',
        headers: { 
          'Content-Type': 'application/json',
          ...(csrfToken && { 'X-CSRFToken': csrfToken }),
        },
        body: JSON.stringify({
          username: studentId.trim(),
          password: password,
        }),
      });

      const data = await res.json();

      if (res.ok) {
        onLogin({ type: 'STUDENT', id: studentId.trim(), name: data.name || studentId.trim() });
      } else {
        setError(data.error || data.student_id?.[0] || 'Invalid Student ID or Password.');
      }
    } catch (err) {
      setError('Connection error. Please ensure the server is running.');
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Handle Guest Access — no authentication needed
   */
  const handleGuestAccess = () => {
    onLogin({ type: 'GUEST', id: null, name: 'Guest' });
  };

  return (
    <div className="login-bg h-full w-full flex items-center justify-center p-4 overflow-auto">
      {/* Background decorative elements */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-20%] left-[-10%] w-[500px] h-[500px] rounded-full bg-spus-green/5 blur-[100px]" />
        <div className="absolute bottom-[-20%] right-[-10%] w-[400px] h-[400px] rounded-full bg-spus-gold/5 blur-[100px]" />
      </div>

      <div className="relative z-10 w-full max-w-5xl">
        {/* Main Entry Card */}
        <div className="entry-card glass-card rounded-3xl overflow-hidden">
          <div className="flex flex-col lg:flex-row">

            {/* ============================================================
                LEFT SIDE — Student Portal Login
                ============================================================ */}
            <div className="flex-1 p-8 lg:p-12 flex flex-col justify-center">
              {/* Logo & Title */}
              <div className="flex items-center gap-4 mb-8 animate-fade-in-up">
                <div className="w-14 h-14 rounded-2xl flex items-center justify-center overflow-hidden shadow-lg shadow-spus-green/20 border border-spus-green/20">
                  <img
                    src="/spus-logo.webp"
                    alt="SPUS Logo"
                    className="w-14 h-14 object-contain"
                  />
                </div>
                <div>
                  <h1 className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'var(--font-family-heading)' }}>
                    PauliBot
                  </h1>
                  <p className="text-sm text-text-secondary font-light">
                    Saint Paul University Surigao
                  </p>
                </div>
              </div>

              {/* Student Portal Header */}
              <div className="mb-6 animate-fade-in-up animation-delay-100">
                <h2 className="text-lg font-semibold text-text-primary mb-1" style={{ fontFamily: 'var(--font-family-heading)' }}>
                  Student Portal
                </h2>
                <p className="text-sm text-text-secondary font-light">
                  Sign in with your student credentials to access personalized assistance.
                </p>
              </div>

              {/* Login Form */}
              <form onSubmit={handleStudentLogin} className="space-y-4 animate-fade-in-up animation-delay-200">
                {/* Error Message */}
                {error && (
                  <div className="px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                    {error}
                  </div>
                )}

                {/* Student ID */}
                <div>
                  <label htmlFor="student-id" className="block text-xs text-text-secondary uppercase tracking-wider font-medium mb-2">
                    Student ID
                  </label>
                  <input
                    id="student-id"
                    type="text"
                    value={studentId}
                    onChange={(e) => setStudentId(e.target.value)}
                    placeholder="e.g. 2024-00123"
                    autoComplete="username"
                    className="w-full px-4 py-3 rounded-xl bg-bg-input border border-glass-border
                               text-text-primary text-sm placeholder:text-text-muted
                               focus:outline-none focus:border-spus-green/50 focus:ring-1 focus:ring-spus-green/20
                               transition-all duration-200"
                  />
                </div>

                {/* Password */}
                <div>
                  <label htmlFor="password" className="block text-xs text-text-secondary uppercase tracking-wider font-medium mb-2">
                    Password
                  </label>
                  <input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your password"
                    autoComplete="current-password"
                    className="w-full px-4 py-3 rounded-xl bg-bg-input border border-glass-border
                               text-text-primary text-sm placeholder:text-text-muted
                               focus:outline-none focus:border-spus-green/50 focus:ring-1 focus:ring-spus-green/20
                               transition-all duration-200"
                  />
                </div>

                {/* Login Button */}
                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full py-3.5 rounded-xl font-semibold text-sm
                             bg-gradient-to-r from-spus-green to-spus-green-600
                             text-white cursor-pointer
                             hover:shadow-lg hover:shadow-spus-green/25 hover:from-spus-green-400 hover:to-spus-green
                             disabled:opacity-50 disabled:cursor-not-allowed
                             transition-all duration-300 active:scale-[0.98]"
                >
                  {isLoading ? (
                    <span className="flex items-center justify-center gap-2">
                      <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                      Signing in...
                    </span>
                  ) : (
                    'Sign In'
                  )}
                </button>
              </form>
            </div>

            {/* ============================================================
                DIVIDER
                ============================================================ */}
            <div className="hidden lg:flex items-center">
              <div className="w-px h-[60%] bg-gradient-to-b from-transparent via-glass-border to-transparent" />
            </div>
            <div className="lg:hidden mx-8">
              <div className="h-px w-full bg-gradient-to-r from-transparent via-glass-border to-transparent" />
            </div>

            {/* ============================================================
                RIGHT SIDE — Guest Access
                ============================================================ */}
            <div className="flex-1 p-8 lg:p-12 flex flex-col items-center justify-center text-center">
              <div className="animate-fade-in-up animation-delay-300">
                {/* Guest Icon */}
                <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-gradient-to-br from-spus-gold/10 to-spus-gold/5 border border-spus-gold/20 flex items-center justify-center">
                  <svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-spus-gold">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
                  </svg>
                </div>

                <h2 className="text-lg font-semibold text-text-primary mb-2" style={{ fontFamily: 'var(--font-family-heading)' }}>
                  Visitor Access
                </h2>
                <p className="text-sm text-text-secondary font-light mb-8 max-w-xs mx-auto leading-relaxed">
                  Explore PauliBot as a guest. Ask about admissions, programs, campus facilities, and more — no account needed.
                </p>

                {/* Guest Button */}
                <button
                  onClick={handleGuestAccess}
                  className="w-full max-w-xs py-3.5 rounded-xl font-semibold text-sm
                             bg-gradient-to-r from-spus-gold/15 to-spus-gold/10
                             text-spus-gold border border-spus-gold/30
                             cursor-pointer
                             hover:from-spus-gold/25 hover:to-spus-gold/15 hover:border-spus-gold/50
                             hover:shadow-lg hover:shadow-spus-gold/10
                             transition-all duration-300 active:scale-[0.98]"
                >
                  Continue as Guest →
                </button>

                {/* Features list */}
                <div className="mt-8 space-y-3 text-left max-w-xs mx-auto">
                  {[
                    { icon: 'chat', text: 'AI-powered campus assistant', color: '#10B981' },
                    { icon: 'assignment', text: 'Enrollment & admissions info', color: '#F59E0B' },
                    { icon: 'location_on', text: 'Campus locations & navigation', color: '#3B82F6' },
                  ].map((item, i) => (
                    <div key={i} className="flex items-center gap-3 text-xs text-text-muted">
                      <MaterialIcon name={item.icon} size={16} color={item.color} />
                      <span>{item.text}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

          </div>
        </div>

        {/* Footer */}
        <p className="text-center text-[0.65rem] text-text-muted mt-6 animate-fade-in-up animation-delay-400">
          © 2026 Saint Paul University Surigao — PauliBot v2.0
        </p>
      </div>
    </div>
  );
}
