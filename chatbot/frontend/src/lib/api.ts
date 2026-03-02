import type { UploadResponse, ScrapeResponse, ReportResponse, Conversation, Message } from '../types';

const BASE_URL = import.meta.env.VITE_API_URL || '/api';

export interface ToolStartEvent {
  name: string;
  run_id: string;
  input: string;
}

export interface ToolEndEvent {
  name: string;
  run_id: string;
  output: string;
}

export interface TableDataEvent {
  rows: Record<string, unknown>[];
  run_id: string;
}

export interface StreamCallbacks {
  onToken?: (token: string) => void;
  onToolStart?: (event: ToolStartEvent) => void;
  onToolEnd?: (event: ToolEndEvent) => void;
  onTableData?: (event: TableDataEvent) => void;
  onConversationId?: (id: string) => void;
  onDone?: () => void;
  onError?: (error: string) => void;
}

export async function streamChat(
  message: string,
  history: { role: string; content: string }[],
  sessionId?: string,
  conversationId?: string | null,
  callbacks?: StreamCallbacks,
) {
  const { onToken, onToolStart, onToolEnd, onTableData, onConversationId, onDone, onError } = callbacks ?? {};
  try {
    const res = await fetch(`${BASE_URL}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, history, session_id: sessionId, conversation_id: conversationId || undefined }),
    });

    if (!res.ok) {
      const errText = await res.text();
      onError?.(errText || `HTTP ${res.status}`);
      return;
    }

    const reader = res.body?.getReader();
    if (!reader) {
      onError?.('No response body');
      return;
    }

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6).trim();
          if (data === '[DONE]') {
            onDone?.();
            return;
          }
          try {
            const parsed = JSON.parse(data);
            if (parsed.conversation_id) onConversationId?.(parsed.conversation_id);
            if (parsed.token) onToken?.(parsed.token);
            if (parsed.tool_start) onToolStart?.(parsed.tool_start);
            if (parsed.tool_end) onToolEnd?.(parsed.tool_end);
            if (parsed.table_data) onTableData?.(parsed.table_data);
            if (parsed.error) onError?.(parsed.error);
          } catch {
            if (data) onToken?.(data);
          }
        }
      }
    }

    onDone?.();
  } catch (err) {
    onError?.(err instanceof Error ? err.message : 'Stream failed');
  }
}

export async function uploadFiles(files: FileList): Promise<UploadResponse> {
  const formData = new FormData();
  Array.from(files).forEach((f) => formData.append('files', f));

  const res = await fetch(`${BASE_URL}/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return res.json();
}

export async function confirmChemicals(
  sessionId: string,
  chemicals: string[],
): Promise<ScrapeResponse> {
  const res = await fetch(`${BASE_URL}/confirm-chemicals`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, chemical_list: chemicals }),
  });

  if (!res.ok) throw new Error(`Confirm chemicals failed: ${res.status}`);
  return res.json();
}

export async function confirmResults(
  sessionId: string,
  results: unknown[],
): Promise<ReportResponse> {
  const res = await fetch(`${BASE_URL}/confirm-results`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, scraping_results: results }),
  });

  if (!res.ok) throw new Error(`Confirm results failed: ${res.status}`);
  return res.json();
}

export async function fetchConversations(): Promise<Conversation[]> {
  const res = await fetch(`${BASE_URL}/conversations`);
  if (!res.ok) throw new Error(`Fetch conversations failed: ${res.status}`);
  return res.json();
}

export async function createConversation(): Promise<Conversation> {
  const res = await fetch(`${BASE_URL}/conversations`, { method: 'POST' });
  if (!res.ok) throw new Error(`Create conversation failed: ${res.status}`);
  return res.json();
}

export async function fetchMessages(conversationId: string): Promise<Message[]> {
  const res = await fetch(`${BASE_URL}/conversations/${conversationId}/messages`);
  if (!res.ok) throw new Error(`Fetch messages failed: ${res.status}`);
  const raw: { id: string; role: 'user' | 'assistant'; content: string; blocks?: Message['blocks']; created_at: string }[] = await res.json();
  return raw.map((m) => ({
    id: m.id,
    role: m.role,
    content: m.content,
    timestamp: new Date(m.created_at),
    blocks: m.blocks,
  }));
}

export async function deleteConversation(conversationId: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/conversations/${conversationId}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`Delete conversation failed: ${res.status}`);
}

export async function exportQuoteXlsx(
  rows: { name: string; catalogNo: string; hsn: string; brand: string; unit: string; rate: number; discount: number; qty: number; gstPercent: number }[],
  fileName: string = 'quote',
): Promise<Blob> {
  const res = await fetch(`${BASE_URL}/export-quote`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rows, file_name: fileName }),
  });

  if (!res.ok) throw new Error(`Export quote failed: ${res.status}`);
  return res.blob();
}
