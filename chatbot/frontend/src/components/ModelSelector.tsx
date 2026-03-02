import { ChevronDown } from 'lucide-react';
import { useState, useRef, useEffect, useCallback } from 'react';

const models = [
  { id: 'claude-sonnet', label: 'Claude Sonnet' },
  { id: 'gpt-5', label: 'GPT-5' },
  { id: 'gpt-4o', label: 'GPT-4o' },
];

interface ModelSelectorProps {
  value: string;
  onChange: (modelId: string) => void;
}

export default function ModelSelector({ value, onChange }: ModelSelectorProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const selected = models.find((m) => m.id === value) ?? models[0];

  const close = useCallback(() => setOpen(false), []);

  useEffect(() => {
    if (!open) return;

    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) close();
    }
    function handleEscape(e: KeyboardEvent) {
      if (e.key === 'Escape') close();
    }

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [open, close]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium
                   text-[var(--color-fg-muted)] hover:bg-[var(--color-bg-tertiary)]
                   transition-colors duration-150"
      >
        {selected.label}
        <ChevronDown size={12} />
      </button>
      {open && (
        <div className="absolute bottom-full left-0 mb-1 w-40 py-1 rounded-lg border
                        border-[var(--color-border)] bg-[var(--color-bg)]
                        shadow-lg z-50 animate-fade-in">
          {models.map((m) => (
            <button
              key={m.id}
              onClick={() => { onChange(m.id); close(); }}
              className={`w-full text-left px-3 py-1.5 text-xs transition-colors duration-100
                ${m.id === value
                  ? 'text-[var(--color-accent)] bg-[var(--color-bg-secondary)]'
                  : 'text-[var(--color-fg-muted)] hover:bg-[var(--color-bg-secondary)]'
                }`}
            >
              {m.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
