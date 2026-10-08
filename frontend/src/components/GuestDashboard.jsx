import { useRef, useEffect } from 'react';
import { TriangleAlert } from 'lucide-react';
import PromptGrid from './PromptGrid';
import MessageBubble from './MessageBubble';
import TypingIndicator from './TypingIndicator';
import ChatInput from './ChatInput';
import MaterialIcon from './MaterialIcon';

export default function GuestDashboard({ onLogout, messages, isTyping, onSend }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const isChatEmpty = messages.length === 0;

  return (
    <div className="h-full w-full flex flex-col bg-[#F3F4F6]">
      
      {/* Premium Top Nav */}
      <header className="w-full bg-white border-b border-gray-200 px-6 lg:px-10 py-5 flex items-center justify-between shrink-0 shadow-sm z-10">
        <h1 className="text-[#005529] font-bold text-xl tracking-tight" style={{ fontFamily: 'var(--font-family-heading)' }}>
          Welcome Guest
        </h1>
        <button
          onClick={onLogout}
          className="text-gray-700 hover:text-[#005529] font-semibold text-[0.9rem] transition"
        >
          Login
        </button>
      </header>

      {/* Main Area */}
      <main className="flex-1 overflow-y-auto relative flex flex-col h-full w-full bg-white">
        <div className="w-full max-w-4xl mx-auto flex-1 flex flex-col relative h-full pt-4 pb-4">
          
          {isChatEmpty ? (
            <div className="flex-1 flex flex-col items-center justify-center p-6 h-full mt-[-60px] w-full">
              <div className="w-24 h-24 mb-4 mx-auto flex items-center justify-center">
                 <img src="/spus-logo.webp" alt="SPUS Logo" className="w-full h-full object-contain filter drop-shadow-md" />
              </div>
              <h2 className="text-[2.5rem] text-[#004d26] font-bold mb-1 tracking-tight text-center" style={{ fontFamily: 'var(--font-family-heading)' }}>
                PauliBot
              </h2>
              <p className="text-gray-500 text-[0.95rem] mb-4 font-medium text-center">
                Saint Paul University Surigao AI Assistant
              </p>
              
              <div className="flex items-center gap-2 text-amber-600 text-[0.85rem] font-bold mb-10 bg-amber-50 px-4 py-2 rounded-full border border-amber-200">
                <MaterialIcon name="warning" size={16} color="#D97706" />
                <span>Guest Mode: Chat history not saved</span>
              </div>
              
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
      </main>

      {/* Sticky Input Bar */}
      <div className="bg-white">
         <ChatInput onSend={onSend} disabled={isTyping} />
      </div>
    </div>
  );
}
