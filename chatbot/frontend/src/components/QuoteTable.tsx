import { useState, useCallback, useRef, useEffect } from 'react';
import { Download, Plus, Trash2, ExternalLink, Loader2 } from 'lucide-react';
import type { QuoteRow } from '../types';

interface QuoteTableProps {
  initialRows: QuoteRow[];
  conversationId?: string | null;
}

/** Normalize a row from API (snake_case) or stream (camelCase) and coerce numbers so computed values are never NaN. */
function normalizeRow(r: Record<string, unknown>): QuoteRow {
  const num = (v: unknown, fallback: number) => {
    const n = Number(v);
    return Number.isFinite(n) ? n : fallback;
  };
  return {
    name: String(r.name ?? ''),
    catalogNo: String(r.catalogNo ?? r.catalog_no ?? ''),
    hsn: String(r.hsn ?? ''),
    brand: String(r.brand ?? ''),
    unit: String(r.unit ?? ''),
    rate: num(r.rate, 0),
    discount: num(r.discount, 0),
    qty: Math.max(1, num(r.qty, 1)),
    gstPercent: num(r.gstPercent ?? r.gst_percent, 18),
    sourceUrl: String(r.sourceUrl ?? r.source_url ?? ''),
  };
}

function computeRow(r: QuoteRow) {
  const rate = Number.isFinite(r.rate) ? r.rate : 0;
  const discount = Number.isFinite(r.discount) ? r.discount : 0;
  const qty = Number.isFinite(r.qty) && r.qty >= 1 ? r.qty : 1;
  const gstPercent = Number.isFinite(r.gstPercent) ? r.gstPercent : 0;
  const discountedRate = rate * (1 - discount / 100);
  const amount = discountedRate * qty;
  const gstValue = amount * (gstPercent / 100);
  const grandAmount = amount + gstValue;
  return { discountedRate, amount, gstValue, grandAmount };
}

function fmt(n: number): string {
  if (!Number.isFinite(n) || n === 0) return '0';
  return n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

const COL_DEFS = [
  { key: 'sno', label: 'S.no', minW: 40, initW: 48 },
  { key: 'name', label: 'Name of the items', minW: 100, initW: 200 },
  { key: 'catalogNo', label: 'Cat.No', minW: 60, initW: 100 },
  { key: 'hsn', label: 'HSN', minW: 60, initW: 90 },
  { key: 'brand', label: 'Brand', minW: 60, initW: 100 },
  { key: 'unit', label: 'Unit', minW: 50, initW: 80 },
  { key: 'rate', label: 'Rate/unit', minW: 60, initW: 90 },
  { key: 'discount', label: 'Dis.%', minW: 45, initW: 60 },
  { key: 'discountedRate', label: 'Rate/unit', minW: 60, initW: 90 },
  { key: 'qty', label: 'Qty', minW: 40, initW: 55 },
  { key: 'amount', label: 'Amount', minW: 60, initW: 90 },
  { key: 'gstPercent', label: 'GST%', minW: 45, initW: 60 },
  { key: 'gstValue', label: 'G.Val', minW: 60, initW: 90 },
  { key: 'grandAmount', label: 'G.Amt', minW: 72, initW: 110 },
];

function ResizeHandle({ onResize }: { onResize: (delta: number) => void }) {
  const startXRef = useRef(0);

  const onMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      startXRef.current = e.clientX;

      const onMouseMove = (ev: MouseEvent) => {
        const delta = ev.clientX - startXRef.current;
        startXRef.current = ev.clientX;
        onResize(delta);
      };

      const onMouseUp = () => {
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      };

      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup', onMouseUp);
    },
    [onResize],
  );

  return (
    <div
      onMouseDown={onMouseDown}
      className="absolute right-0 top-0 bottom-0 w-1.5 cursor-col-resize
                 hover:bg-[var(--color-accent)]/30 active:bg-[var(--color-accent)]/50
                 transition-colors z-10"
    />
  );
}

const inputClass =
  'w-full bg-transparent border border-transparent hover:border-[var(--color-border)] focus:border-[var(--color-accent)] rounded px-1 py-1 text-xs text-[var(--color-fg)] outline-none transition-colors';

export default function QuoteTable({ initialRows, conversationId }: QuoteTableProps) {
  const [rows, setRows] = useState<QuoteRow[]>(() => initialRows.map((r) => normalizeRow(r as unknown as Record<string, unknown>)));
  const [colWidths, setColWidths] = useState(() => COL_DEFS.map((c) => c.initW));

  // When conversation is loaded/refreshed, initialRows may be from API (snake_case); sync and normalize
  useEffect(() => {
    setRows(initialRows.map((r) => normalizeRow(r as unknown as Record<string, unknown>)));
  }, [initialRows]);

  const resizeCol = useCallback((colIdx: number, delta: number) => {
    setColWidths((prev) => {
      const next = [...prev];
      next[colIdx] = Math.max(COL_DEFS[colIdx].minW, next[colIdx] + delta);
      return next;
    });
  }, []);

  const updateRow = useCallback((index: number, field: keyof QuoteRow, value: string | number) => {
    setRows((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], [field]: value };
      return updated;
    });
  }, []);

  const deleteRow = useCallback((index: number) => {
    setRows((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const addRow = useCallback(() => {
    setRows((prev) => [
      ...prev,
      { name: '', catalogNo: '', hsn: '', brand: '', unit: '', rate: 0, discount: 0, qty: 1, gstPercent: 18, sourceUrl: '' },
    ]);
  }, []);

  const [exporting, setExporting] = useState(false);

  const exportXlsx = useCallback(async () => {
    setExporting(true);
    try {
      const { exportQuoteXlsx } = await import('../lib/api');
      const blob = await exportQuoteXlsx(
        rows.map((r) => ({
          name: r.name,
          catalogNo: r.catalogNo,
          hsn: r.hsn,
          brand: r.brand,
          unit: r.unit,
          rate: r.rate,
          discount: r.discount,
          qty: r.qty,
          gstPercent: r.gstPercent,
        })),
        'quote',
        conversationId,
      );

      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'quote.xlsx';
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export failed:', err);
    } finally {
      setExporting(false);
    }
  }, [rows]);

  let totalGrandAmount = 0;
  const computed = rows.map((r) => {
    const c = computeRow(r);
    totalGrandAmount += c.grandAmount;
    return c;
  });

  const actionColW = 48;

  // Min width so table doesn't shrink below content when container is narrow (enables horizontal scroll)
  const totalMinWidth =
    colWidths.reduce((sum, w, i) => sum + (i === 1 ? COL_DEFS[1].minW : w), 0) + actionColW;

  return (
    <div className="w-full min-w-0 rounded-xl border border-[var(--color-border)] overflow-hidden animate-fade-in">
      <div className="flex items-center justify-between px-4 py-2.5 bg-[var(--color-bg-tertiary)]">
        <span className="text-sm font-semibold text-[var(--color-fg)]">Procurement Quote</span>
        <div className="flex gap-2">
          <button
            onClick={addRow}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                       bg-[var(--color-accent)]/10 text-[var(--color-accent)] border border-[var(--color-accent)]/20
                       hover:bg-[var(--color-accent)]/20 transition-colors"
          >
            <Plus size={12} /> Add Row
          </button>
          <button
            onClick={exportXlsx}
            disabled={exporting}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                       bg-emerald-500/10 text-emerald-400 border border-emerald-500/20
                       hover:bg-emerald-500/20 transition-colors disabled:opacity-50"
          >
            {exporting ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
            {exporting ? 'Exporting...' : 'Export XLSX'}
          </button>
        </div>
      </div>

      <div className="overflow-x-auto min-w-0">
        <table
          className="text-xs border-collapse w-full"
          style={{ tableLayout: 'fixed', minWidth: totalMinWidth }}
        >
          <colgroup>
            {colWidths.map((w, i) =>
              i === 1 ? (
                <col key={i} style={{ minWidth: COL_DEFS[1].minW }} />
              ) : (
                <col key={i} style={{ width: w }} />
              ),
            )}
            <col style={{ width: actionColW }} />
          </colgroup>

          <thead>
            <tr className="bg-[var(--color-bg-tertiary)]/50">
              {COL_DEFS.map((col, ci) => (
                <th
                  key={col.key}
                  className="relative px-2 py-2 text-left font-semibold text-[var(--color-fg-muted)] border-b border-[var(--color-border)] whitespace-nowrap overflow-hidden text-ellipsis"
                >
                  {col.label}
                  <ResizeHandle onResize={(d) => resizeCol(ci, d)} />
                </th>
              ))}
              <th className="px-2 py-2 border-b border-[var(--color-border)]" />
            </tr>
          </thead>

          <tbody>
            {rows.map((row, ri) => {
              const c = computed[ri];
              return (
                <tr key={ri} className="border-b border-[var(--color-border)]/50 hover:bg-[var(--color-bg-tertiary)]/30 transition-colors">
                  <td className="px-2 py-1.5 text-[var(--color-fg-muted)]">{ri + 1}</td>

                  <td className="px-1 py-0.5">
                    <div className="flex items-center gap-1">
                      <input type="text" value={row.name} onChange={(e) => updateRow(ri, 'name', e.target.value)} className={inputClass} />
                      {row.sourceUrl && (
                        <a href={row.sourceUrl} target="_blank" rel="noopener noreferrer" className="shrink-0 text-[var(--color-accent)] hover:opacity-70">
                          <ExternalLink size={10} />
                        </a>
                      )}
                    </div>
                  </td>

                  {(['catalogNo', 'hsn', 'brand', 'unit'] as const).map((field) => (
                    <td key={field} className="px-1 py-0.5">
                      <input type="text" value={row[field]} onChange={(e) => updateRow(ri, field, e.target.value)} className={inputClass} />
                    </td>
                  ))}

                  <td className="px-1 py-0.5">
                    <input type="number" value={row.rate || ''} onChange={(e) => updateRow(ri, 'rate', parseFloat(e.target.value) || 0)} className={`${inputClass} text-right`} />
                  </td>
                  <td className="px-1 py-0.5">
                    <input type="number" value={row.discount || ''} onChange={(e) => updateRow(ri, 'discount', parseFloat(e.target.value) || 0)} className={`${inputClass} text-right`} />
                  </td>

                  <td className="px-2 py-1.5 text-right text-[var(--color-fg-muted)] overflow-hidden text-ellipsis">{fmt(c.discountedRate)}</td>

                  <td className="px-1 py-0.5">
                    <input type="number" value={row.qty || ''} onChange={(e) => updateRow(ri, 'qty', parseInt(e.target.value) || 1)} className={`${inputClass} text-right`} />
                  </td>

                  <td className="px-2 py-1.5 text-right text-[var(--color-fg-muted)] overflow-hidden text-ellipsis">{fmt(c.amount)}</td>

                  <td className="px-1 py-0.5">
                    <input type="number" value={row.gstPercent || ''} onChange={(e) => updateRow(ri, 'gstPercent', parseFloat(e.target.value) || 0)} className={`${inputClass} text-right`} />
                  </td>

                  <td className="px-2 py-1.5 text-right text-[var(--color-fg-muted)] overflow-hidden text-ellipsis">{fmt(c.gstValue)}</td>
                  <td className="px-2 py-1.5 text-right font-medium text-[var(--color-fg)] overflow-hidden text-ellipsis">{fmt(c.grandAmount)}</td>

                  <td className="px-1 py-0.5 text-center">
                    <button onClick={() => deleteRow(ri)} className="p-1 rounded hover:bg-red-500/10 text-[var(--color-fg-muted)] hover:text-red-400 transition-colors">
                      <Trash2 size={12} />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>

          <tfoot>
            <tr className="bg-[var(--color-bg-tertiary)]/50 font-semibold">
              <td colSpan={13} className="px-2 py-2 text-right text-[var(--color-fg)]">Total</td>
              <td className="px-2 py-2 text-right text-[var(--color-fg)]">{fmt(totalGrandAmount)}</td>
              <td />
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
