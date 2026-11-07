import { useState } from 'react';
import ThemeToggle from './ThemeToggle';

export default function RegisterPage({ onNavigateLogin }) {
  const [formData, setFormData] = useState({
    student_id: '',
    username: '',
    email: '',
    first_name: '',
    last_name: '',
    password: ''
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      const res = await fetch('/api/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });
      const data = await res.json();

      if (res.ok) {
        onNavigateLogin();
      } else {
        const errMsg = Object.values(data).flat().join(', ') || 'Registration failed.';
        setError(errMsg);
      }
    } catch (err) {
      setError('Connection error.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="register-wrapper" style={{ position: 'relative' }}>
      <div style={{ position: 'absolute', top: '20px', right: '20px', zIndex: 10 }}>
        <ThemeToggle />
      </div>
      <div className="register-container">
        
        <div className="register-header">
          <img 
            src="/spus-logo.webp" 
            alt="SPUS Logo" 
            style={{ height: '60px', width: '60px', objectFit: 'contain', marginBottom: '10px', filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.2))' }}
          />
          <h1>Create Account</h1>
          <p>Join the Paulinian Community</p>
        </div>

        <div className="register-content">
          {error && (
            <div className="error-message">{error}</div>
          )}

          <form onSubmit={handleRegister}>
            <div className="form-group" style={{ marginBottom: '20px' }}>
              <label htmlFor="student_id" className="reg-label">Student ID</label>
              <input
                type="text" id="student_id" name="student_id" required
                className="reg-input" placeholder="e.g., 2024-00001"
                onChange={handleChange} value={formData.student_id}
              />
            </div>

            <div className="form-group" style={{ marginBottom: '20px' }}>
              <label htmlFor="username" className="reg-label">Username</label>
              <input type="text" id="username" name="username" required className="reg-input" onChange={handleChange} value={formData.username} />
            </div>

            <div className="form-group" style={{ marginBottom: '20px' }}>
              <label htmlFor="email" className="reg-label">Email Address</label>
              <input type="email" id="email" name="email" required className="reg-input" onChange={handleChange} value={formData.email} />
            </div>

            <div className="register-name-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px', marginBottom: '20px' }}>
              <div>
                <label htmlFor="first_name" className="reg-label">First Name</label>
                <input type="text" id="first_name" name="first_name" required className="reg-input" onChange={handleChange} value={formData.first_name} />
              </div>
              <div>
                <label htmlFor="last_name" className="reg-label">Last Name</label>
                <input type="text" id="last_name" name="last_name" required className="reg-input" onChange={handleChange} value={formData.last_name} />
              </div>
            </div>

            <div className="form-group" style={{ marginBottom: '20px' }}>
              <label htmlFor="password" className="reg-label">Password</label>
              <input type="password" id="password" name="password" required className="reg-input" onChange={handleChange} value={formData.password} />
              <div className="help-text">Must be at least 8 characters long</div>
            </div>

            <button type="submit" disabled={isLoading} className="btn btn-primary outline-none">
              {isLoading ? 'Creating...' : 'Create Account'}
            </button>
            
            <button type="button" onClick={onNavigateLogin} className="btn-secondary">
              Already have an account? Login
            </button>
          </form>
        </div>

      </div>
    </div>
  );
}
