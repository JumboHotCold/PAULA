import { useState, useCallback, useEffect, useRef } from 'react';
import { createSendGuard } from './sendGuard';
import './App.css';
import MaterialIcon from './components/MaterialIcon';

import AuthPage from './components/AuthPage';
import RegisterPage from './components/RegisterPage';
import Dashboard from './components/Dashboard';
import AdminDashboard from './components/AdminDashboard';
import ThemeToggle from './components/ThemeToggle';
import AdminSessionNotice from './components/AdminSessionNotice';
import { restoreIdentity, userFromSession } from './authIdentity';

import { 
  sendMessage, 
  chatErrorMessage,
  ensureCsrfToken, 
  fetchConversations, 
  getCookie,
  deleteConversation,
  fetchConversationDetails,
  logoutSession,
  sessionStatus
} from './api/chatApi';

function chatSession(user, fresh = false) {
  const key = user?.type === 'GUEST' ? null : `paula-chat:${user?.id}`;
  const current = key && !fresh ? sessionStorage.getItem(key) : null;
  const value = current || crypto.randomUUID();
  if (key) sessionStorage.setItem(key, value);
  if (key && fresh) sessionStorage.removeItem(`paula-thread:${user.id}`);
  return value;
}

const GUEST_GREETING = "Hello! Welcome to Saint Paul University Surigao!\n\nI'm PAULA (Paulinian Artificial User Support and Learning Assistant), your virtual campus assistant. I can help you with admissions, office locations, tuition fees, staff info, and more.\n\nHow may I assist you today?";

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
          onLogin({ type: 'ADMIN', id: data.account_id || username.trim(), name: data.name, is_superuser: true });
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
  useEffect(() => {
    const viewport = window.visualViewport;
    const updateHeight = () => {
      if (!viewport || viewport.scale === 1) {
        document.documentElement.style.setProperty('--app-height', `${viewport?.height ?? window.innerHeight}px`);
      }
    };
    updateHeight();
    window.addEventListener('resize', updateHeight);
    viewport?.addEventListener('resize', updateHeight);
    return () => {
      window.removeEventListener('resize', updateHeight);
      viewport?.removeEventListener('resize', updateHeight);
      document.documentElement.style.removeProperty('--app-height');
    };
  }, []);
  const [user, setUser] = useState(null); // null = not logged in
  const [availableAdmin, setAvailableAdmin] = useState(null);
  const [currentView, setCurrentView] = useState(() => {
    const path = window.location.pathname.replace(/\/$/, '') || '/';
    if (path === '/admin') return 'admin';
    if (path === '/register') return 'register';
    return 'login';
  });
  
  const [messages, setMessages] = useState([]);
  const [isTyping, setIsTyping] = useState(false);
  const [conversationId, setConversationId] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [chatSessionId, setChatSessionId] = useState(null);
  const [isRestoring, setIsRestoring] = useState(true);
  const chatEpoch = useRef(0);
  const sendGuard = useRef(null);
  if (!sendGuard.current) sendGuard.current = createSendGuard();

  // Restore session
  useEffect(() => {
    const epoch = chatEpoch.current;
    let cancelled = false;
    let stored = null;
    try { stored = JSON.parse(localStorage.getItem('paulibot_user')); }
    catch { localStorage.removeItem('paulibot_user'); }
    const adminRoute = window.location.pathname.replace(/\/+$/, '') === '/admin';
    const restore = async () => {
      let session = null;
      try { session = await sessionStatus(); } catch { /* No verified privileged identity. */ }
      if (cancelled || epoch !== chatEpoch.current) return;
      const identity = restoreIdentity(stored, session, adminRoute);
      setAvailableAdmin(identity.availableAdmin);
      if (identity.user) {
        localStorage.setItem('paulibot_user', JSON.stringify(identity.user));
        setUser(identity.user);
        setChatSessionId(chatSession(identity.user));
        setCurrentView(identity.user.is_superuser && adminRoute ? 'admin' : 'chat');
      } else {
        localStorage.removeItem('paulibot_user');
        setCurrentView(adminRoute ? 'admin' : 'login');
      }
      setIsRestoring(false);
    };
    restore();
    return () => { cancelled = true; };
  }, []);

  // A login in another tab may become available; guest identity stays explicit.
  useEffect(() => {
    if (isRestoring || (user && user.type !== 'GUEST')) return;
    let cancelled = false;
    const epoch = chatEpoch.current;
    const check = async () => {
      if (document.visibilityState === 'hidden') return;
      try {
        const account = userFromSession(await sessionStatus());
        if (!cancelled && epoch === chatEpoch.current) setAvailableAdmin(account?.is_superuser ? account : null);
      } catch {
        if (!cancelled && epoch === chatEpoch.current) setAvailableAdmin(null);
      }
    };
    window.addEventListener('focus', check);
    document.addEventListener('visibilitychange', check);
    return () => {
      cancelled = true;
      window.removeEventListener('focus', check);
      document.removeEventListener('visibilitychange', check);
    };
  }, [isRestoring, user?.type, user?.id]);

  // Fetch history if student
  useEffect(() => {
    let cancelled = false;
    const epoch = chatEpoch.current;
    if (user && user.type !== 'GUEST') {
      fetchConversations()
        .then(async data => {
          if (cancelled || epoch !== chatEpoch.current) return;
          setConversations(data);
          const activeSession = sessionStorage.getItem(`paula-chat:${user.id}`);
          const activeId = sessionStorage.getItem(`paula-thread:${user.id}`);
          const active = data.find(conversation => String(conversation.id) === activeId) ||
            data.find(conversation => conversation.client_session_id === activeSession);
          if (active) {
            const details = await fetchConversationDetails(active.id);
            if (cancelled || epoch !== chatEpoch.current) return;
            setConversationId(active.id);
            setMessages(details.flatMap(row => [{ text: row.message, isUser: true }, { text: row.response, isUser: false }]));
          }
        })
        .catch(console.error);
    }
    return () => { cancelled = true; };
  }, [user?.id, user?.type]);

  const handleLogin = useCallback(async (userData) => {
    const epoch = ++chatEpoch.current;
    if (userData.type === 'GUEST') {
      try {
        await logoutSession();
      } catch (error) {
        window.alert(error.message);
        return;
      }
    }
    if (epoch !== chatEpoch.current) return;
    setIsTyping(false);
    setAvailableAdmin(null);
    setUser(userData);
    setChatSessionId(chatSession(userData, true));
    setConversations([]);
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

  const handleResumeAdmin = useCallback(async () => {
    const epoch = chatEpoch.current;
    try {
      const account = userFromSession(await sessionStatus());
      if (epoch !== chatEpoch.current) return;
      if (!account?.is_superuser || String(account.id) !== String(availableAdmin?.id)) {
        setAvailableAdmin(null);
        window.alert('Your administrator session changed. Please sign in again.');
        return;
      }
      await handleLogin(account);
    } catch {
      setAvailableAdmin(null);
      window.alert('Could not verify your administrator session. Please sign in again.');
    }
  }, [availableAdmin?.id, handleLogin]);

  const handleUpdateUser = useCallback((updatedUserData) => {
    setUser(updatedUserData);
    localStorage.setItem('paulibot_user', JSON.stringify(updatedUserData));
  }, []);

  const handleLogout = useCallback(() => {
    if (user?.type === 'GUEST') {
      chatEpoch.current++;
      setIsTyping(false);
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
        text: "Are you sure you want to log out of PAULA?",
        icon: 'question',
        showCancelButton: true,
        confirmButtonColor: '#005529',
        cancelButtonColor: '#d33',
        confirmButtonText: 'Yes, log out!'
      }).then(async (result) => {
        if (result.isConfirmed) {
          chatEpoch.current++;
          setIsTyping(false);
          try {
            await logoutSession();
          } catch (error) {
            Swal.fire('Logout failed', error.message, 'error');
            return;
          }
          setUser(null);
          setMessages([]);
          setConversations([]);
          setConversationId(null);
          localStorage.removeItem('paulibot_user');
          setCurrentView('login');
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
              setChatSessionId(chatSession(user, true));
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
    const epoch = ++chatEpoch.current;
    setIsTyping(false);
    setMessages([]);
    setConversationId(null);
    setChatSessionId(chatSession(user, true));
    if (user?.type !== 'GUEST') fetchConversations().then(data => {
      if (epoch === chatEpoch.current) setConversations(data);
    }).catch(console.error);
  }, [user]);

  const handleSend = useCallback(
    async (text) => {
      if (typeof text !== 'string' || !text.trim()) return;
      const epoch = chatEpoch.current;
      const ticket = sendGuard.current.acquire(epoch);
      if (!ticket) return;
      setMessages((prev) => [...prev, { text, isUser: true, timestamp: Date.now() / 1000 }]);
      setIsTyping(true);

      try {
        const clarificationHistory = messages.slice(-8).map(message => ({
          role: message.isUser ? 'user' : 'assistant',
          content: message.text,
          ...(message.timestamp ? { timestamp: message.timestamp } : {}),
        }));
        const data = await sendMessage(text, conversationId, clarificationHistory, messages.at(-1)?.contextToken,
          user?.type === 'GUEST' ? 'guest' : 'authenticated', chatSessionId, user?.id,
          messages.filter(message => message.isUser && message.text.length <= 500).map(message => message.text).slice(-64));
        if (epoch !== chatEpoch.current) return;

        if (data.conversation_id && data.saved) {
          setConversationId(data.conversation_id);
          sessionStorage.setItem(`paula-thread:${user.id}`, String(data.conversation_id));
          fetchConversations().then(data => { if (epoch === chatEpoch.current) setConversations(data); }).catch(console.error);
        }

        setIsTyping(false);
        setMessages((prev) => [
          ...prev,
          { text: data.response || 'Sorry, I encountered an error.', sources: data.sources || [], suggestions: data.suggestions,
            suggestionsKind: data.suggestions_kind, action: data.action, action_data: data.action_data,
            isUser: false, timestamp: Date.now() / 1000, contextToken: data.context_token },
        ]);
      } catch (err) {
        if (epoch !== chatEpoch.current) return;
        setIsTyping(false);
        if (err.status === 401) {
          chatEpoch.current++;
          setUser(null);
          setMessages([]);
          setConversations([]);
          setConversationId(null);
          localStorage.removeItem('paulibot_user');
          setCurrentView('login');
          window.alert(err.message);
          return;
        }
        setMessages((prev) => [
          ...prev,
          { text: chatErrorMessage(err), isUser: false },
        ]);
      } finally {
        sendGuard.current.release(ticket);
      }
    },
    [conversationId, user, messages, chatSessionId]
  );

  // Router Logic
  if (isRestoring) return <div role="status" className="p-6 text-center">Loading PAULA...</div>;
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
    return <><AdminSessionNotice onContinue={availableAdmin ? handleResumeAdmin : null} /><AuthPage onLogin={handleLogin} onNavigateRegister={() => setCurrentView('register')} /></>;
  }

  if (currentView === 'login' && !user) {
    // Currently, it uses AuthPage. We maintain this as per existing code.
    return <><AdminSessionNotice onContinue={availableAdmin ? handleResumeAdmin : null} /><AuthPage onLogin={handleLogin} onNavigateRegister={() => setCurrentView('register')} /></>;
  }

  return (
    <Dashboard
      user={user}
      onLogout={handleLogout}
      onNavigateLogin={() => { handleLogout(); setCurrentView('login'); }}
      onResumeAdmin={availableAdmin ? handleResumeAdmin : null}
      messages={messages}
      isTyping={isTyping}
      onSend={handleSend}
      onNewChat={handleNewChat}
      conversations={conversations}
      onDeleteChat={handleDeleteChat}
      onNavigateAdmin={user?.is_superuser ? () => {
        setCurrentView('admin');
        window.history.pushState(null, '', '/admin');
      } : null}
      onUpdateUser={handleUpdateUser}
      onLoadChat={async (id) => {
        const epoch = ++chatEpoch.current;
        setIsTyping(false);
        const details = await fetchConversationDetails(id);
        if (epoch !== chatEpoch.current) return;
        setMessages(details.map(d => ({ text: d.message, isUser: true })).flatMap((m, i) => [m, { text: details[i].response, isUser: false}]));
        setConversationId(id);
        sessionStorage.setItem(`paula-thread:${user.id}`, String(id));
        const session = conversations.find(conversation => conversation.id === id)?.client_session_id;
        if (session) {
          sessionStorage.setItem(`paula-chat:${user.id}`, session);
          setChatSessionId(session);
        }
      }}
    />
  );
}
