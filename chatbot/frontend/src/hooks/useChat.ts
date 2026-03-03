import { useState, useCallback, useRef } from 'react';
import type { Message, ContentBlock, QuoteRow } from '../types';
import type { ToolStartEvent, ToolEndEvent, TableDataEvent } from '../lib/api';
import { streamChat, fetchMessages as apiFetchMessages } from '../lib/api';

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [conversationId, setConversationId] = useState<string | null>(null);
  const abortRef = useRef(false);

  const updateLastAssistant = useCallback(
    (updater: (msg: Message) => Message) => {
      setMessages((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last?.role === 'assistant') {
          updated[updated.length - 1] = updater(last);
        }
        return updated;
      });
    },
    [],
  );

  const newChat = useCallback(() => {
    setMessages([]);
    setConversationId(null);
    setSessionId(undefined);
  }, []);

  const loadConversation = useCallback(async (convId: string) => {
    try {
      const dbMessages = await apiFetchMessages(convId);
      const mapped: Message[] = dbMessages.map((m) => ({
        id: m.id || crypto.randomUUID(),
        role: m.role,
        content: m.content || '',
        timestamp: new Date(m.timestamp || Date.now()),
        blocks: m.blocks && m.blocks.length > 0 ? m.blocks : undefined,
      }));
      setMessages(mapped);
      setConversationId(convId);
    } catch (err) {
      console.error('Failed to load conversation:', err);
    }
  }, []);

  const sendMessage = useCallback(
    async (text: string, files?: File[]) => {
      if (isStreaming) return;
      abortRef.current = false;

      const userMsg: Message = {
        id: crypto.randomUUID(),
        role: 'user',
        content: text,
        timestamp: new Date(),
        attachments: files?.map((f) => f.name),
      };

      const assistantMsg: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        blocks: [],
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setIsStreaming(true);

      const history = [...messages, userMsg].map((m) => ({
        role: m.role,
        content: m.content,
      }));

      await streamChat(text, history, sessionId, conversationId, files, {
        onConversationId: (id) => {
          setConversationId(id);
        },
        onExtracting: (active) => {
          if (abortRef.current) return;
          updateLastAssistant((msg) => {
            const blocks = [...(msg.blocks ?? [])];
            if (active) {
              blocks.push({ type: 'extracting', done: false });
            } else {
              const idx = blocks.findIndex((b) => b.type === 'extracting');
              if (idx >= 0) {
                blocks[idx] = { ...blocks[idx], done: true } as typeof blocks[number];
              }
            }
            return { ...msg, blocks };
          });
        },
        onFileExtracted: (event) => {
          if (abortRef.current) return;
          updateLastAssistant((msg) => {
            const blocks = [...(msg.blocks ?? [])];
            const idx = blocks.findIndex((b) => b.type === 'extracting');
            if (idx >= 0) {
              const blk = blocks[idx] as { type: 'extracting'; done: boolean; files?: string[] };
              blocks[idx] = { ...blk, files: [...(blk.files ?? []), event.filename] };
            }
            return { ...msg, blocks };
          });
        },
        onThinking: (text) => {
          if (abortRef.current) return;
          updateLastAssistant((msg) => {
            const blocks = [...(msg.blocks ?? [])];
            const last = blocks[blocks.length - 1];
            if (last && last.type === 'thinking') {
              blocks[blocks.length - 1] = { type: 'thinking', text: last.text + text };
            } else {
              blocks.push({ type: 'thinking', text });
            }
            return { ...msg, blocks };
          });
        },
        onSummarizing: (active, summary) => {
          if (abortRef.current) return;
          updateLastAssistant((msg) => {
            const blocks = [...(msg.blocks ?? [])];
            if (active) {
              blocks.push({ type: 'summarizing', done: false });
            } else {
              const idx = blocks.findIndex((b) => b.type === 'summarizing');
              if (idx >= 0) {
                blocks[idx] = { type: 'summarizing', done: true, summary };
              }
            }
            return { ...msg, blocks };
          });
        },
        onToken: (token) => {
          if (abortRef.current) return;
          updateLastAssistant((msg) => {
            const blocks = [...(msg.blocks ?? [])];
            const last = blocks[blocks.length - 1];
            if (last && last.type === 'text') {
              blocks[blocks.length - 1] = { type: 'text', text: last.text + token };
            } else {
              blocks.push({ type: 'text', text: token });
            }
            return { ...msg, content: msg.content + token, blocks };
          });
        },
        onToolStart: (event: ToolStartEvent) => {
          if (abortRef.current) return;
          const toolBlock: ContentBlock = {
            type: 'tool',
            toolCall: {
              id: event.run_id,
              name: event.name,
              input: event.input,
              status: 'calling',
            },
          };
          updateLastAssistant((msg) => ({
            ...msg,
            blocks: [...(msg.blocks ?? []), toolBlock],
          }));
        },
        onToolEnd: (event: ToolEndEvent) => {
          if (abortRef.current) return;
          updateLastAssistant((msg) => ({
            ...msg,
            blocks: (msg.blocks ?? []).map((block) =>
              block.type === 'tool' && block.toolCall.id === event.run_id
                ? { ...block, toolCall: { ...block.toolCall, status: 'done' as const, result: event.output } }
                : block,
            ),
          }));
        },
        onTableData: (event: TableDataEvent) => {
          if (abortRef.current) return;
          const rows: QuoteRow[] = (event.rows ?? []).map((r) => ({
            name: String(r.name ?? ''),
            catalogNo: String(r.catalog_no ?? ''),
            hsn: String(r.hsn ?? ''),
            brand: String(r.brand ?? ''),
            unit: String(r.unit ?? ''),
            rate: Number(r.rate ?? 0),
            discount: Number(r.discount ?? 0),
            qty: Number(r.qty ?? 1),
            gstPercent: Number(r.gst_percent ?? 0),
            sourceUrl: String(r.source_url ?? ''),
          }));
          const tableBlock: ContentBlock = { type: 'table', rows };
          updateLastAssistant((msg) => {
            const blocks = (msg.blocks ?? []).filter(
              (b) => !(b.type === 'tool' && b.toolCall.name === 'prepare_quote_table'),
            );
            return { ...msg, blocks: [...blocks, tableBlock] };
          });
        },
        onDone: () => setIsStreaming(false),
        onError: (error) => {
          updateLastAssistant((msg) => ({
            ...msg,
            content: msg.content || `Sorry, an error occurred: ${error}`,
            blocks: [
              ...(msg.blocks ?? []),
              ...(msg.content ? [] : [{ type: 'text' as const, text: `Sorry, an error occurred: ${error}` }]),
            ],
          }));
          setIsStreaming(false);
        },
      });
    },
    [isStreaming, messages, sessionId, conversationId, updateLastAssistant],
  );

  const stopStreaming = useCallback(() => {
    abortRef.current = true;
    setIsStreaming(false);
  }, []);

  return { messages, isStreaming, sessionId, conversationId, sendMessage, stopStreaming, newChat, loadConversation };
}
