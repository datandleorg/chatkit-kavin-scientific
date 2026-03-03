import { useState, useRef, type KeyboardEvent } from 'react';
import { Plus, ArrowUp, X, FileText, Image, Loader2, Square } from 'lucide-react';
import ModelSelector from './ModelSelector';

interface ChatInputProps {
  onSend: (text: string, files?: File[]) => void;
  onStop?: () => void;
  disabled?: boolean;
}

function fileIcon(name: string) {
  const ext = name.split('.').pop()?.toLowerCase() ?? '';
  if (['png', 'jpg', 'jpeg', 'webp', 'gif'].includes(ext)) return <Image size={12} />;
  return <FileText size={12} />;
}

export default function ChatInput({ onSend, onStop, disabled }: ChatInputProps) {
  const [text, setText] = useState('');
  const [model, setModel] = useState('claude-sonnet');
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const canSend = text.trim().length > 0 || attachedFiles.length > 0;

  const handleSend = () => {
    if (!canSend || disabled) return;
    const trimmed = text.trim() || (attachedFiles.length > 0 ? 'Process the attached files and search for the products across all vendors.' : '');
    onSend(trimmed, attachedFiles.length > 0 ? attachedFiles : undefined);
    setText('');
    setAttachedFiles([]);
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
      setAttachedFiles((prev) => [...prev, ...Array.from(e.target.files!)]);
      e.target.value = '';
    }
  };

  const removeFile = (index: number) => {
    setAttachedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  return (
    <div className="px-4 pb-4 pt-2">
      {disabled && (
        <div className="max-w-3xl mx-auto mb-2 flex items-center justify-center gap-2 text-xs text-[var(--color-fg-muted)]">
          <Loader2 size={14} className="animate-spin" />
          <span>Agent is working...</span>
        </div>
      )}
      <div className={`max-w-3xl mx-auto flex items-end gap-2 transition-opacity duration-200 ${disabled ? 'opacity-60' : ''}`}>
        <div className={`flex-1 flex flex-col rounded-2xl border transition-colors duration-200
                        bg-[var(--color-input-bg)]
                        ${disabled ? 'border-[var(--color-border)]' : 'border-[var(--color-border)] focus-within:border-[var(--color-fg-subtle)]'}`}>

          {attachedFiles.length > 0 && (
            <div className="flex flex-wrap gap-1.5 px-3 pt-2.5">
              {attachedFiles.map((file, i) => (
                <span
                  key={`${file.name}-${i}`}
                  className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs
                             bg-[var(--color-bg-tertiary)] text-[var(--color-fg-muted)]
                             border border-[var(--color-border)]"
                >
                  {fileIcon(file.name)}
                  <span className="max-w-[120px] truncate">{file.name}</span>
                  <button
                    type="button"
                    onClick={() => removeFile(i)}
                    className="ml-0.5 hover:text-[var(--color-fg)] transition-colors"
                  >
                    <X size={12} />
                  </button>
                </span>
              ))}
            </div>
          )}

          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            onInput={handleInput}
            placeholder={attachedFiles.length > 0 ? 'Add a message or send to process files...' : 'Ask the concierge a question'}
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
        {disabled && onStop ? (
          <button
            type="button"
            onClick={onStop}
            className="flex items-center justify-center w-10 h-10 rounded-full shrink-0
                       transition-all duration-200 mb-0.5
                       bg-red-500/15 text-red-400 hover:bg-red-500/25 border border-red-500/20"
            aria-label="Stop generation"
          >
            <Square size={14} fill="currentColor" />
          </button>
        ) : (
          <button
            type="button"
            onClick={handleSend}
            disabled={!canSend || disabled}
            className={`flex items-center justify-center w-10 h-10 rounded-full shrink-0
                       transition-all duration-200 mb-0.5
              ${canSend && !disabled
                ? 'bg-[var(--color-fg)] text-[var(--color-bg)] hover:opacity-80'
                : 'bg-[var(--color-bg-tertiary)] text-[var(--color-fg-subtle)] cursor-not-allowed'
              }`}
            aria-label="Send message"
          >
            <ArrowUp size={18} />
          </button>
        )}
      </div>
    </div>
  );
}
