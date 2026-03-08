import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { BarChart3, MessageSquare, Download, FileSpreadsheet, ExternalLink } from 'lucide-react';
import { fetchUsage, fetchSavedQuotes, downloadQuote, type UsageResponse, type SavedQuote } from '../lib/api';
import { CONVERSATION_ID_PARAM } from '../hooks/useChat';

const TOKEN_COLORS = {
  input_tokens: '#6366f1',
  output_tokens: '#22c55e',
  cache_tokens: '#f59e0b',
  total_tokens: '#64748b',
};

const TOOL_LABELS: Record<string, string> = {
  search_hyma: 'Search Hyma',
  get_hyma_product_details: 'Hyma Details',
  search_spectrochem: 'Search Spectrochem',
  get_spectrochem_product_details: 'Spectrochem Details',
  search_glosil: 'Search Glosil',
  get_glosil_product_details: 'Glosil Details',
  search_tci: 'Search TCI',
  get_tci_product_details: 'TCI Details',
  prepare_quote_table: 'Quote Table',
};

export default function Dashboard() {
  const [data, setData] = useState<UsageResponse | null>(null);
  const [quotes, setQuotes] = useState<SavedQuote[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchUsage()
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load usage');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchSavedQuotes()
      .then((res) => {
        if (!cancelled) setQuotes(res);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg)]">
        <div className="text-[var(--color-fg-muted)]">Loading usage…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg)]">
        <div className="text-red-500">{error}</div>
      </div>
    );
  }

  const totals = data?.totals ?? { input_tokens: 0, output_tokens: 0, total_tokens: 0, cache_tokens: 0 };
  const cost = data?.cost ?? 0;
  const costInr = data?.cost_inr ?? null;
  const usdToInrRate = data?.usd_to_inr_rate ?? null;
  const byDay = data?.by_day ?? [];
  const byToolCalls = (data?.by_tool_calls ?? []).map((t) => ({
    ...t,
    tool_label: TOOL_LABELS[t.tool_name] ?? t.tool_name,
  }));

  const pieData = [
    { name: 'Input', value: totals.input_tokens, color: TOKEN_COLORS.input_tokens },
    { name: 'Output', value: totals.output_tokens, color: TOKEN_COLORS.output_tokens },
    { name: 'Cache', value: totals.cache_tokens, color: TOKEN_COLORS.cache_tokens },
  ].filter((d) => d.value > 0);

  const formatTokens = (n: number) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${(n / 1e3).toFixed(1)}K` : String(n));
  const formatTooltipValue = (value: unknown): [string, string] => [formatTokens(Number(value ?? 0)), ''];

  return (
    <div className="min-h-screen bg-[var(--color-bg)] text-[var(--color-fg)]">
      <header className="sticky top-0 z-10 border-b border-[var(--color-border)] bg-[var(--color-bg)]/95 backdrop-blur">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <BarChart3 className="w-6 h-6 text-[var(--color-accent)]" />
            <h1 className="text-lg font-semibold">Token usage</h1>
          </div>
          <Link
            to="/"
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-[var(--color-fg-muted)] hover:bg-[var(--color-bg-secondary)] hover:text-[var(--color-fg)] transition-colors"
          >
            <MessageSquare className="w-4 h-4" />
            Chat
          </Link>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Summary cards */}
        <section className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 mb-10">
          <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-5">
            <div className="text-xs font-medium uppercase tracking-wide text-[var(--color-fg-muted)] mb-1">Input tokens</div>
            <div className="text-2xl font-semibold" style={{ color: TOKEN_COLORS.input_tokens }}>
              {formatTokens(totals.input_tokens)}
            </div>
          </div>
          <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-5">
            <div className="text-xs font-medium uppercase tracking-wide text-[var(--color-fg-muted)] mb-1">Output tokens</div>
            <div className="text-2xl font-semibold" style={{ color: TOKEN_COLORS.output_tokens }}>
              {formatTokens(totals.output_tokens)}
            </div>
          </div>
          <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-5">
            <div className="text-xs font-medium uppercase tracking-wide text-[var(--color-fg-muted)] mb-1">Cache tokens</div>
            <div className="text-2xl font-semibold" style={{ color: TOKEN_COLORS.cache_tokens }}>
              {formatTokens(totals.cache_tokens)}
            </div>
          </div>
          <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-5">
            <div className="text-xs font-medium uppercase tracking-wide text-[var(--color-fg-muted)] mb-1">Total tokens</div>
            <div className="text-2xl font-semibold text-[var(--color-fg)]">
              {formatTokens(totals.total_tokens)}
            </div>
          </div>
          <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-5">
            <div className="text-xs font-medium uppercase tracking-wide text-[var(--color-fg-muted)] mb-1">Estimated cost (USD)</div>
            <div className="text-2xl font-semibold text-[var(--color-fg)]">
              ${cost.toFixed(4)}
            </div>
          </div>
          <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-5">
            <div className="text-xs font-medium uppercase tracking-wide text-[var(--color-fg-muted)] mb-1">
              Estimated cost (₹ INR)
              {usdToInrRate != null && (
                <span className="block font-normal normal-case mt-0.5">@ ₹{usdToInrRate.toFixed(2)}/USD</span>
              )}
            </div>
            <div className="text-2xl font-semibold text-[var(--color-fg)]">
              {costInr != null ? (
                <>₹{costInr.toLocaleString('en-IN', { maximumFractionDigits: 2 })}</>
              ) : (
                <span className="text-[var(--color-fg-muted)] text-base">—</span>
              )}
            </div>
          </div>
        </section>

        {/* Charts row */}
        <div className="grid lg:grid-cols-2 gap-8 mb-10">
          {/* Tokens over time */}
          <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-6">
            <h2 className="text-sm font-semibold text-[var(--color-fg-muted)] uppercase tracking-wide mb-4">
              Tokens over time
            </h2>
            {byDay.length > 0 ? (
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={byDay} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                    <XAxis dataKey="date" tick={{ fill: 'var(--color-fg-muted)', fontSize: 12 }} />
                    <YAxis tick={{ fill: 'var(--color-fg-muted)', fontSize: 12 }} tickFormatter={formatTokens} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'var(--color-bg)',
                        border: '1px solid var(--color-border)',
                        borderRadius: '8px',
                      }}
                      labelStyle={{ color: 'var(--color-fg)' }}
                      formatter={formatTooltipValue}
                      labelFormatter={(label) => `Date: ${label}`}
                    />
                    <Legend />
                    <Line type="monotone" dataKey="input_tokens" name="Input" stroke={TOKEN_COLORS.input_tokens} strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="output_tokens" name="Output" stroke={TOKEN_COLORS.output_tokens} strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="cache_tokens" name="Cache" stroke={TOKEN_COLORS.cache_tokens} strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-72 flex items-center justify-center text-[var(--color-fg-muted)] text-sm">
                No usage data yet
              </div>
            )}
          </section>

          {/* Breakdown pie */}
          <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-6">
            <h2 className="text-sm font-semibold text-[var(--color-fg-muted)] uppercase tracking-wide mb-4">
              Token breakdown
            </h2>
            {pieData.length > 0 ? (
              <div className="h-72 flex items-center justify-center">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={100}
                      paddingAngle={2}
                      dataKey="value"
                      nameKey="name"
                      label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}
                    >
                      {pieData.map((entry, i) => (
                        <Cell key={i} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'var(--color-bg)',
                        border: '1px solid var(--color-border)',
                        borderRadius: '8px',
                      }}
                      formatter={formatTooltipValue}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-72 flex items-center justify-center text-[var(--color-fg-muted)] text-sm">
                No usage data yet
              </div>
            )}
          </section>
        </div>

        {/* Tool calls: success vs failure */}
        <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-6 mb-10">
          <h2 className="text-sm font-semibold text-[var(--color-fg-muted)] uppercase tracking-wide mb-4">
            Tool calls — success vs failure
          </h2>
          {byToolCalls.length > 0 ? (
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={byToolCalls}
                  margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis dataKey="tool_label" tick={{ fill: 'var(--color-fg-muted)', fontSize: 11 }} />
                  <YAxis tick={{ fill: 'var(--color-fg-muted)', fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'var(--color-bg)',
                      border: '1px solid var(--color-border)',
                      borderRadius: '8px',
                    }}
                  />
                  <Legend />
                  <Bar dataKey="success_count" name="Success" fill="#22c55e" radius={[2, 2, 0, 0]} />
                  <Bar dataKey="failure_count" name="Failure" fill="#ef4444" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-48 flex items-center justify-center text-[var(--color-fg-muted)] text-sm">
              No tool call data yet
            </div>
          )}
        </section>

        {/* Recent quotes */}
        <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-secondary)] p-6">
          <h2 className="text-sm font-semibold text-[var(--color-fg-muted)] uppercase tracking-wide mb-4 flex items-center gap-2">
            <FileSpreadsheet className="w-4 h-4" />
            Recent quotes
          </h2>
          {quotes.length > 0 ? (
            <ul className="space-y-2">
              {quotes.map((q) => (
                <li
                  key={q.id}
                  className="flex items-center justify-between gap-4 py-2 px-3 rounded-lg hover:bg-[var(--color-bg-tertiary)]"
                >
                  <Link
                    to={q.conversation_id ? `/?${CONVERSATION_ID_PARAM}=${q.conversation_id}` : '#'}
                    className={`min-w-0 flex-1 flex items-center gap-2 ${q.conversation_id ? 'cursor-pointer' : 'cursor-default pointer-events-none'}`}
                    title={q.conversation_id ? 'Open conversation' : undefined}
                  >
                    <div className="min-w-0 flex-1">
                      <span className="font-medium truncate block">{q.file_name}</span>
                    {q.message_prompt ? (
                      <p className="text-xs text-[var(--color-fg-muted)] truncate mt-0.5" title={q.message_prompt}>
                        “{q.message_prompt.length > 60 ? q.message_prompt.slice(0, 60) + '…' : q.message_prompt}”
                      </p>
                    ) : null}
                    <span className="text-xs text-[var(--color-fg-muted)]">
                      {q.rows_count} rows
                      {q.conversation_id ? ` · Conv ${q.conversation_id.slice(0, 8)}…` : ''}
                      {' · '}
                      {new Date(q.created_at).toLocaleString()}
                    </span>
                    </div>
                    {q.conversation_id ? (
                      <ExternalLink className="w-4 h-4 shrink-0 text-[var(--color-fg-muted)]" aria-hidden />
                    ) : null}
                  </Link>
                  <a
                    href="#"
                    onClick={async (e) => {
                      e.preventDefault();
                      try {
                        const blob = await downloadQuote(q.id);
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = q.file_name || 'quote.xlsx';
                        a.click();
                        URL.revokeObjectURL(url);
                      } catch (err) {
                        console.error(err);
                      }
                    }}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--color-accent)] text-white text-sm font-medium hover:opacity-90 shrink-0"
                  >
                    <Download className="w-4 h-4" />
                    Download
                  </a>
                </li>
              ))}
            </ul>
          ) : (
            <div className="py-8 text-center text-[var(--color-fg-muted)] text-sm">
              No saved quotes yet. Generate a quote from a chat to see it here.
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
