import { useRef, useEffect, useState, useMemo, useCallback } from 'react';
import { latestSuggestions, parseMessage } from '../suggestions';
import ThemeToggle from './ThemeToggle';
import EditProfileModal from './EditProfileModal';
import { fetchAnnouncements } from '../api/chatApi';
import VirtualTour from './VirtualTour';
import MapModule from './MapModule';
import PromptGrid from './PromptGrid';
import MaterialIcon from './MaterialIcon';
import PaulaAvatar from './PaulaAvatar';
import UserAvatar from './UserAvatar';
import AdminSessionNotice from './AdminSessionNotice';

// =============================================================================
// SUB-COMPONENTS FOR Markdown & Sources
// =============================================================================

function renderFormattedText(str) {
  if (!str) return '';
  const parts = [];
  const regex = /(\*\*.*?\*\*|\[.*?\]\(.*?\))/g;
  let lastIndex = 0;
  let match;
  while ((match = regex.exec(str)) !== null) {
    if (match.index > lastIndex) {
      parts.push(str.substring(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith('**') && token.endsWith('**')) {
      parts.push(<strong key={match.index}>{token.slice(2, -2)}</strong>);
    } else if (token.startsWith('[')) {
      const linkMatch = token.match(/\[(.*?)\]\((.*?)\)/);
      if (linkMatch) {
        parts.push(
          <a key={match.index} href={linkMatch[2]} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--color-primary)', textDecoration: 'underline', fontWeight: 500 }}>
            {linkMatch[1]}
          </a>
        );
      } else {
        parts.push(token);
      }
    }
    lastIndex = regex.lastIndex;
  }
  if (lastIndex < str.length) {
    parts.push(str.substring(lastIndex));
  }
  return parts.length > 0 ? parts : str;
}

function ListItemLine({ text, indent, bullet }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', marginLeft: `${(indent?.length || 0) * 8 + 6}px`, marginBottom: '6px', lineHeight: '1.5' }}>
      <span style={{ color: 'var(--spus-green, #005529)', fontWeight: 600, minWidth: bullet && bullet.endsWith('.') ? '22px' : '10px', userSelect: 'none' }}>
        {bullet}
      </span>
      <span style={{ flex: 1 }}>{renderFormattedText(text)}</span>
    </div>
  );
}

function MarkdownRenderer({ text }) {
  return (
    <div className="markdown-renderer">
      {text.split('\n').map((line, idx) => {
        const unorderedMatch = line.match(/^(\s*)(?:-\s|\*\s)(.*)$/);
        if (unorderedMatch) {
          return <ListItemLine key={idx} text={unorderedMatch[2]} indent={unorderedMatch[1]} bullet="•" />;
        }
        const orderedMatch = line.match(/^(\s*)(\d+\.)\s(.*)$/);
        if (orderedMatch) {
          return <ListItemLine key={idx} text={orderedMatch[3]} indent={orderedMatch[1]} bullet={orderedMatch[2]} />;
        }
        return line.trim() ? <p key={idx} style={{ marginBottom: '8px' }}>{renderFormattedText(line)}</p> : <div key={idx} style={{ height: '8px' }} />;
      })}
    </div>
  );
}

function SourcesAccordion({ sources }) {
  const [open, setOpen] = useState(false);
  if (!sources || sources.length === 0) return null;
  return (
    <div className="sources-container" style={{ marginTop: '12px', fontSize: '0.86em', borderTop: '1px solid var(--color-border)', paddingTop: '8px' }}>
      <button aria-expanded={open} aria-label={`${open ? 'Hide' : 'Show'} sources`} onClick={() => setOpen(!open)} style={{ background: 'none', border: 'none', color: 'var(--color-text-muted)', cursor: 'pointer', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px', padding: '4px 0', fontFamily: 'var(--font-family-sans)' }}>
        <MaterialIcon name="attach_file" size={16} /> Sources ({sources.length}) <MaterialIcon name="chevron_right" size={14} style={{ transform: open ? 'rotate(90deg)' : 'none', transition: 'transform 0.2s' }} />
      </button>
      {open && (
        <div style={{ marginTop: '8px', padding: '10px 14px', background: 'var(--color-surface-hover)', borderRadius: '8px', color: 'var(--color-text)', border: '1px solid var(--color-border)' }}>
          {sources.map((s, i) => (
            <div key={i} style={{ marginBottom: '6px', display: 'flex', gap: '6px', alignItems: 'flex-start' }}>
              <MaterialIcon name="description" size={16} color="var(--color-primary)" />
              <span style={{ lineHeight: 1.4 }}>
                {s.citation_index ? `${s.citation_index}. ` : ''}
                {s.url ? <a href={s.url} target="_blank" rel="noreferrer" style={{color: 'var(--color-primary)', textDecoration: 'underline', fontWeight: 500}}>{s.title}</a> : s.title}
                {s.page ? ` (Page ${s.page})` : ''}
                {s.retrieved_at && Number.isFinite(Date.parse(s.retrieved_at)) && (
                  <small style={{ display: 'block', color: 'var(--color-text-muted)' }}>
                    Website fetched: {new Date(s.retrieved_at).toLocaleDateString('en-PH')}
                  </small>
                )}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Dashboard({ user, onLogout, onNavigateLogin, messages, isTyping, onSend, onNewChat, conversations = [], onNavigateAdmin, onUpdateUser, onDeleteChat, onLoadChat, onResumeAdmin }) {
  const bottomRef = useRef(null);
  const [announcement, setAnnouncement] = useState(null);
  const [isProfileModalOpen, setIsProfileModalOpen] = useState(false);
  const closeProfile = useCallback(() => setIsProfileModalOpen(false), []);
  const [activeModule, setActiveModule] = useState('chat'); // 'chat' | 'tour' | 'map'
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const sidebarRef = useRef(null);
  const [compact, setCompact] = useState(() => window.matchMedia('(max-width: 1024px)').matches);
  const [navigationDestination, setNavigationDestination] = useState(null);
  const activeSuggestions = useMemo(() => latestSuggestions(messages, isTyping), [messages, isTyping]);

  useEffect(() => {
    document.body.classList.add('paula-workspace-open');
    const media = window.matchMedia('(max-width: 1024px)');
    const resized = () => setCompact(media.matches);
    media.addEventListener('change', resized);
    return () => { document.body.classList.remove('paula-workspace-open'); media.removeEventListener('change', resized); };
  }, []);

  useEffect(() => {
    if (!compact || !isSidebarOpen) return;
    const previous = document.activeElement;
    const focusable = () => [...sidebarRef.current.querySelectorAll('button, a, input')].filter(el => !el.disabled);
    focusable()[0]?.focus();
    const key = event => {
      if (event.key === 'Escape') setIsSidebarOpen(false);
      if (event.key !== 'Tab') return;
      const items = focusable(), first = items[0], last = items.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    document.addEventListener('keydown', key);
    return () => { document.removeEventListener('keydown', key); previous?.focus(); };
  }, [compact, isSidebarOpen]);

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
        <button type="button" aria-label="Close conversation history"
          className="sidebar-overlay"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* Sidebar - Exact replica of chat.html <aside class="sidebar"> */}
      {!isGuest && (
        <aside ref={sidebarRef} id="chat-history-sidebar" aria-label="Conversation history" inert={compact && !isSidebarOpen ? true : undefined}
               className={`sidebar ${isSidebarOpen ? 'sidebar-open' : ''}`}>
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
                    className="delete-conversation-btn" aria-label={`Delete conversation: ${conv.title || 'New Chat'}`}
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
            <button type="button" className="user-profile profile-trigger" onClick={() => { if (!isGuest) { setIsSidebarOpen(false); setIsProfileModalOpen(true); } }} style={{ cursor: isGuest ? 'default' : 'pointer' }}>
              <div className="avatar" style={{ background: 'transparent' }}>
                <UserAvatar user={user} size="sm" />
              </div>
              <div className="user-info">
                <div>{user.nickname || user.name}</div>
                <span>{user.id} {!isGuest && <em style={{ fontSize: '0.8em', marginLeft: '5px', color: 'var(--color-accent)' }}>(Edit)</em>}</span>
              </div>
            </button>
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
             <div className="module-toolbar">
             <span>{activeModule === 'tour' ? 'Explore the campus' : 'Campus navigation'}</span>
             <button 
                onClick={() => { setActiveModule('chat'); setNavigationDestination(null); }} 
                className="module-close-btn"
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}
             >
               <MaterialIcon name="close" size={16} style={{ marginRight: '6px' }} /> Close {activeModule === 'tour' ? 'Tour' : 'Map'}
             </button>
             </div>
             
             {activeModule === 'tour' && <VirtualTour className="w-full h-full shadow-2xl" />}
             {activeModule === 'map' && <MapModule className="w-full h-full shadow-2xl" destination={navigationDestination} user={user} />}
          </div>
        )}

      {/* Main Chat - Exact replica of <main class="main-chat"> */}
      <main className={`main-chat ${activeModule !== 'chat' ? 'chat-with-module' : ''}`}>
        
        <header className="chat-header">
          <div className="chat-brand" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {/* Hamburger menu for mobile */}
            {!isGuest && (
              <button 
                className="hamburger-btn"
                onClick={() => setIsSidebarOpen(true)}
                aria-label="Open sidebar"
                aria-expanded={isSidebarOpen} aria-controls="chat-history-sidebar"
              >
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="3" y1="6" x2="21" y2="6" />
                  <line x1="3" y1="12" x2="21" y2="12" />
                  <line x1="3" y1="18" x2="21" y2="18" />
                </svg>
              </button>
            )}
            <h1 className="chat-title">
              PAULA
            </h1>
          </div>
          <div className="chat-header-actions" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <button className="tour-toggle-btn map-toggle-btn" aria-label="Campus map" aria-pressed={activeModule === 'map'}
                    onClick={() => { setActiveModule(previous => previous === 'map' ? 'chat' : 'map'); setNavigationDestination(null); }}>
              <MaterialIcon name="map" size={20} /><span className="map-btn-label">Campus map</span>
            </button>
            {/* Smart Virtual Tour Button */}
            <button
              onClick={() => setActiveModule(prev => prev === 'tour' ? 'chat' : 'tour')}
              className="tour-toggle-btn"
              aria-label="Smart Virtual Tour"
              aria-pressed={activeModule === 'tour'}
              style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <MaterialIcon name="explore" size={18} />
              <span className="tour-btn-label">Smart Virtual Tour</span>
            </button>
            <ThemeToggle />
            {isGuest && (
              <button 
                onClick={onNavigateLogin} 
                className="chat-login-btn"
              >
                Login
              </button>
            )}
          </div>
        </header>

        {isGuest && <AdminSessionNotice onContinue={onResumeAdmin} />}

        {/* Announcement banner removed as per user request */}

        <div className="messages-container">
          {isChatEmpty ? (
            <div className="empty-chat-state">
              <div className="w-24 h-24 mb-4 mx-auto flex items-center justify-center" title="St. Paul University Surigao">
                 <img 
                   src="/spus-logo.webp" 
                   alt="SPUS Logo" 
                   className="w-full h-full object-contain" 
                   style={{ filter: 'drop-shadow(0 4px 6px rgba(0,0,0,0.2))' }} 
                 />
              </div>
              <h2 className="empty-chat-title">
                PAULA
              </h2>
              <p className="empty-chat-subtitle">
                Paulinian Artificial User Support and Learning Assistant • SPUS
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
                const text = msg.isUser ? msg.text : parseMessage(msg.text).text;
                const suggestions = idx === activeSuggestions.index ? activeSuggestions.suggestions : [];

                return (
                  <div key={idx} className={`message-wrapper ${msg.isUser ? 'user' : 'bot'}`}>
                    <div className="message-avatar">
                      {msg.isUser ? (
                        <UserAvatar user={user} size="sm" />
                      ) : (
                        <PaulaAvatar size="sm" variant="crest" />
                      )}
                    </div>
                    <div className="message-content">
                      {msg.isUser ? text : <MarkdownRenderer text={text} />}
                      
                      {!msg.isUser && msg.sources && msg.sources.length > 0 && (
                        <SourcesAccordion sources={msg.sources} />
                      )}

                      {suggestions.length > 0 && (
                        <div className="follow-up-chips" role="group" aria-label="Suggested next questions or choices">
                          {suggestions.map((s, i) => (
                            <button 
                              key={i} 
                              className="follow-up-chip" 
                              disabled={isTyping}
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
                  <div className="message-avatar">
                    <PaulaAvatar size="sm" variant="crest" isTyping={true} />
                  </div>
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
              aria-label="Message PAULA" enterKeyHint="send"
              className="chat-input" 
              placeholder="Type your question here..." 
              autoComplete="off" 
              disabled={isTyping}
            />
            <button type="submit" className="send-btn" disabled={isTyping} aria-label="Send message">
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
          onClose={closeProfile}
          user={user} 
          onUpdate={onUpdateUser}
        />
      )}
    </div>
  );
}
