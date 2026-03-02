import { Sun, Moon } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';

export default function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      className="flex items-center justify-center w-9 h-9 rounded-lg
                 hover:bg-[var(--color-bg-secondary)] transition-colors duration-200"
      aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
    >
      {theme === 'dark' ? (
        <Sun size={18} className="text-[var(--color-fg-muted)]" />
      ) : (
        <Moon size={18} className="text-[var(--color-fg-muted)]" />
      )}
    </button>
  );
}
