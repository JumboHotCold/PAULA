import { useRef, useEffect, useState } from 'react';
import ThemeToggle from './ThemeToggle';
import EditProfileModal from './EditProfileModal';
import { fetchAnnouncements } from '../api/chatApi';
import VirtualTour from './VirtualTour';
import MapModule from './MapModule';
import PromptGrid from './PromptGrid';
import MaterialIcon from './MaterialIcon';

// =============================================================================
// SUB-COMPONENTS FOR Markdown & Sources
// =============================================================================

function CheckboxLine({ text, indent }) {
  const [checked, setChecked] = useState(false);
  return (
    <label style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', cursor: 'pointer', marginLeft: indent.length * 8 + 'px', opacity: checked ? 0.6 : 1, textDecoration: checked ? 'line-through' : 'none', marginBottom: '6px' }}>
      <input type="checkbox" checked={checked} onChange={(e) => setChecked(e.target.checked)} style={{ marginTop: '5px', accentColor: 'var(--spus-green)' }} />
      <span style={{ flex: 1 }}>{text}</span>
    </label>
  );
}

function MarkdownRenderer({ text }) {
  return (
    <div className="markdown-renderer">
      {text.split('\n').map((line, idx) => {
        const listRegex = /^(\s*)(?:-\s|\*\s|\d+\.\s)(.*)$/;
        const match = line.match(listRegex);
        if (match) {
          return <CheckboxLine key={idx} text={match[2]} indent={match[1]} />;
        }
        return line.trim() ? <p key={idx} style={{ marginBottom: '8px' }}>{line}</p> : <div key={idx} style={{ height: '8px' }} />;
      })}
    </div>
  );
}

function SourcesAccordion({ sources }) {
  const [open, setOpen] = useState(false);
  if (!sources || sources.length === 0) return null;
  return (
    <div className="sources-container" style={{ marginTop: '12px', fontSize: '0.86em', borderTop: '1px solid var(--color-border)', paddingTop: '8px' }}>
      <button onClick={() => setOpen(!open)} style={{ background: 'none', border: 'none', color: 'var(--color-text-muted)', cursor: 'pointer', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px', padding: '4px 0', fontFamily: 'var(--font-family-sans)' }}>
        <MaterialIcon name="attach_file" size={16} /> Sources <MaterialIcon name="chevron_right" size={14} style={{ transform: open ? 'rotate(90deg)' : 'none', transition: 'transform 0.2s' }} />
      </button>
      {open && (
        <div style={{ marginTop: '8px', padding: '10px 14px', background: 'var(--color-surface-hover)', borderRadius: '8px', color: 'var(--color-text)', border: '1px solid var(--color-border)' }}>
          {sources.map((s, i) => (
            <div key={i} style={{ marginBottom: '6px', display: 'flex', gap: '6px', alignItems: 'flex-start' }}>
              <MaterialIcon name="description" size={16} color="var(--color-primary)" />
              <span style={{ lineHeight: 1.4 }}>
                {s.url ? <a href={s.url} target="_blank" rel="noreferrer" style={{color: 'var(--color-primary)', textDecoration: 'underline', fontWeight: 500}}>{s.title}</a> : s.title}
                {s.page ? ` (Page ${s.page})` : ''}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Parses an incoming message to separate true text from structured suggestions.
// Example: "Kamusta? [SUGGESTIONS: 'Hi' | 'Hello']"
function parseMessage(rawText) {
  if (!rawText) return { text: '', suggestions: [] };
  
  const regex = /\[SUGGESTIONS:\s*(.*?)\]/g;
  let suggestions = [];
  let cleanText = rawText;

  const match = regex.exec(rawText);
  if (match && match[1]) {
    // split by |
    const rawSuggestions = match[1].split('|');
    // strip out wrapping quotes and trim whitespace
    suggestions = rawSuggestions
      .map(s => s.replace(/^["'\s]+|["'\s]+$/g, ''))
      .filter(Boolean);
    
    // remove the suggestion block from the display text
    cleanText = rawText.replace(match[0], '').trim();
  }
  return { text: cleanText, suggestions };
}

export default function Dashboard({ user, onLogout, onNavigateLogin, messages, isTyping, onSend, onNewChat, conversations = [], onNavigateAdmin, onUpdateUser, onDeleteChat, onLoadChat }) {
  const bottomRef = useRef(null);
  const [announcement, setAnnouncement] = useState(null);
  const [isProfileModalOpen, setIsProfileModalOpen] = useState(false);
  const [activeModule, setActiveModule] = useState('chat'); // 'chat' | 'tour' | 'map'
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [navigationDestination, setNavigationDestination] = useState(null);

  useEffect(() => {
    // Check if the latest message triggers an active module change
    if (messages.length > 0) {
      const lastMessage = messages[messages.length - 1];
      if (lastMessage.action === 'navigate_map') {
        setActiveModule('map');
        setNavigationDestination(lastMessage.action_data?.destination || null);
      } else if (lastMessage.action === 'show_map') {
        setActiveModule('map');
      } else if (lastMessage.action === 'load_tour') {
        setActiveModule('tour');
      }
    }
  }, [messages]);

  useEffect(() => {
    // Fetch active announcement on mount
    const getAnnouncement = async () => {
      try {
        const data = await fetchAnnouncements();
        if (data.has_announcement) {
          setAnnouncement(data);
        }
      } catch (err) {
        console.error("Failed to load announcements:", err);
      }
    };
    getAnnouncement();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  // Close sidebar when switching to a module on mobile
  useEffect(() => {
    if (activeModule !== 'chat') {
      setIsSidebarOpen(false);
    }
  }, [activeModule]);

  const isGuest = user.type === 'GUEST';
  const isChatEmpty = messages.length === 0;
  
  const displayName = user?.nickname || user?.name || 'User';
  const initial = displayName.charAt(0).toUpperCase();

  const handleSend = (e) => {
    e.preventDefault();
    const inputEl = e.target.elements.message;
    const text = inputEl.value.trim();
    if (!text || isTyping) return;
    onSend(text);
    inputEl.value = '';
  };

  return (
    <div className="chat-layout">
      
      {/* Mobile Sidebar Overlay */}
      {!isGuest && isSidebarOpen && (
        <div 
          className="sidebar-overlay"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* Sidebar - Exact replica of chat.html <aside class="sidebar"> */}
      {!isGuest && (
        <aside className={`sidebar ${isSidebarOpen ? 'sidebar-open' : ''}`}>
          {/* Mobile close button */}
          <button 
            className="sidebar-close-btn"
            onClick={() => setIsSidebarOpen(false)}
            aria-label="Close sidebar"
          >
            <MaterialIcon name="close" size={18} />
          </button>

          <div className="sidebar-header">
            <button className="new-chat-btn" onClick={() => { onNewChat(); setIsSidebarOpen(false); }}>
              <MaterialIcon name="add" size={18} /> New Chat
            </button>
          </div>

          <div className="sidebar-content">
            {conversations.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '20px', color: '#999' }}>
                No previous conversations
              </div>
            ) : (
              conversations.map(conv => (
                <div key={conv.id} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <button className="conversation-item" onClick={() => { onLoadChat && onLoadChat(conv.id); setIsSidebarOpen(false); }} style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', textAlign: 'left' }}>
                    {conv.title || "New Chat"}
                  </button>
                  <button 
                    onClick={(e) => { e.stopPropagation(); onDeleteChat && onDeleteChat(conv.id); }}
                    style={{ background: 'none', border: 'none', color: '#dc3545', cursor: 'pointer', padding: '5px', display: 'flex', alignItems: 'center' }}
                    title="Delete Chat"
                  >
                    <MaterialIcon name="delete" size={16} color="#dc3545" />
                  </button>
                </div>
              ))
            )}
          </div>

          <div className="sidebar-footer">
            <div className="user-profile" onClick={() => !isGuest && setIsProfileModalOpen(true)} style={{ cursor: isGuest ? 'default' : 'pointer' }}>
              <div className="avatar">
                {user.avatar_url ? (
                  <img src={user.avatar_url.startsWith('http') ? user.avatar_url : `http://localhost:8000${user.avatar_url}`} alt="Avatar" style={{ width: '100%', height: '100%', borderRadius: '50%', objectFit: 'cover' }} />
                ) : (
                  initial
                )}
              </div>
              <div className="user-info">
                <div>{user.nickname || user.name}</div>
                <span>{user.id} {!isGuest && <em style={{ fontSize: '0.8em', marginLeft: '5px', color: 'var(--color-accent)' }}>(Edit)</em>}</span>
              </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '15px' }}>
              {onNavigateAdmin && (
                <button className="logout-btn" onClick={onNavigateAdmin} style={{ background: 'var(--spus-gold)', color: 'var(--text-dark)', borderColor: 'var(--spus-gold)' }}>
                  Admin Dashboard
                </button>
              )}
              <button className="logout-btn" onClick={onLogout}>Log Out</button>
            </div>
          </div>
        </aside>
      )}

      {/* Main Area: Split Screen logic */}
      <div className={`main-area-wrapper ${activeModule !== 'chat' ? 'has-module' : 'chat-only'}`}>
        
        {/* Module Area (Tour / Map) — stacks on top for mobile, side for desktop */}
        {activeModule !== 'chat' && (
          <div className="module-panel">
             <button 
                onClick={() => { setActiveModule('chat'); setNavigationDestination(null); }} 
                className="module-close-btn"
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}
             >
               <MaterialIcon name="close" size={16} style={{ marginRight: '6px' }} /> Close {activeModule === 'tour' ? 'Tour' : 'Map'}
             </button>
             
             {activeModule === 'tour' && <VirtualTour className="w-full h-full shadow-2xl" />}
             {activeModule === 'map' && <MapModule className="w-full h-full shadow-2xl" destination={navigationDestination} />}
          </div>
        )}

      {/* Main Chat - Exact replica of <main class="main-chat"> */}
      <main className={`main-chat ${activeModule !== 'chat' ? 'chat-with-module' : ''}`}>
        
        <header className="chat-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {/* Hamburger menu for mobile */}
            {!isGuest && (
              <button 
                className="hamburger-btn"
                onClick={() => setIsSidebarOpen(true)}
                aria-label="Open sidebar"
              >
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="3" y1="6" x2="21" y2="6" />
                  <line x1="3" y1="12" x2="21" y2="12" />
                  <line x1="3" y1="18" x2="21" y2="18" />
                </svg>
              </button>
            )}
            <h1 className="chat-title">
              {!isGuest ? 'New Chat' : 'Welcome Guest'}
            </h1>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            {/* Smart Virtual Tour Button */}
            <button
              onClick={() => setActiveModule(prev => prev === 'tour' ? 'chat' : 'tour')}
              className="tour-toggle-btn"
              style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <MaterialIcon name="explore" size={18} />
              <span className="tour-btn-label">Smart Virtual Tour</span>
            </button>
            <ThemeToggle />
            {isGuest && (
              <button 
                onClick={onNavigateLogin} 
                style={{ background: 'none', border: 'none', color: 'var(--color-primary)', fontWeight: 600, cursor: 'pointer', fontSize: '0.9em', padding: '6px 10px', borderRadius: '6px' }}
                className="hover:opacity-80"
              >
                Login
              </button>
            )}
          </div>
        </header>

        {/* Announcement banner removed as per user request */}

        <div className="messages-container">
          {isChatEmpty ? (
            <div className="empty-chat-state">
              <div className="w-24 h-24 mb-4 mx-auto flex items-center justify-center">
                 <img 
                   src="/spus-logo.webp" 
                   alt="SPUS Logo" 
                   className="w-full h-full object-contain" 
                   style={{ filter: 'drop-shadow(0 4px 6px rgba(0,0,0,0.2))' }} 
                 />
              </div>
              <h2 className="empty-chat-title">
                PauliBot
              </h2>
              <p className="empty-chat-subtitle">
                Saint Paul University Surigao AI Assistant
              </p>
              
              {isGuest && (
                <div className="guest-warning-badge">
                  <MaterialIcon name="warning" size={16} color="#DC2626" />
                  <span>Guest Mode: Chat history not saved</span>
                </div>
              )}
              
              <div style={{ width: '100%', maxWidth: '600px', marginTop: isGuest ? '10px' : '30px' }}>
                <PromptGrid onPromptClick={(prompt) => { if (!isTyping) onSend(prompt); }} />
              </div>
            </div>
          ) : (
            <>
              {messages.map((msg, idx) => {
                const { text, suggestions } = msg.isUser ? { text: msg.text, suggestions: [] } : parseMessage(msg.text);

                return (
                  <div key={idx} className={`message-wrapper ${msg.isUser ? 'user' : 'bot'}`}>
                    <div className="message-avatar">
                      {msg.isUser ? initial : 'P'}
                    </div>
                    <div className="message-content">
                      {msg.isUser ? text : <MarkdownRenderer text={text} />}
                      
                      {!msg.isUser && msg.sources && msg.sources.length > 0 && (
                        <SourcesAccordion sources={msg.sources} />
                      )}

                      {suggestions.length > 0 && (
                        <div className="follow-up-chips">
                          {suggestions.map((s, i) => (
                            <button 
                              key={i} 
                              className="follow-up-chip" 
                              onClick={() => { if (!isTyping) onSend(s); }}
                            >
                              {s}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              {isTyping && (
                <div className="message-wrapper bot">
                  <div className="message-avatar">P</div>
                  <div className="message-content" style={{ padding: '0' }}>
                    <div className="typing-indicator">
                      <div className="typing-dot"></div>
                      <div className="typing-dot"></div>
                      <div className="typing-dot"></div>
                    </div>
                  </div>
                </div>
              )}
              <div ref={bottomRef} style={{ height: '2px' }}></div>
            </>
          )}
        </div>

        {/* Input Area - Exact replica of chat.html input area */}
        <div className="input-area">
          <form className="input-wrapper" onSubmit={handleSend}>
            <input 
              type="text" 
              name="message"
              className="chat-input" 
              placeholder="Type your question here..." 
              autoComplete="off" 
              disabled={isTyping}
            />
            <button type="submit" className="send-btn" disabled={isTyping}>
              <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
                <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"></path>
              </svg>
            </button>
          </form>
        </div>
      </main>
      </div>

      {!isGuest && (
        <EditProfileModal 
          isOpen={isProfileModalOpen} 
          onClose={() => setIsProfileModalOpen(false)} 
          user={user} 
          onUpdate={onUpdateUser}
        />
      )}
    </div>
  );
}
