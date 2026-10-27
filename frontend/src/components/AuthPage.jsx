import { useState } from 'react';
import { getCookie, ensureCsrfToken } from '../api/chatApi';
import ThemeToggle from './ThemeToggle';

export default function AuthPage({ onLogin, onNavigateRegister }) {
  const [studentId, setStudentId] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleStudentLogin = async (e) => {
    e.preventDefault();
    if (!studentId || !password) return;

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
        body: JSON.stringify({ student_id: studentId, password }),
      });
      const data = await res.json();

      if (res.ok) {
        onLogin({ type: 'STUDENT', id: studentId, name: data.name || 'Student' });
      } else {
        setError(data.error || 'Invalid credentials.');
      }
    } catch (err) {
      setError('Connection error.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      <nav className="navbar">
        <a href="#" className="brand">
          <img 
            src="/spus-logo.webp" 
            alt="SPUS Logo" 
            style={{ height: '50px', width: '50px', filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.2))', objectFit: 'contain' }}
          />
          <div className="brand-text">
            <h1>PAULA</h1>
            <p>Paulinian Artificial User Support and Learning Assistant • SPUS</p>
          </div>
        </a>
        <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
          <ThemeToggle />
        </div>
      </nav>

      <div className="main-container">
        <div className="landing-card">
          
          {/* Login Side */}
          <div className="login-section">
            <div className="section-header">
              <h2>Student Portal</h2>
              <p>Log in to access personalized assistance and chat history.</p>
            </div>

            {error && (
              <div className="error-message">{error}</div>
            )}

            <form onSubmit={handleStudentLogin}>
              <div className="form-group">
                <input
                  type="text"
                  id="student_id"
                  className="form-input"
                  placeholder=" "
                  value={studentId}
                  onChange={(e) => setStudentId(e.target.value)}
                  required
                />
                <label htmlFor="student_id" className="form-label">Student ID</label>
              </div>

              <div className="form-group">
                <input
                  type="password"
                  id="password"
                  className="form-input"
                  placeholder=" "
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
                <label htmlFor="password" className="form-label">Password</label>
              </div>

              <button type="submit" disabled={isLoading} className="btn btn-primary">
                {isLoading ? 'Loading...' : 'Login'}
              </button>
            </form>
          </div>

          {/* Guest Side */}
          <div className="guest-section">
            <div className="guest-content">
              <h3>Visitor Access</h3>
              <p style={{ marginBottom: '25px', opacity: 0.9 }}>
                Need quick answers? Interact with PAULA instantly without logging in.
                Perfect for prospective students and visitors.
              </p>

              <ul className="feature-list">
                <li>
                  <svg viewBox="0 0 24 24">
                    <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
                  </svg>
                  Instant Answers
                </li>
                <li>
                  <svg viewBox="0 0 24 24">
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14H9v-2h2v2zm0-5H9V7h2v5z" />
                  </svg>
                  Admissions Info
                </li>
                <li>
                  <svg viewBox="0 0 24 24">
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 4c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm6 12H6v-1c0-2 4-3.1 6-3.1s6 1.1 6 3.1v1z" />
                  </svg>
                  No Registration
                </li>
              </ul>

              <button onClick={() => onLogin({ type: 'GUEST', id: null, name: 'Guest' })} className="btn btn-guest">
                Continue as Guest
              </button>

              <p className="guest-note">
                * Chat history is not saved in guest mode.
              </p>
            </div>
          </div>
          
        </div>
      </div>

      <footer className="footer">
        &copy; {new Date().getFullYear()} Saint Paul University Surigao. All Rights Reserved.
      </footer>
    </>
  );
}
