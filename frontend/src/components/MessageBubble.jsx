/**
 * MessageBubble Component
 * ========================
 * Renders a single chat message, styled by sender.
 * Parses [SUGGESTIONS: ...] from bot responses into clickable buttons.
 */
import { parseMessage } from '../suggestions';

export default function MessageBubble({ text, isUser, onSuggestionClick }) {
  const { text: displayText, suggestions } = isUser ? { text, suggestions: [] } : parseMessage(text);

  return (
    <div className={`flex animate-message-in ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className="max-w-[85%] flex flex-col gap-2">
        {/* Bubble */}
        <div
          className={`px-4 py-3 text-[0.92rem] leading-relaxed whitespace-pre-wrap shadow-md ${
            isUser
              ? 'bg-gradient-to-br from-spus-green to-spus-green-700 text-white rounded-2xl rounded-br-sm'
              : 'bg-msg-bot text-text-primary rounded-2xl rounded-bl-sm border border-glass-border'
          }`}
        >
          {displayText}
        </div>

        {/* Suggestion chips */}
        {suggestions.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pl-1">
            {suggestions.map((s, i) => (
              <button
                key={i}
                onClick={() => onSuggestionClick?.(s)}
                className="text-xs px-3 py-1.5 rounded-full border border-glass-border
                           text-spus-gold hover:bg-spus-green/15 hover:border-spus-green/40
                           transition-all duration-200 cursor-pointer"
              >
                {s}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
