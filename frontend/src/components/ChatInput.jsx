import { useState } from 'react';
import { Send } from 'lucide-react';

export default function ChatInput({ onSend, disabled }) {
  const [input, setInput] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim() || disabled) return;
    onSend(input);
    setInput('');
  };

  return (
    <div className="w-full bg-white p-4 shrink-0 flex justify-center z-10 pb-6 md:pb-8">
      <form 
        onSubmit={handleSubmit}
        className="w-full max-w-3xl relative flex items-center bg-white shadow-[var(--shadow-input)] 
                   rounded-xl border border-gray-200 transition-all focus-within:shadow-md focus-within:border-[#005529]/30"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={disabled}
          placeholder="Type a message to PAULA..."
          className="w-full py-4 pl-5 pr-14 bg-transparent border-none outline-none
                     text-gray-700 text-[0.95rem] font-body placeholder:text-gray-400
                     disabled:cursor-not-allowed"
        />
        <button
          type="submit"
          disabled={!input.trim() || disabled}
          className="absolute right-2 top-1/2 -translate-y-1/2 w-10 h-10 rounded-lg flex items-center justify-center
                     bg-[#004d26] text-white cursor-pointer hover:bg-spus-green-light
                     disabled:opacity-30 disabled:cursor-not-allowed transition transform active:scale-95"
        >
          <Send className="w-5 h-5 ml-[-2px] mt-[1px]" />
        </button>
      </form>
    </div>
  );
}
