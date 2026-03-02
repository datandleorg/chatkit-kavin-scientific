import { User, Bot, Search, CheckCircle2, ChevronDown, ChevronRight, AlertCircle } from 'lucide-react';
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
    return (
      <div className="flex gap-3 animate-fade-in justify-end">
        <div className="flex flex-col gap-2 max-w-[80%] min-w-0">
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

  const groups: { kind: 'text' | 'tools' | 'table'; items: ContentBlock[] }[] = [];
  for (const block of blocks) {
    if (block.type === 'text') {
      groups.push({ kind: 'text', items: [block] });
    } else if (block.type === 'table') {
      groups.push({ kind: 'table', items: [block] });
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
