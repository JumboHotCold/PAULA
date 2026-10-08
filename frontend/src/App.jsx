import { useState, useCallback, useEffect } from 'react';
import './App.css';
import MaterialIcon from './components/MaterialIcon';

import AuthPage from './components/AuthPage';
import RegisterPage from './components/RegisterPage';
import Dashboard from './components/Dashboard';
import AdminDashboard from './components/AdminDashboard';
import ThemeToggle from './components/ThemeToggle';

import { 
  sendMessage, 
  ensureCsrfToken, 
  fetchConversations, 
  getCookie,
  deleteConversation,
  fetchConversationDetails
} from './api/chatApi';

const GUEST_GREETING = "Hello! Welcome to Saint Paul University Surigao!\n\nI'm PauliBot, your virtual campus assistant. I can help you with admissions, office locations, tuition fees, staff info, and more.\n\nHow may I assist you today?";

function AdminLogin({ onLogin, onBack }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleAdminLogin = async (e) => {
    e.preventDefault();
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
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (res.ok) {
        if (data.is_superuser) {
          onLogin({ type: 'ADMIN', id: username, name: data.name, is_superuser: true });
        } else {
          setError('Access denied. Administrator privileges required.');
        }
      } else {
        const errorMsg = data.non_field_errors ? data.non_field_errors[0] : (data.error || 'Invalid username or password.');
        setError(errorMsg);
      }
    } catch (err) {
      setError('Connection error. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'var(--color-bg)', padding: '1rem', position: 'relative' }}>
       <div style={{ position: 'absolute', top: '20px', right: '20px', zIndex: 10 }}>
         <ThemeToggle />
       </div>
       <div style={{ backgroundColor: 'var(--color-surface)', padding: '2.5rem', borderRadius: '1rem', boxShadow: '0 10px 30px rgba(0, 0, 0, 0.25)', width: '100%', maxWidth: '400px', border: '1px solid var(--color-border)', transition: 'background-color 0.2s, border-color 0.2s' }}>
          <div style={{ width: '64px', height: '64px', margin: '0 auto 1rem', backgroundColor: 'rgba(16, 185, 129, 0.15)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
             <MaterialIcon name="shield" size={28} color="#10B981" />
          </div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 'bold', textAlign: 'center', color: 'var(--color-primary)', marginBottom: '0.5rem', fontFamily: 'var(--font-family-heading)', letterSpacing: '-0.015em' }}>Admin Access</h2>
          <p style={{ textAlign: 'center', fontSize: '0.875rem', color: 'var(--color-text-muted)', marginBottom: '1.5rem' }}>Restricted to authorized personnel</p>
          
          {error && <div style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', fontSize: '0.875rem', padding: '0.75rem', borderRadius: '0.5rem', border: '1px solid rgba(239, 68, 68, 0.2)', marginBottom: '1rem', textAlign: 'center' }}>{error}</div>}
          
          <form onSubmit={handleAdminLogin} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
             <div>
                <label style={{ fontSize: '0.75rem', fontWeight: 'bold', color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.25rem', display: 'block' }}>Username / ID</label>
                <input type="text" value={username} onChange={e => setUsername(e.target.value)} required style={{ width: '100%', backgroundColor: 'var(--color-input-bg)', border: '1px solid var(--color-border)', color: 'var(--color-text)', padding: '0.75rem 1rem', borderRadius: '0.75rem', outline: 'none', transition: 'all 0.2s' }} />
             </div>
             <div>
                <label style={{ fontSize: '0.75rem', fontWeight: 'bold', color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.25rem', display: 'block' }}>Password</label>
                <input type="password" value={password} onChange={e => setPassword(e.target.value)} required style={{ width: '100%', backgroundColor: 'var(--color-input-bg)', border: '1px solid var(--color-border)', color: 'var(--color-text)', padding: '0.75rem 1rem', borderRadius: '0.75rem', outline: 'none', transition: 'all 0.2s' }} />
             </div>
             <button type="submit" disabled={isLoading} style={{ width: '100%', backgroundColor: 'var(--color-primary)', color: '#ffffff', padding: '0.875rem', borderRadius: '0.75rem', fontWeight: 'bold', cursor: isLoading ? 'not-allowed' : 'pointer', border: 'none', transition: 'all 0.2s', marginTop: '0.5rem' }}>
               {isLoading ? 'Authenticating...' : 'Secure Login'}
             </button>
             <button type="button" onClick={onBack} style={{ width: '100%', textAlign: 'center', fontSize: '0.875rem', color: 'var(--color-text-muted)', background: 'none', border: 'none', cursor: 'pointer', outline: 'none', marginTop: '0.5rem' }}>
               ← Back to Home
             </button>
          </form>
       </div>
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState(null); // null = not logged in
  const [currentView, setCurrentView] = useState(() => {
    const path = window.location.pathname;
    if (path === '/admin') return 'admin';
    if (path === '/register') return 'register';
    return 'login';
  });
  
  const [messages, setMessages] = useState([]);
  const [isTyping, setIsTyping] = useState(false);
  const [conversationId, setConversationId] = useState(null);
  const [conversations, setConversations] = useState([]);

  // Restore session
  useEffect(() => {
    ensureCsrfToken();
    const storedUser = localStorage.getItem('paulibot_user');
    if (storedUser) {
      try {
        const parsed = JSON.parse(storedUser);
        setUser(parsed);
        
        if (parsed.is_superuser && window.location.pathname === '/admin') {
          setCurrentView('admin');
        } else {
          setCurrentView('chat');
        }

        if (parsed.type === 'GUEST') {
           setMessages([]);
        }
      } catch (e) {
        localStorage.removeItem('paulibot_user');
      }
    }
  }, []);

  // Fetch history if student
  useEffect(() => {
    if (user?.type === 'STUDENT') {
      fetchConversations()
        .then(data => setConversations(data))
        .catch(console.error);
    }
  }, [user]);

  const handleLogin = useCallback((userData) => {
    setUser(userData);
    localStorage.setItem('paulibot_user', JSON.stringify(userData));
    
    if (userData.type === 'GUEST') {
      setMessages([]);
    } else {
      setMessages([]);
    }
    setConversationId(null);
    // If superuser, show admin dashboard first; otherwise, go to chat
    if (userData.is_superuser) {
      setCurrentView('admin');
      window.history.pushState(null, '', '/admin');
    } else {
      setCurrentView('chat');
      window.history.pushState(null, '', '/');
    }
  }, []);

  const handleUpdateUser = useCallback((updatedUserData) => {
    setUser(updatedUserData);
    localStorage.setItem('paulibot_user', JSON.stringify(updatedUserData));
  }, []);

  const handleLogout = useCallback(() => {
    if (user?.type === 'GUEST') {
      setUser(null);
      setMessages([]);
      setConversations([]);
      setConversationId(null);
      localStorage.removeItem('paulibot_user');
      setCurrentView('login');
      return;
    }

    import('sweetalert2').then((SwalModule) => {
      const Swal = SwalModule.default;
      Swal.fire({
        title: 'Ready to leave?',
        text: "Are you sure you want to log out of PauliBot?",
        icon: 'question',
        showCancelButton: true,
        confirmButtonColor: '#005529',
        cancelButtonColor: '#d33',
        confirmButtonText: 'Yes, log out!'
      }).then((result) => {
        if (result.isConfirmed) {
          setUser(null);
          setMessages([]);
          setConversations([]);
          setConversationId(null);
          localStorage.removeItem('paulibot_user');
          setCurrentView('login');
          const csrfToken = getCookie('csrftoken');
          fetch('/api/login', { 
            method: 'DELETE', 
            credentials: 'include',
            headers: {
              ...(csrfToken && { 'X-CSRFToken': csrfToken }),
            }
          }).catch(() => {});
        }
      });
    });
  }, [user]);

  const handleDeleteChat = useCallback(async (id) => {
    import('sweetalert2').then((SwalModule) => {
      const Swal = SwalModule.default;
      Swal.fire({
        title: 'Delete Conversation?',
        text: "This action cannot be undone.",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        cancelButtonColor: '#3085d6',
        confirmButtonText: 'Yes, delete it!'
      }).then(async (result) => {
        if (result.isConfirmed) {
          try {
            await deleteConversation(id);
            const updatedConversations = await fetchConversations();
            setConversations(updatedConversations);
            if (conversationId === id) {
              setConversationId(null);
              setMessages([]);
            }
            Swal.fire({ title: 'Deleted!', text: 'Conversation removed.', icon: 'success', timer: 1500, showConfirmButton: false });
          } catch (err) {
            console.error(err);
            Swal.fire('Error', 'Could not delete conversation.', 'error');
          }
        }
      });
    });
  }, [conversationId, user]);

  const handleNewChat = useCallback(() => {
    setMessages([]);
    setConversationId(null);
    fetchConversations().then(data => setConversations(data)).catch(console.error);
  }, [user]);

  const handleSend = useCallback(
    async (text) => {
      setMessages((prev) => [...prev, { text, isUser: true }]);
      setIsTyping(true);

      try {
        const data = await sendMessage(text, conversationId);

        if (data.conversation_id && user?.type === 'STUDENT') {
          setConversationId(data.conversation_id);
          fetchConversations().then(data => setConversations(data)).catch(console.error);
        }

        setTimeout(() => {
          setIsTyping(false);
          setMessages((prev) => [
            ...prev,
            { text: data.response || 'Sorry, I encountered an error.', sources: data.sources || [], action: data.action, action_data: data.action_data, isUser: false },
          ]);
        }, 600); // 600ms network delay simulation from your index.html logic
      } catch (err) {
        setIsTyping(false);
        setMessages((prev) => [
          ...prev,
          { text: "Network error. Please try again.", isUser: false },
        ]);
      }
    },
    [conversationId, user]
  );

  // Router Logic
  if (currentView === 'register') {
    return <RegisterPage onNavigateLogin={() => setCurrentView('login')} />;
  }

  // Admin Dashboard
  if (currentView === 'admin') {
    if (user?.is_superuser) {
      return (
        <AdminDashboard
          user={user}
          onBackToChat={() => {
             setCurrentView('chat');
             window.history.pushState(null, '', '/');
          }}
        />
      );
    } else if (user) {
      // If logged in but not superuser, force them to chat
      setCurrentView('chat');
    } else {
      // Not logged in but trying to access admin
      return <AdminLogin onLogin={handleLogin} onBack={() => { setCurrentView('login'); window.history.pushState(null, '', '/'); }} />;
    }
  }

  // If a user is not logged in but they are trying to view something else
  if (!user && currentView !== 'login') {
    return <AuthPage onLogin={handleLogin} onNavigateRegister={() => setCurrentView('register')} />;
  }

  if (currentView === 'login' && !user) {
    // Currently, it uses AuthPage. We maintain this as per existing code.
    return <AuthPage onLogin={handleLogin} onNavigateRegister={() => setCurrentView('register')} />;
  }

  return (
    <Dashboard
      user={user}
      onLogout={handleLogout}
      onNavigateLogin={() => { handleLogout(); setCurrentView('login'); }}
      messages={messages}
      isTyping={isTyping}
      onSend={handleSend}
      onNewChat={handleNewChat}
      conversations={conversations}
      onDeleteChat={handleDeleteChat}
      onNavigateAdmin={user?.is_superuser ? () => setCurrentView('admin') : null}
      onUpdateUser={handleUpdateUser}
      onLoadChat={async (id) => {
        const details = await fetchConversationDetails(id);
        setMessages(details.map(d => ({ text: d.message, isUser: true })).flatMap((m, i) => [m, { text: details[i].response, isUser: false}]));
        setConversationId(id);
      }}
    />
  );
}
