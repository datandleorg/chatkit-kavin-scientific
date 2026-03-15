import { useEffect, useState } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import {
  listKnowledgeBases,
  checkKnowledgeBase,
  createKnowledgeBase,
  getKbDocuments,
  ingestKbDocuments,
  removeKbDocuments,
  deleteKnowledgeBase,
  type KnowledgeBaseItem,
  type KbDocumentItem,
  type IngestProgressEvent,
} from '../lib/api';
import { Database, Plus, Trash2, Upload, FileText, Loader2, ArrowLeft, X } from 'lucide-react';

const ACCEPTED_INGEST = '.pdf,.xlsx,.xls';

export default function KnowledgeBasePage() {
  const { kbId } = useParams<{ kbId: string }>();
  const navigate = useNavigate();
  const [list, setList] = useState<KnowledgeBaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [createName, setCreateName] = useState('');
  const [createError, setCreateError] = useState<string | null>(null);
  const [duplicateChecked, setDuplicateChecked] = useState<string | null>(null);
  const [documents, setDocuments] = useState<KbDocumentItem[]>([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [ingestFiles, setIngestFiles] = useState<File[]>([]);
  const [ingestProgress, setIngestProgress] = useState<IngestProgressEvent | null>(null);
  const [ingestError, setIngestError] = useState<string | null>(null);
  const [removeDocName, setRemoveDocName] = useState<string | null>(null);

  const selectedKb = list.find((kb) => kb.id === kbId);

  useEffect(() => {
    let cancelled = false;
    listKnowledgeBases()
      .then((data) => {
        if (!cancelled) setList(data);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!kbId) {
      setDocuments([]);
      return;
    }
    setDocsLoading(true);
    getKbDocuments(kbId)
      .then(setDocuments)
      .catch(() => setDocuments([]))
      .finally(() => setDocsLoading(false));
  }, [kbId]);

  const handleCheckDuplicate = async () => {
    const name = createName.trim();
    if (!name) return;
    setCreateError(null);
    setDuplicateChecked(null);
    try {
      const { exists } = await checkKnowledgeBase(name);
      setDuplicateChecked(exists ? 'Vendor already exists' : 'Name available');
    } catch {
      setDuplicateChecked('Check failed');
    }
  };

  const handleCreate = async () => {
    const name = createName.trim();
    if (!name) return;
    setCreateError(null);
    try {
      const created = await createKnowledgeBase(name);
      setList((prev) => [...prev, created]);
      setCreateName('');
      setDuplicateChecked(null);
      navigate(`/knowledge-base/${created.id}`);
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : 'Create failed');
    }
  };

  const handleDeleteKb = async (id: string) => {
    if (!confirm('Delete this knowledge base and all its documents?')) return;
    try {
      await deleteKnowledgeBase(id);
      setList((prev) => prev.filter((kb) => kb.id !== id));
      if (kbId === id) navigate('/knowledge-base');
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Delete failed');
    }
  };

  const handleIngest = async () => {
    if (!kbId || ingestFiles.length === 0) return;
    setIngestError(null);
    setIngestProgress({ stage: 'chunking' });
    try {
      await ingestKbDocuments(kbId, ingestFiles, (event) => setIngestProgress(event));
      setIngestProgress(null);
      setIngestFiles([]);
      getKbDocuments(kbId).then(setDocuments);
    } catch (e) {
      setIngestProgress(null);
      setIngestError(e instanceof Error ? e.message : 'Ingest failed');
    }
  };

  const handleRemoveDoc = async (filename: string) => {
    if (!kbId) return;
    setRemoveDocName(filename);
    try {
      await removeKbDocuments(kbId, [filename]);
      setDocuments((prev) => prev.filter((d) => d.source_filename !== filename));
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Remove failed');
    } finally {
      setRemoveDocName(null);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--color-bg)] text-[var(--color-fg)]">
      <header className="sticky top-0 z-10 border-b border-[var(--color-border)] bg-[var(--color-bg)]/95 backdrop-blur">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Database className="w-6 h-6 text-[var(--color-accent)]" />
            <h1 className="text-lg font-semibold">Knowledge Base</h1>
          </div>
          <div className="flex items-center gap-2">
            <Link
              to="/knowledge-base"
              className="flex items-center gap-2 px-3 py-2 rounded-lg text-[var(--color-fg-muted)] hover:bg-[var(--color-bg-secondary)] hover:text-[var(--color-fg)] transition-colors"
            >
              <Database className="w-4 h-4" />
              All KBs
            </Link>
            <Link
              to="/"
              className="flex items-center gap-2 px-3 py-2 rounded-lg text-[var(--color-fg-muted)] hover:bg-[var(--color-bg-secondary)] hover:text-[var(--color-fg)] transition-colors"
            >
              Chat
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-8">
        {!kbId ? (
          <>
            <section className="mb-8">
              <h2 className="text-sm font-medium text-[var(--color-fg-muted)] mb-3">Create new</h2>
              <div className="flex flex-wrap items-end gap-3">
                <div>
                  <label className="block text-xs text-[var(--color-fg-muted)] mb-1">Vendor name</label>
                  <input
                    type="text"
                    value={createName}
                    onChange={(e) => {
                      setCreateName(e.target.value);
                      setDuplicateChecked(null);
                      setCreateError(null);
                    }}
                    onBlur={handleCheckDuplicate}
                    placeholder="e.g. Acme Chemicals"
                    className="w-56 px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] text-[var(--color-fg)] placeholder:text-[var(--color-fg-muted)]"
                  />
                </div>
                <button
                  type="button"
                  onClick={handleCheckDuplicate}
                  className="px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] text-[var(--color-fg-muted)] hover:text-[var(--color-fg)]"
                >
                  Check duplicate
                </button>
                <button
                  type="button"
                  onClick={handleCreate}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90"
                >
                  <Plus size={16} />
                  Create
                </button>
              </div>
              {duplicateChecked && (
                <p className={`mt-2 text-sm ${duplicateChecked === 'Name available' ? 'text-green-600' : 'text-amber-600'}`}>
                  {duplicateChecked}
                </p>
              )}
              {createError && <p className="mt-2 text-sm text-red-500">{createError}</p>}
            </section>

            <section>
              <h2 className="text-sm font-medium text-[var(--color-fg-muted)] mb-3">Knowledge bases</h2>
              {loading ? (
                <p className="text-[var(--color-fg-muted)]">Loading…</p>
              ) : list.length === 0 ? (
                <p className="text-[var(--color-fg-muted)]">No knowledge bases yet. Create one above.</p>
              ) : (
                <ul className="space-y-2">
                  {list.map((kb) => (
                    <li
                      key={kb.id}
                      className="flex items-center justify-between rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-4 py-3"
                    >
                      <Link to={`/knowledge-base/${kb.id}`} className="font-medium text-[var(--color-fg)] hover:underline">
                        {kb.vendor_name}
                      </Link>
                      <div className="flex items-center gap-2">
                        <Link
                          to={`/knowledge-base/${kb.id}`}
                          className="px-3 py-1.5 rounded-lg border border-[var(--color-border)] text-sm hover:bg-[var(--color-bg)]"
                        >
                          Open
                        </Link>
                        <button
                          type="button"
                          onClick={() => handleDeleteKb(kb.id)}
                          className="p-1.5 rounded text-red-500 hover:bg-red-500/10"
                          title="Delete"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </>
        ) : (
          <>
            <div className="mb-6 flex items-center gap-3">
              <Link
                to="/knowledge-base"
                className="flex items-center gap-2 text-[var(--color-fg-muted)] hover:text-[var(--color-fg)]"
              >
                <ArrowLeft size={18} />
                Back
              </Link>
              <h2 className="text-xl font-semibold">{selectedKb?.vendor_name ?? 'Knowledge base'}</h2>
            </div>

            <section className="mb-8">
              <h3 className="text-sm font-medium text-[var(--color-fg-muted)] mb-3">Add documents (PDF, Excel)</h3>
              <div className="flex flex-wrap items-center gap-3">
                <input
                  type="file"
                  accept={ACCEPTED_INGEST}
                  multiple
                  onChange={(e) => setIngestFiles(e.target.files ? Array.from(e.target.files) : [])}
                  className="text-sm text-[var(--color-fg)] file:mr-2 file:py-2 file:px-3 file:rounded file:border file:border-[var(--color-border)] file:bg-[var(--color-bg-secondary)]"
                />
                <button
                  type="button"
                  onClick={handleIngest}
                  disabled={ingestFiles.length === 0 || !!ingestProgress}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--color-accent)] text-white disabled:opacity-50"
                >
                  {ingestProgress ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      {ingestProgress.stage === 'chunking' && (ingestProgress.file ? `Chunking ${ingestProgress.file}…` : 'Chunking…')}
                      {ingestProgress.stage === 'chunking_done' && 'Chunked'}
                      {ingestProgress.stage === 'embedding' &&
                        `Embedding ${ingestProgress.current ?? 0}/${ingestProgress.total ?? 0}`}
                      {ingestProgress.stage === 'done' && 'Done'}
                    </>
                  ) : (
                    <>
                      <Upload size={16} />
                      Add documents
                    </>
                  )}
                </button>
              </div>
              {ingestFiles.length > 0 && !ingestProgress && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {ingestFiles.map((f) => (
                    <span
                      key={f.name}
                      className="inline-flex items-center gap-1 px-2 py-1 rounded bg-[var(--color-bg-secondary)] text-sm"
                    >
                      {f.name}
                      <button type="button" onClick={() => setIngestFiles((prev) => prev.filter((x) => x !== f))}>
                        <X size={14} />
                      </button>
                    </span>
                  ))}
                </div>
              )}
              {ingestError && <p className="mt-2 text-sm text-red-500">{ingestError}</p>}
            </section>

            <section>
              <h3 className="text-sm font-medium text-[var(--color-fg-muted)] mb-3">Documents in this KB</h3>
              {docsLoading ? (
                <p className="text-[var(--color-fg-muted)]">Loading…</p>
              ) : documents.length === 0 ? (
                <p className="text-[var(--color-fg-muted)]">No documents yet. Add PDF or Excel files above.</p>
              ) : (
                <ul className="space-y-2">
                  {documents.map((doc) => (
                    <li
                      key={doc.source_filename}
                      className="flex items-center justify-between rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] px-4 py-3"
                    >
                      <div className="flex items-center gap-2">
                        <FileText size={16} className="text-[var(--color-fg-muted)]" />
                        <span>{doc.source_filename}</span>
                        <span className="text-xs text-[var(--color-fg-muted)]">({doc.chunk_count} chunks)</span>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleRemoveDoc(doc.source_filename)}
                        disabled={removeDocName === doc.source_filename}
                        className="flex items-center gap-1 px-2 py-1 rounded text-red-500 hover:bg-red-500/10 disabled:opacity-50"
                      >
                        {removeDocName === doc.source_filename ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                        Remove
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </>
        )}
      </main>
    </div>
  );
}
