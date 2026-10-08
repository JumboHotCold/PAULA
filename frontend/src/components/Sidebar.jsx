import { Plus, MessageSquare } from 'lucide-react';
import MaterialIcon from './MaterialIcon';

export default function Sidebar({ user, onLogout, onNewChat, conversations, onDeleteChat, onLoadChat }) {
  // Extract initial
  const initial = user?.name ? user.name.charAt(0).toUpperCase() : 'S';

  return (
    <aside className="hidden md:flex flex-col w-[260px] bg-[#F9FAFB] border-r border-gray-200 shrink-0 h-full">
      {/* Top action */}
      <div className="p-4">
        <button
          onClick={onNewChat}
          className="w-full bg-[#005529] hover:bg-spus-green-dark text-white rounded-md py-3 px-4
                     flex items-center justify-center flex-row gap-2 font-semibold text-[0.85rem] shadow-sm transition-all"
        >
          <Plus className="w-4 h-4" strokeWidth={3} />
          New Chat
        </button>
      </div>

      {/* History List */}
      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1 custom-scrollbar">
        {conversations.length === 0 ? (
          <p className="text-xs text-gray-400 text-center mt-6 font-medium">No previous chats</p>
        ) : (
          conversations.map((conv) => (
            <div key={conv.id} className="w-full flex items-center pr-2 group">
              <button
                onClick={() => onLoadChat && onLoadChat(conv.id)}
                className="flex-1 text-left px-3 py-2.5 rounded-md text-[0.85rem] text-gray-700 font-medium
                           hover:bg-white hover:shadow-sm border border-transparent hover:border-gray-200
                           truncate flex items-center gap-2 transition-all"
              >
                <MessageSquare className="w-4 h-4 shrink-0 text-gray-400" />
                <span className="truncate">{conv.title || "New Chat"}</span>
              </button>
              <button 
                onClick={(e) => { e.stopPropagation(); onDeleteChat && onDeleteChat(conv.id); }}
                className="opacity-0 group-hover:opacity-100 p-1.5 text-red-400 hover:text-red-600 transition-opacity flex items-center"
                title="Delete Chat"
              >
                <MaterialIcon name="delete" size={16} color="#DC2626" />
              </button>
            </div>
          ))
        )}
      </div>

      {/* Bottom Profile */}
      <div className="p-4 bg-white border-t border-gray-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-spus-gold flex items-center justify-center text-[#3C2A0A] font-bold text-lg shadow-sm">
              {initial}
            </div>
            <div>
              <p className="text-sm font-bold text-gray-900 leading-tight">{user?.name || 'Student'}</p>
              <p className="text-[0.7rem] text-gray-500 font-medium">{user?.id}</p>
            </div>
          </div>
        </div>
        <button
          onClick={onLogout}
          className="mt-4 w-full py-2 rounded border border-gray-200 text-gray-600 text-xs font-semibold
                     hover:bg-gray-50 hover:text-gray-900 transition-colors"
        >
          Log Out
        </button>
      </div>
    </aside>
  );
}
