import { ChevronDown } from 'lucide-react';
import { useState, useRef, useEffect, useCallback } from 'react';
import { getModels, type AllowedModel } from '../lib/api';

const DEFAULT_MODEL_ID = 'gpt-5-mini';

/** Only OpenAI models are selectable for now; Claude models are excluded. */
function groupByProvider(models: AllowedModel[]): { group: string; models: { id: string; label: string }[] }[] {
  const openai = models.filter((m) => m.provider === 'openai');
  const result: { group: string; models: { id: string; label: string }[] }[] = [];
  if (openai.length) result.push({ group: 'OpenAI', models: openai.map((m) => ({ id: m.id, label: m.label })) });
  return result;
}

interface ModelSelectorProps {
  value: string;
  onChange: (modelId: string) => void;
}

export default function ModelSelector({ value, onChange }: ModelSelectorProps) {
  const [open, setOpen] = useState(false);
  const [modelGroups, setModelGroups] = useState<{ group: string; models: { id: string; label: string }[] }[]>([]);
  const [loading, setLoading] = useState(true);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getModels()
      .then((list) => {
        setModelGroups(groupByProvider(list));
      })
      .catch(() => setModelGroups([]))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (modelGroups.length === 0) return;
    const models = modelGroups.flatMap((g) => g.models);
    const ids = new Set(models.map((m) => m.id));
    if (value && !ids.has(value)) {
      const defaultId = ids.has(DEFAULT_MODEL_ID) ? DEFAULT_MODEL_ID : models[0]?.id ?? DEFAULT_MODEL_ID;
      onChange(defaultId);
    }
  }, [modelGroups, value, onChange]);

  const models = modelGroups.flatMap((g) => g.models);
  const selected = models.find((m) => m.id === value) ?? models.find((m) => m.id === DEFAULT_MODEL_ID) ?? models[0];

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

  if (loading || modelGroups.length === 0) {
    return (
      <span className="px-2 py-1 text-xs font-medium text-[var(--color-fg-muted)]">
        {loading ? '…' : DEFAULT_MODEL_ID}
      </span>
    );
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium
                   text-[var(--color-fg-muted)] hover:bg-[var(--color-bg-tertiary)]
                   transition-colors duration-150"
      >
        {selected?.label ?? value ?? DEFAULT_MODEL_ID}
        <ChevronDown size={12} />
      </button>
      {open && (
        <div className="absolute bottom-full left-0 mb-1 w-44 py-1 rounded-lg border
                        border-[var(--color-border)] bg-[var(--color-bg)]
                        shadow-lg z-50 animate-fade-in max-h-64 overflow-y-auto">
          {modelGroups.map(({ group, models: groupModels }) => (
            <div key={group}>
              <div className="px-3 py-1 text-[10px] font-semibold uppercase tracking-wide
                              text-[var(--color-fg-muted)] border-b border-[var(--color-border)]">
                {group}
              </div>
              {groupModels.map((m) => (
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
          ))}
        </div>
      )}
    </div>
  );
}
