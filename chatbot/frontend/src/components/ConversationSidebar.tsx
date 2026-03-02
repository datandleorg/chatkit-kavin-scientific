import { useEffect, useState, useCallback } from 'react';
import { X, PlusCircle, Trash2, MessageSquare } from 'lucide-react';
import type { Conversation } from '../types';
import { fetchConversations, deleteConversation as apiDeleteConversation } from '../lib/api';

interface ConversationSidebarProps {
  open: boolean;
  onClose: () => void;
  activeConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onNewChat: () => void;
}

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = now - then;
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

export default function ConversationSidebar({
  open,
  onClose,
  activeConversationId,
  onSelectConversation,
  onNewChat,
}: ConversationSidebarProps) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(false);

  const loadConversations = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchConversations();
      setConversations(data);
    } catch (err) {
      console.error('Failed to load conversations:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) loadConversations();
  }, [open, loadConversations]);

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    try {
      await apiDeleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (activeConversationId === id) onNewChat();
    } catch (err) {
      console.error('Failed to delete conversation:', err);
    }
  };

  const handleSelect = (id: string) => {
    onSelectConversation(id);
    onClose();
  };

  const handleNewChat = () => {
    onNewChat();
    onClose();
  };

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 bg-black/30 z-40 transition-opacity"
          onClick={onClose}
        />
      )}

      <aside
        className={`fixed top-0 left-0 h-full w-72 z-50 flex flex-col
                     bg-[var(--color-bg)] border-r border-[var(--color-border)]
                     shadow-xl transition-transform duration-300 ease-in-out
                     ${open ? 'translate-x-0' : '-translate-x-full'}`}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
          <span className="text-sm font-semibold text-[var(--color-fg)]">Conversations</span>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-[var(--color-bg-secondary)] transition-colors"
            aria-label="Close sidebar"
          >
            <X size={16} className="text-[var(--color-fg-muted)]" />
          </button>
        </div>

        <div className="px-3 py-2">
          <button
            onClick={handleNewChat}
            className="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm font-medium
                       bg-[var(--color-accent)]/10 text-[var(--color-accent)]
                       border border-[var(--color-accent)]/20
                       hover:bg-[var(--color-accent)]/20 transition-colors"
          >
            <PlusCircle size={16} />
            New Chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-2 pb-4">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className="w-5 h-5 border-2 border-[var(--color-accent)] border-t-transparent rounded-full animate-spin" />
            </div>
          ) : conversations.length === 0 ? (
            <div className="text-center py-8 text-xs text-[var(--color-fg-muted)]">
              No conversations yet
            </div>
          ) : (
            <div className="flex flex-col gap-0.5">
              {conversations.map((conv) => (
                <button
                  key={conv.id}
                  onClick={() => handleSelect(conv.id)}
                  className={`group w-full flex items-start gap-2.5 px-3 py-2.5 rounded-lg text-left transition-colors
                              ${activeConversationId === conv.id
                                ? 'bg-[var(--color-accent)]/10 text-[var(--color-accent)]'
                                : 'text-[var(--color-fg)] hover:bg-[var(--color-bg-secondary)]'}`}
                >
                  <MessageSquare size={14} className="shrink-0 mt-0.5 text-[var(--color-fg-muted)]" />
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium truncate">{conv.title}</div>
                    <div className="text-[10px] text-[var(--color-fg-muted)] mt-0.5">
                      {timeAgo(conv.updated_at)}
                    </div>
                  </div>
                  <button
                    onClick={(e) => handleDelete(e, conv.id)}
                    className="shrink-0 p-1 rounded opacity-0 group-hover:opacity-100
                               hover:bg-red-500/10 text-[var(--color-fg-muted)] hover:text-red-400 transition-all"
                    aria-label="Delete conversation"
                  >
                    <Trash2 size={12} />
                  </button>
                </button>
              ))}
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
