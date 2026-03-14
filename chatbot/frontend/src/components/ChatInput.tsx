import { useState, useRef, useCallback, type KeyboardEvent, type DragEvent } from 'react';
import { Plus, ArrowUp, X, FileText, Image, Loader2, Square, Upload, Brain } from 'lucide-react';
import ModelSelector from './ModelSelector';
import Toggle from './Toggle';

interface ChatInputProps {
  onSend: (text: string, files?: File[], model?: string, reasoning?: boolean) => void;
  onStop?: () => void;
  disabled?: boolean;
  /** When provided with onReasoningChange, the reasoning toggle is controlled by the parent. */
  reasoning?: boolean;
  onReasoningChange?: (value: boolean) => void;
}

const ACCEPTED_TYPES = new Set([
  'application/pdf',
  'image/png', 'image/jpeg', 'image/webp', 'image/gif',
]);
const ACCEPTED_EXTS = new Set(['.pdf', '.png', '.jpg', '.jpeg', '.webp', '.gif']);

function isAcceptedFile(file: File): boolean {
  if (ACCEPTED_TYPES.has(file.type)) return true;
  const ext = '.' + (file.name.split('.').pop()?.toLowerCase() ?? '');
  return ACCEPTED_EXTS.has(ext);
}

function fileIcon(name: string) {
  const ext = name.split('.').pop()?.toLowerCase() ?? '';
  if (['png', 'jpg', 'jpeg', 'webp', 'gif'].includes(ext)) return <Image size={12} />;
  return <FileText size={12} />;
}

export default function ChatInput({ onSend, onStop, disabled, reasoning: reasoningProp, onReasoningChange }: ChatInputProps) {
  const [text, setText] = useState('');
  const [model, setModel] = useState('claude-sonnet-4-20250514');
  const [internalReasoning, setInternalReasoning] = useState(false);
  const reasoning = reasoningProp !== undefined ? reasoningProp : internalReasoning;
  const setReasoning = onReasoningChange ?? setInternalReasoning;
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const dragCounter = useRef(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const canSend = text.trim().length > 0 || attachedFiles.length > 0;

  const addFiles = useCallback((files: File[]) => {
    const valid = files.filter(isAcceptedFile);
    if (valid.length > 0) setAttachedFiles((prev) => [...prev, ...valid]);
  }, []);

  const handleSend = () => {
    if (!canSend || disabled) return;
    const trimmed = text.trim() || (attachedFiles.length > 0 ? 'Process the attached files and search for the products across all vendors.' : '');
    // Pass reasoning as explicit boolean so backend receives correct value
    const useReasoning = reasoning === true;
    onSend(trimmed, attachedFiles.length > 0 ? attachedFiles : undefined, model, useReasoning);
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
      addFiles(Array.from(e.target.files));
      e.target.value = '';
    }
  };

  const removeFile = (index: number) => {
    setAttachedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleDragEnter = (e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current++;
    if (e.dataTransfer.types.includes('Files')) setIsDragging(true);
  };

  const handleDragLeave = (e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current--;
    if (dragCounter.current === 0) setIsDragging(false);
  };

  const handleDragOver = (e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current = 0;
    setIsDragging(false);
    if (disabled) return;
    const files = Array.from(e.dataTransfer.files);
    addFiles(files);
  };

  return (
    <div
      className="px-4 pb-4 pt-2 relative"
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      {isDragging && !disabled && (
        <div className="absolute inset-0 z-10 flex items-center justify-center
                        bg-[var(--color-bg)]/80 backdrop-blur-sm rounded-2xl
                        border-2 border-dashed border-[var(--color-accent)] mx-4 mb-4 mt-2">
          <div className="flex flex-col items-center gap-2 text-[var(--color-accent)]">
            <Upload size={28} />
            <span className="text-sm font-medium">Drop images or PDFs here</span>
          </div>
        </div>
      )}

      {disabled && (
        <div className="max-w-3xl mx-auto mb-2 flex items-center justify-center gap-2 text-xs text-[var(--color-fg-muted)]">
          <Loader2 size={14} className="animate-spin" />
          <span>Agent is working...</span>
        </div>
      )}
      <div className={`max-w-3xl mx-auto flex items-end gap-2 transition-opacity duration-200 ${disabled ? 'opacity-60' : ''}`}>
        <div className={`flex-1 flex flex-col rounded-2xl border transition-colors duration-200
                        bg-[var(--color-input-bg)]
                        ${isDragging && !disabled
                          ? 'border-[var(--color-accent)] ring-2 ring-[var(--color-accent)]/20'
                          : disabled ? 'border-[var(--color-border)]' : 'border-[var(--color-border)] focus-within:border-[var(--color-fg-subtle)]'}`}>

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
            placeholder={attachedFiles.length > 0 ? 'Add a message or send to process files...' : 'Drop files here or ask a question'}
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
              <Toggle
                checked={reasoning}
                onCheckedChange={setReasoning}
                aria-label={reasoning ? 'Turn off extended thinking' : 'Turn on extended thinking'}
                label="Reasoning"
                icon={<Brain size={14} />}
                title={reasoning ? 'Extended thinking on' : 'Extended thinking off'}
              />
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
