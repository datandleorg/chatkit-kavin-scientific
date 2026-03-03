import { User, Bot, Search, CheckCircle2, ChevronDown, ChevronRight, AlertCircle, Brain, Loader2, FileText, Paperclip, ScanText, Image } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Message, ToolCall, ContentBlock, QuoteRow } from '../types';
import { useState } from 'react';
import QuoteTable from './QuoteTable';

interface MessageBubbleProps {
  message: Message;
  isStreaming?: boolean;
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

export default function MessageBubble({ message, isStreaming }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const blocks = message.blocks;

  if (isUser) {
    const attachments = message.attachments;
    return (
      <div className="flex gap-3 animate-fade-in justify-end">
        <div className="flex flex-col gap-2 max-w-[80%] min-w-0 items-end">
          {attachments && attachments.length > 0 && (
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
          )}
          <div className="px-4 py-2.5 rounded-2xl text-sm leading-relaxed min-w-0
                          bg-[var(--color-user-bubble)] text-[var(--color-user-bubble-fg)] rounded-br-md">
            <span className="whitespace-pre-wrap">{message.content}</span>
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
            return <QuoteTable key={`table-${gi}`} initialRows={tableBlock.rows} />;
          }
          return <ToolGroup key={`tools-${gi}`} blocks={group.items} />;
        })}
        {isStreaming && groups.length > 0 && groups[groups.length - 1].kind === 'tools' && (
          <div className="px-4 py-2.5 rounded-2xl text-sm leading-relaxed min-w-0
                          bg-[var(--color-assistant-bubble)] text-[var(--color-assistant-bubble-fg)] rounded-bl-md">
            <span className="inline-block w-1.5 h-4 bg-[var(--color-fg-muted)] rounded-sm animate-pulse" />
          </div>
        )}
      </div>
    </div>
  );
}
