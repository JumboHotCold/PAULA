import { useRef, useEffect } from 'react';
import { Plus } from 'lucide-react';
import Sidebar from './Sidebar';
import PromptGrid from './PromptGrid';
import MessageBubble from './MessageBubble';
import TypingIndicator from './TypingIndicator';
import ChatInput from './ChatInput';

export default function StudentDashboard({ user, onLogout, messages, isTyping, onSend, onNewChat, conversations = [], onDeleteChat, onLoadChat }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const isChatEmpty = messages.length === 0;

  return (
    <div className="h-full w-full flex bg-white font-body">
      
      {/* SIDEBAR */}
      <Sidebar user={user} onLogout={onLogout} onNewChat={onNewChat} conversations={conversations} onDeleteChat={onDeleteChat} onLoadChat={onLoadChat} />

      {/* MAIN CHAT AREA */}
      <main className="flex-1 flex flex-col h-full relative overflow-hidden">
        
        {/* Mobile Header */}
        <header className="md:hidden w-full border-b border-gray-200 px-4 py-3 flex items-center justify-between shrink-0 bg-white z-10 shadow-sm">
           <h2 className="text-[#005529] font-bold text-lg" style={{ fontFamily: 'var(--font-family-heading)' }}>
             PAULA
           </h2>
           <button onClick={onNewChat} className="p-2 text-gray-500 hover:text-[#005529]">
             <Plus className="w-6 h-6" />
           </button>
        </header>

        {/* Top Spacer/Title for Desktop Active Chat */}
        {!isChatEmpty && (
          <div className="hidden md:flex w-full px-6 py-5 shrink-0 bg-white/90 backdrop-blur items-center z-10 absolute top-0 left-0 border-b border-gray-100">
             <h2 className="text-[#005529] font-bold text-base" style={{ fontFamily: 'var(--font-family-heading)' }}>
               Chat with PAULA
             </h2>
          </div>
        )}

        {/* Scrollable Messages Area */}
        <div className="flex-1 overflow-y-auto w-full relative pt-4 md:pt-16 pb-4">
          <div className="w-full max-w-4xl mx-auto h-full flex flex-col">
            
            {isChatEmpty ? (
              <div className="flex-1 flex flex-col items-center justify-center p-6 h-full mt-[-80px] w-full">
                <div className="w-24 h-24 mb-4 mx-auto flex items-center justify-center">
                   <img src="/spus-logo.webp" alt="SPUS Logo" className="w-full h-full object-contain filter drop-shadow-md" />
                </div>
                <h1 className="text-[2.5rem] text-[#004d26] font-bold mb-1 tracking-tight text-center" style={{ fontFamily: 'var(--font-family-heading)' }}>
                  PAULA
                </h1>
                <p className="text-gray-500 text-[0.95rem] mb-10 font-medium text-center">
                  Paulinian Artificial User Support and Learning Assistant • SPUS
                </p>
                <PromptGrid onPromptClick={onSend} />
              </div>
            ) : (
              <div className="flex-1 px-4 lg:px-6 space-y-6">
                {messages.map((msg, idx) => (
                  <MessageBubble key={idx} text={msg.text} isUser={msg.isUser} onSuggestionClick={onSend} />
                ))}
                {isTyping && <TypingIndicator />}
                <div ref={bottomRef} className="h-6" />
              </div>
            )}
          </div>
        </div>

        {/* Input Bar */}
        <ChatInput onSend={onSend} disabled={isTyping} />
      </main>
    </div>
  );
}
