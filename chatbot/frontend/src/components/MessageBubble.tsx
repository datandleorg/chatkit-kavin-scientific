import { User, Bot, Search, CheckCircle2, ChevronDown, ChevronRight, AlertCircle, Brain, Loader2, FileText, Paperclip, ScanText, Image, Info, Copy, Check } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Message, ToolCall, ContentBlock, QuoteRow } from '../types';
import { useState, useCallback } from 'react';
import QuoteTable from './QuoteTable';

interface MessageBubbleProps {
  message: Message;
  isStreaming?: boolean;
  conversationId?: string | null;
}

const TOOL_LABELS: Record<string, string> = {
  search_hyma: 'Search Hyma',
  get_hyma_product_details: 'Hyma Details',
  search_spectrochem: 'Search Spectrochem',
  get_spectrochem_product_details: 'Spectrochem Details',
  search_glosil: 'Search Glosil',
  get_glosil_product_details: 'Glosil Details',
  search_tci: 'Search TCI',
  get_tci_product_details: 'TCI Details',
};

function extractToolOutput(raw: string): string {
  const contentMatch = raw.match(/content='([\s\S]*?)' name=/);
  if (contentMatch) {
    return contentMatch[1]
      .replace(/\\n/g, '\n')
      .replace(/\\t/g, '\t')
      .replace(/\\'/g, "'")
      .replace(/\\"/g, '"');
  }
  const contentMatch2 = raw.match(/content="([\s\S]*?)" name=/);
  if (contentMatch2) {
    return contentMatch2[1]
      .replace(/\\n/g, '\n')
      .replace(/\\t/g, '\t')
      .replace(/\\'/g, "'")
      .replace(/\\"/g, '"');
  }
  return raw;
}

function isErrorResult(text: string): boolean {
  return /error|failed|certificate|timeout|connection refused/i.test(text);
}

function formatTokenCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

function ToolCallChip({ toolCall }: { toolCall: ToolCall }) {
  const [expanded, setExpanded] = useState(false);
  const label = TOOL_LABELS[toolCall.name] ?? toolCall.name;
  const isCalling = toolCall.status === 'calling';
  const output = toolCall.result ? extractToolOutput(toolCall.result) : null;
  const hasError = output ? isErrorResult(output) : false;

  const inputLabel = toolCall.input
    ? toolCall.input.length > 30
      ? toolCall.input.slice(0, 30) + '...'
      : toolCall.input
    : null;

  return (
    <div className="flex flex-col">
      <button
        onClick={() => toolCall.result && setExpanded(!expanded)}
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium
          transition-all duration-150
          ${isCalling
            ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
            : hasError
              ? 'bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 cursor-pointer'
              : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 cursor-pointer'
          }`}
      >
        {isCalling ? (
          <Search size={12} className="animate-pulse" />
        ) : hasError ? (
          <AlertCircle size={12} />
        ) : (
          <CheckCircle2 size={12} />
        )}
        <span>{label}</span>
        {inputLabel && (
          <span className="opacity-60 font-normal">({inputLabel})</span>
        )}
        {isCalling && <span className="animate-pulse">...</span>}
        {!isCalling && toolCall.result && (
          expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />
        )}
      </button>
      {expanded && output && (
        <div className="mt-1.5 ml-1 px-3 py-2 rounded-lg text-xs
                        bg-[var(--color-bg-tertiary)]/50 border border-[var(--color-border)]
                        animate-fade-in max-h-60 overflow-y-auto">
          <div className="prose-chat text-xs">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {output}
            </ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}

function ThinkingBlock({ text, isLast, isStreaming }: { text: string; isLast: boolean; isStreaming: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const isActive = isLast && isStreaming;

  return (
    <div className="flex flex-col">
      <button
        onClick={() => setExpanded(!expanded)}
        className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
          transition-all duration-150 cursor-pointer
          ${isActive
            ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20'
            : 'bg-[var(--color-bg-tertiary)] text-[var(--color-fg-muted)] border border-[var(--color-border)] hover:bg-[var(--color-bg-tertiary)]/80'
          }`}
      >
        <Brain size={13} />
        <span>{isActive ? 'Thinking...' : 'Thought process'}</span>
        {isActive && <Loader2 size={12} className="animate-spin" />}
        {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
      </button>
      {expanded && (
        <div className="mt-1.5 ml-1 px-3 py-2 rounded-lg text-xs italic
                        bg-[var(--color-bg-tertiary)]/50 border border-[var(--color-border)]
                        text-[var(--color-fg-muted)] max-h-60 overflow-y-auto animate-fade-in whitespace-pre-wrap">
          {text}
          {isActive && (
            <span className="inline-block w-1.5 h-3 ml-0.5 bg-purple-400 rounded-sm animate-pulse align-middle" />
          )}
        </div>
      )}
    </div>
  );
}

function SummarizingBlock({ done, summary }: { done: boolean; summary?: string }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="flex flex-col">
      <button
        onClick={() => summary && setExpanded(!expanded)}
        className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
          transition-all duration-150
          ${!done
            ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
            : 'bg-[var(--color-bg-tertiary)] text-[var(--color-fg-muted)] border border-[var(--color-border)] hover:bg-[var(--color-bg-tertiary)]/80 cursor-pointer'
          }`}
      >
        <FileText size={13} />
        <span>{!done ? 'Summarizing conversation...' : 'Conversation summarized'}</span>
        {!done && <Loader2 size={12} className="animate-spin" />}
        {done && summary && (expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />)}
      </button>
      {expanded && summary && (
        <div className="mt-1.5 ml-1 px-3 py-2 rounded-lg text-xs
                        bg-[var(--color-bg-tertiary)]/50 border border-[var(--color-border)]
                        text-[var(--color-fg-muted)] max-h-40 overflow-y-auto animate-fade-in whitespace-pre-wrap">
          {summary}
        </div>
      )}
    </div>
  );
}

function ExtractingBlock({ done, files }: { done: boolean; files?: string[] }) {
  return (
    <div className="flex flex-col gap-1">
      <div
        className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
          ${!done
            ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20'
            : 'bg-[var(--color-bg-tertiary)] text-[var(--color-fg-muted)] border border-[var(--color-border)]'
          }`}
      >
        <ScanText size={13} />
        <span>{!done ? 'Extracting text from files...' : 'Files processed'}</span>
        {!done && <Loader2 size={12} className="animate-spin" />}
      </div>
      {files && files.length > 0 && (
        <div className="flex flex-wrap gap-1 ml-1">
          {files.map((name, i) => (
            <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px]
                                     bg-[var(--color-bg-tertiary)] text-[var(--color-fg-muted)] border border-[var(--color-border)]">
              <CheckCircle2 size={10} className="text-emerald-400" />
              {name}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function TextBlock({ text, isLast, isStreaming }: { text: string; isLast: boolean; isStreaming: boolean }) {
  return (
    <div className="px-4 py-2.5 rounded-2xl text-sm leading-relaxed min-w-0
                    bg-[var(--color-assistant-bubble)] text-[var(--color-assistant-bubble-fg)] rounded-bl-md">
      <div className="prose-chat">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {text}
        </ReactMarkdown>
        {isLast && isStreaming && (
          <span className="inline-block w-1.5 h-4 ml-0.5 bg-[var(--color-fg-muted)] rounded-sm animate-pulse align-middle" />
        )}
      </div>
    </div>
  );
}

function ToolGroup({ blocks }: { blocks: ContentBlock[] }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {blocks.map((block) =>
        block.type === 'tool' ? (
          <ToolCallChip key={block.toolCall.id} toolCall={block.toolCall} />
        ) : null,
      )}
    </div>
  );
}

export default function MessageBubble({ message, isStreaming, conversationId }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const blocks = message.blocks;
  const [copied, setCopied] = useState(false);
  const [showExtractionTooltip, setShowExtractionTooltip] = useState(false);

  /** Copy only the message body text (no usage/cost/metadata). */
  const getMessageBodyText = useCallback((): string => {
    if (message.content && message.content.trim()) return message.content.trim();
    const blocks = message.blocks ?? [];
    const textParts = blocks
      .filter((b): b is ContentBlock & { type: 'text' } => b.type === 'text')
      .map((b) => b.text)
      .filter(Boolean);
    return textParts.join('\n\n') || '';
  }, [message.content, message.blocks]);

  const copyContent = useCallback(() => {
    const text = getMessageBodyText();
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [getMessageBodyText]);

  if (isUser) {
    const attachments = message.attachments;
    const fileBlocks = (message.blocks || []).filter((b): b is ContentBlock & { type: 'file' } => b.type === 'file');
    const uploadsBase = import.meta.env.VITE_API_URL || '/api';
    return (
      <div className="flex gap-3 animate-fade-in justify-end">
        <div className="flex flex-col gap-2 max-w-[80%] min-w-0 items-end">
          {fileBlocks.length > 0 ? (
            <div className="flex flex-wrap gap-1.5 justify-end">
              {fileBlocks.map((block, i) => {
                const ext = (block.filename || '').split('.').pop()?.toLowerCase() ?? '';
                const isImg = ['png', 'jpg', 'jpeg', 'webp', 'gif'].includes(ext);
                const url = `${uploadsBase}/uploads/${block.path}`;
                return isImg ? (
                  <a
                    key={i}
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block rounded-lg overflow-hidden border border-[var(--color-border)]
                               max-w-[120px] max-h-[120px] hover:opacity-90 transition-opacity"
                  >
                    <img src={url} alt={block.filename} className="w-full h-full object-cover max-w-[120px] max-h-[120px]" />
                  </a>
                ) : (
                  <a
                    key={i}
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs
                               bg-[var(--color-accent)]/10 text-[var(--color-accent)]
                               border border-[var(--color-accent)]/20 hover:opacity-90"
                  >
                    <FileText size={12} />
                    <span className="max-w-[150px] truncate">{block.filename}</span>
                  </a>
                );
              })}
            </div>
          ) : attachments && attachments.length > 0 ? (
            <div className="flex flex-wrap gap-1 justify-end">
              {attachments.map((name, i) => {
                const ext = name.split('.').pop()?.toLowerCase() ?? '';
                const isImg = ['png', 'jpg', 'jpeg', 'webp', 'gif'].includes(ext);
                return (
                  <span key={i} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs
                                           bg-[var(--color-accent)]/10 text-[var(--color-accent)]
                                           border border-[var(--color-accent)]/20">
                    {isImg ? <Image size={12} /> : <Paperclip size={12} />}
                    <span className="max-w-[150px] truncate">{name}</span>
                  </span>
                );
              })}
            </div>
          ) : null}
          <div className="px-4 py-2.5 rounded-2xl text-sm leading-relaxed min-w-0
                          bg-[var(--color-user-bubble)] text-[var(--color-user-bubble-fg)] rounded-br-md">
            <span className="whitespace-pre-wrap">{message.content}</span>
          </div>
          <div className="flex items-center justify-end">
            <button
              type="button"
              onClick={copyContent}
              className="p-1 rounded text-[var(--color-fg-muted)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-fg)] transition-colors"
              title="Copy message text"
              aria-label="Copy message text"
            >
              {copied ? <Check size={14} /> : <Copy size={14} />}
            </button>
          </div>
        </div>
        <div className="flex items-start pt-1 shrink-0">
          <div className="flex items-center justify-center w-7 h-7 rounded-full bg-[var(--color-accent)]">
            <User size={14} className="text-white" />
          </div>
        </div>
      </div>
    );
  }

  const hasUsageDetails =
    message.usage ||
    message.extraction_usage ||
    (message.cost_usd != null && message.cost_usd > 0);

  const usageTooltipContent = hasUsageDetails ? (
      <div className="text-xs min-w-[200px]">
        {message.usage && (
          <div className="mb-2">
            <div className="font-medium text-[var(--color-fg-muted)] mb-0.5">Chat</div>
            <div className="flex flex-col gap-0.5 text-[var(--color-fg)]">
              <div>Total: {formatTokenCount(message.usage.total_tokens)} tokens</div>
              <div className="text-[var(--color-fg-muted)]">
                In {formatTokenCount(message.usage.input_tokens)} · Out {formatTokenCount(message.usage.output_tokens)}
                {message.usage.cache_tokens ? ` · Cache ${formatTokenCount(message.usage.cache_tokens)}` : ''}
              </div>
            </div>
          </div>
        )}
        {message.extraction_usage && (
          <div className="mb-2">
            <div className="font-medium text-[var(--color-fg-muted)] mb-0.5">Image extraction</div>
            <div className="flex flex-col gap-0.5 text-[var(--color-fg)]">
              <div>Total: {formatTokenCount(message.extraction_usage.total_tokens)} tokens</div>
              <div className="text-[var(--color-fg-muted)]">
                In {formatTokenCount(message.extraction_usage.input_tokens)} · Out {formatTokenCount(message.extraction_usage.output_tokens)}
                {message.extraction_usage.cache_tokens ? ` · Cache ${formatTokenCount(message.extraction_usage.cache_tokens)}` : ''}
              </div>
            </div>
          </div>
        )}
        {message.cost_usd != null && message.cost_usd > 0 && (
          <div className="pt-1.5 border-t border-[var(--color-border)]">
            <div className="font-medium text-[var(--color-fg-muted)] mb-0.5">Cost</div>
            <div className="text-[var(--color-fg)] flex flex-col gap-0.5">
              <span>${message.cost_usd.toFixed(4)} USD</span>
              {message.cost_inr != null && <span>₹{message.cost_inr.toLocaleString('en-IN')} INR</span>}
            </div>
          </div>
        )}
      </div>
    ) : null;

  const copyButton = (
    <button
      type="button"
      onClick={copyContent}
      className="p-1 rounded text-[var(--color-fg-muted)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-fg)] transition-colors"
      title="Copy message text"
      aria-label="Copy message text"
    >
      {copied ? <Check size={14} /> : <Copy size={14} />}
    </button>
  );

  const usageFooter =
    message.role === 'assistant' && hasUsageDetails ? (
      <div className="text-xs text-[var(--color-fg-muted)] mt-1 flex items-center gap-2 flex-wrap">
        <span
          className="relative inline-flex"
          onMouseEnter={() => setShowExtractionTooltip(true)}
          onMouseLeave={() => setShowExtractionTooltip(false)}
        >
          <Info size={14} className="shrink-0 cursor-help" aria-label="Usage details" />
          {showExtractionTooltip && usageTooltipContent && (
            <div
              className="absolute bottom-full left-0 mb-1 px-3 py-2.5 rounded-lg border border-[var(--color-border)]
                bg-[var(--color-bg)] text-[var(--color-fg)] shadow-lg z-50"
              role="tooltip"
            >
              {usageTooltipContent}
            </div>
          )}
        </span>
        {copyButton}
      </div>
    ) : message.role === 'assistant' ? (
      <div className="mt-1 flex items-center gap-1">{copyButton}</div>
    ) : null;

  if (!blocks || blocks.length === 0) {
    if (!message.content && !isStreaming) return null;
    return (
      <div className="flex gap-3 animate-fade-in justify-start">
        <div className="flex items-start pt-1 shrink-0">
          <div className="flex items-center justify-center w-7 h-7 rounded-full bg-[var(--color-bg-tertiary)]">
            <Bot size={14} className="text-[var(--color-fg-muted)]" />
          </div>
        </div>
        <div className="flex flex-col gap-2 max-w-[80%] min-w-0">
          <TextBlock text={message.content} isLast isStreaming={!!isStreaming} />
          {usageFooter}
        </div>
      </div>
    );
  }

  const groups: { kind: 'text' | 'tools' | 'table' | 'thinking' | 'summarizing' | 'extracting'; items: ContentBlock[] }[] = [];
  for (const block of blocks) {
    if (block.type === 'text') {
      groups.push({ kind: 'text', items: [block] });
    } else if (block.type === 'table') {
      groups.push({ kind: 'table', items: [block] });
    } else if (block.type === 'thinking') {
      groups.push({ kind: 'thinking', items: [block] });
    } else if (block.type === 'summarizing') {
      groups.push({ kind: 'summarizing', items: [block] });
    } else if (block.type === 'extracting') {
      groups.push({ kind: 'extracting', items: [block] });
    } else {
      const lastGroup = groups[groups.length - 1];
      if (lastGroup && lastGroup.kind === 'tools') {
        lastGroup.items.push(block);
      } else {
        groups.push({ kind: 'tools', items: [block] });
      }
    }
  }

  return (
    <div className="flex gap-3 animate-fade-in justify-start">
      <div className="flex items-start pt-1 shrink-0">
        <div className="flex items-center justify-center w-7 h-7 rounded-full bg-[var(--color-bg-tertiary)]">
          <Bot size={14} className="text-[var(--color-fg-muted)]" />
        </div>
      </div>
      <div className="flex flex-col gap-2 max-w-[90%] min-w-0">
        {groups.map((group, gi) => {
          if (group.kind === 'thinking') {
            const thinkBlock = group.items[0] as { type: 'thinking'; text: string };
            const isLast = gi === groups.length - 1;
            return (
              <ThinkingBlock
                key={`think-${gi}`}
                text={thinkBlock.text}
                isLast={isLast}
                isStreaming={!!isStreaming}
              />
            );
          }
          if (group.kind === 'summarizing') {
            const sumBlock = group.items[0] as { type: 'summarizing'; done: boolean; summary?: string };
            return (
              <SummarizingBlock
                key={`sum-${gi}`}
                done={sumBlock.done}
                summary={sumBlock.summary}
              />
            );
          }
          if (group.kind === 'extracting') {
            const extBlock = group.items[0] as { type: 'extracting'; done: boolean; files?: string[] };
            return (
              <ExtractingBlock
                key={`ext-${gi}`}
                done={extBlock.done}
                files={extBlock.files}
              />
            );
          }
          if (group.kind === 'text') {
            const textBlock = group.items[0] as { type: 'text'; text: string };
            const isLast = gi === groups.length - 1;
            return (
              <TextBlock
                key={`text-${gi}`}
                text={textBlock.text}
                isLast={isLast}
                isStreaming={!!isStreaming}
              />
            );
          }
          if (group.kind === 'table') {
            const tableBlock = group.items[0] as { type: 'table'; rows: QuoteRow[] };
            return <QuoteTable key={`table-${gi}`} initialRows={tableBlock.rows} conversationId={conversationId} />;
          }
          return <ToolGroup key={`tools-${gi}`} blocks={group.items} />;
        })}
        {isStreaming && groups.length > 0 && groups[groups.length - 1].kind === 'tools' && (
          <div className="px-4 py-2.5 rounded-2xl text-sm leading-relaxed min-w-0
                          bg-[var(--color-assistant-bubble)] text-[var(--color-assistant-bubble-fg)] rounded-bl-md">
            <span className="inline-block w-1.5 h-4 bg-[var(--color-fg-muted)] rounded-sm animate-pulse" />
          </div>
        )}
        {usageFooter}
      </div>
    </div>
  );
}
