import { Clock, SquarePen } from 'lucide-react';
import ThemeToggle from './ThemeToggle';

interface ChatHeaderProps {
  onToggleHistory: () => void;
  onNewChat: () => void;
}

export default function ChatHeader({ onToggleHistory, onNewChat }: ChatHeaderProps) {
  return (
    <header className="flex items-center justify-end px-4 py-2">
      <div className="flex items-center gap-1">
        <ThemeToggle />
        <button
          onClick={onNewChat}
          className="flex items-center justify-center w-9 h-9 rounded-lg
                     hover:bg-[var(--color-bg-secondary)] transition-colors duration-200"
          aria-label="New chat"
        >
          <SquarePen size={18} className="text-[var(--color-fg-muted)]" />
        </button>
        <button
          onClick={onToggleHistory}
          className="flex items-center justify-center w-9 h-9 rounded-lg
                     hover:bg-[var(--color-bg-secondary)] transition-colors duration-200"
          aria-label="Chat history"
        >
          <Clock size={18} className="text-[var(--color-fg-muted)]" />
        </button>
      </div>
    </header>
  );
}
