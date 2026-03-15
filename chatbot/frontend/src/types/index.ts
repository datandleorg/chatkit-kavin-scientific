export interface ToolCall {
  id: string;
  name: string;
  input: string;
  status: 'calling' | 'done';
  result?: string;
}

export interface QuoteRow {
  name: string;
  catalogNo: string;
  hsn: string;
  brand: string;
  unit: string;
  rate: number;
  discount: number;
  qty: number;
  gstPercent: number;
  sourceUrl: string;
}

export type ContentBlock =
  | { type: 'text'; text: string }
  | { type: 'tool'; toolCall: ToolCall }
  | { type: 'table'; rows: QuoteRow[] }
  | { type: 'thinking'; text: string }
  | { type: 'summarizing'; done: boolean; summary?: string }
  | { type: 'extracting'; done: boolean; files?: string[] }
  | { type: 'file'; filename: string; path: string };

export interface MessageUsage {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cache_tokens: number;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  blocks?: ContentBlock[];
  attachments?: string[];
  usage?: MessageUsage;
  extraction_usage?: MessageUsage;
  cost_usd?: number;
  cost_inr?: number;
}

export interface Conversation {
  id: string;
  title: string;
  updated_at: string;
}

export interface ChatRequest {
  message: string;
  session_id?: string;
  conversation_id?: string;
  history: { role: string; content: string }[];
}

export interface UploadResponse {
  session_id: string;
  chemical_list: string[];
}

export interface ScrapeResponse {
  scraping_results: ChemicalResult[];
}

export interface ChemicalResult {
  chemical: string;
  vendor: string;
  price: string;
  pack_size: string;
  cas_number: string;
  availability: string;
  url: string;
}

export interface ReportResponse {
  final_report: string;
}
