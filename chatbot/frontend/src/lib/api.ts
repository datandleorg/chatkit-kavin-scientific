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

export interface FileExtractedEvent {
  filename: string;
  preview: string;
}

export interface StreamCallbacks {
  onToken?: (token: string) => void;
  onThinking?: (text: string) => void;
  onSummarizing?: (active: boolean, summary?: string) => void;
  onExtracting?: (active: boolean) => void;
  onFileExtracted?: (event: FileExtractedEvent) => void;
  onToolStart?: (event: ToolStartEvent) => void;
  onToolEnd?: (event: ToolEndEvent) => void;
  onTableData?: (event: TableDataEvent) => void;
  onConversationId?: (id: string) => void;
  onDone?: () => void;
  onError?: (error: string) => void;
}

export async function streamChat(
  message: string,
  _history: { role: string; content: string }[],
  sessionId?: string,
  conversationId?: string | null,
  files?: File[],
  callbacks?: StreamCallbacks,
  model?: string | null,
  reasoning?: boolean,
) {
  void _history;
  const { onToken, onThinking, onSummarizing, onExtracting, onFileExtracted, onToolStart, onToolEnd, onTableData, onConversationId, onDone, onError } = callbacks ?? {};
  try {
    const formData = new FormData();
    formData.append('message', message);
    if (sessionId) formData.append('session_id', sessionId);
    if (conversationId) formData.append('conversation_id', conversationId);
    if (model) formData.append('model', model);
    const useReasoning = reasoning === true;
    formData.append('reasoning', useReasoning ? 'true' : 'false');
    if (files) {
      files.forEach((f) => formData.append('files', f));
    }

    const url = `${BASE_URL}/chat/stream?reasoning=${useReasoning ? 'true' : 'false'}`;
    const res = await fetch(url, {
      method: 'POST',
      body: formData,
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
            if (parsed.extracting !== undefined) onExtracting?.(parsed.extracting);
            if (parsed.file_extracted) onFileExtracted?.(parsed.file_extracted);
            if (parsed.thinking) onThinking?.(parsed.thinking);
            if (parsed.summarizing !== undefined) onSummarizing?.(parsed.summarizing);
            if (parsed.summary) onSummarizing?.(false, parsed.summary);
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

export interface UsageTotals {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cache_tokens: number;
}

export interface UsageByDay {
  date: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cache_tokens: number;
  message_count: number;
}

export interface UsageByToolCall {
  tool_name: string;
  success_count: number;
  failure_count: number;
}

export interface UsageResponse {
  totals: UsageTotals;
  by_day: UsageByDay[];
  by_tool_calls: UsageByToolCall[];
  cost?: number;
  cost_inr?: number | null;
  usd_to_inr_rate?: number | null;
}

export interface SavedQuote {
  id: string;
  conversation_id: string;
  file_name: string;
  rows_count: number;
  message_prompt?: string | null;
  created_at: string;
}

export async function fetchUsage(): Promise<UsageResponse> {
  const res = await fetch(`${BASE_URL}/usage`);
  if (!res.ok) throw new Error(`Fetch usage failed: ${res.status}`);
  return res.json();
}

export async function fetchSavedQuotes(limit: number = 50): Promise<SavedQuote[]> {
  const res = await fetch(`${BASE_URL}/quotes?limit=${limit}`);
  if (!res.ok) throw new Error(`Fetch quotes failed: ${res.status}`);
  return res.json();
}

export async function downloadQuote(quoteId: string): Promise<Blob> {
  const res = await fetch(`${BASE_URL}/quotes/${quoteId}/download`);
  if (!res.ok) throw new Error(`Download quote failed: ${res.status}`);
  return res.blob();
}

export async function exportQuoteXlsx(
  rows: { name: string; catalogNo: string; hsn: string; brand: string; unit: string; rate: number; discount: number; qty: number; gstPercent: number }[],
  fileName: string = 'quote',
  conversationId?: string | null,
): Promise<Blob> {
  const res = await fetch(`${BASE_URL}/export-quote`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rows, file_name: fileName, conversation_id: conversationId ?? undefined }),
  });

  if (!res.ok) throw new Error(`Export quote failed: ${res.status}`);
  return res.blob();
}

