import { useState, useRef, type KeyboardEvent } from 'react';
import { Plus, ArrowUp } from 'lucide-react';
import ModelSelector from './ModelSelector';

interface ChatInputProps {
  onSend: (text: string) => void;
  onAttach: (files: FileList) => void;
  disabled?: boolean;
}

export default function ChatInput({ onSend, onAttach, disabled }: ChatInputProps) {
  const [text, setText] = useState('');
  const [model, setModel] = useState('claude-sonnet');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 160) + 'px';
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onAttach(e.target.files);
      e.target.value = '';
    }
  };

  const hasText = text.trim().length > 0;

  return (
    <div className="px-4 pb-4 pt-2">
      <div className="max-w-3xl mx-auto flex items-end gap-2">
        <div className="flex-1 flex flex-col rounded-2xl border border-[var(--color-border)]
                        bg-[var(--color-input-bg)] transition-colors duration-200
                        focus-within:border-[var(--color-fg-subtle)]">
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            onInput={handleInput}
            placeholder="Ask the concierge a question"
            disabled={disabled}
            rows={1}
            className="w-full resize-none bg-transparent px-4 pt-3 pb-1 text-sm
                       text-[var(--color-fg)] placeholder:text-[var(--color-fg-subtle)]
                       focus:outline-none disabled:opacity-50"
          />
          <div className="flex items-center px-3 pb-2">
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="flex items-center justify-center w-7 h-7 rounded-lg
                           text-[var(--color-fg-muted)] hover:bg-[var(--color-bg-tertiary)]
                           transition-colors duration-150"
                aria-label="Attach files"
              >
                <Plus size={16} />
              </button>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,.png,.jpg,.jpeg,.webp,.gif"
                onChange={handleFileChange}
                className="hidden"
              />
              <ModelSelector value={model} onChange={setModel} />
            </div>
          </div>
        </div>
        <button
          type="button"
          onClick={handleSend}
          disabled={!hasText || disabled}
          className={`flex items-center justify-center w-10 h-10 rounded-full shrink-0
                     transition-all duration-200 mb-0.5
            ${hasText && !disabled
              ? 'bg-[var(--color-fg)] text-[var(--color-bg)] hover:opacity-80'
              : 'bg-[var(--color-bg-tertiary)] text-[var(--color-fg-subtle)] cursor-not-allowed'
            }`}
          aria-label="Send message"
        >
          <ArrowUp size={18} />
        </button>
      </div>
    </div>
  );
}
