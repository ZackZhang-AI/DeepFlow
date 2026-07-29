"use client";

import { useCallback, useEffect, useState } from "react";
import {
  createKnowledgeDocument,
  deleteKnowledgeDocument,
  listKnowledgeDocumentChunks,
  listKnowledgeDocuments,
  reindexKnowledgeDocument,
  searchKnowledgeDocuments,
  uploadKnowledgeDocument,
} from "@/lib/api";
import { Button, getButtonClasses } from "@/components/ui/Button";
import type { KnowledgeChunk, KnowledgeDocument, KnowledgeDocumentStatus, KnowledgeSearchHit } from "@/lib/types";

const STATUS_META: Record<KnowledgeDocumentStatus, { label: string; className: string }> = {
  pending: { label: "待处理", className: "border-amber-200 bg-amber-50 text-amber-700" },
  processing: { label: "处理中", className: "border-cyan-200 bg-cyan-50 text-cyan-700" },
  ready: { label: "可检索", className: "border-emerald-200 bg-emerald-50 text-emerald-700" },
  failed: { label: "失败", className: "border-red-200 bg-red-50 text-red-600" },
};

function StatusBadge({ status }: { status: KnowledgeDocumentStatus }) {
  const meta = STATUS_META[status] ?? { label: status, className: "border-slate-200 bg-slate-50 text-slate-600" };
  return <span className={`whitespace-nowrap rounded-full border px-2.5 py-1 text-[11px] font-semibold ${meta.className}`}>{meta.label}</span>;
}

function formatScore(value?: number | null) {
  if (typeof value !== "number") return "-";
  return value.toFixed(3);
}

function getDocErrorSummary(doc: KnowledgeDocument) {
  if (doc.status !== "failed") return "";
  return doc.error_message || "文档处理失败，请重建索引或重新上传。";
}

function ChunkDebugCard({ hit }: { hit: KnowledgeSearchHit }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-white p-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-500">
        <span className="font-mono text-slate-600">chunk_id: {hit.chunk_id}</span>
        <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5">{hit.retrieval_mode}</span>
      </div>
      <p className="mt-1 truncate text-[11px] text-slate-500">
        doc_id: {hit.doc_id} · page: {hit.page_num ?? "-"} · chunk: {hit.chunk_index}
      </p>
      <div className="mt-2 grid grid-cols-2 gap-2 text-[11px] text-slate-500 sm:grid-cols-4">
        <span>score {formatScore(hit.score)}</span>
        <span>vector {formatScore(hit.vector_score)}</span>
        <span>keyword {formatScore(hit.keyword_score)}</span>
        <span>rerank {formatScore(hit.rerank_score)}</span>
      </div>
      <p className="mt-2 text-xs font-medium text-slate-700">{hit.title || hit.source_name || "未命名文档"}</p>
      <p className="mt-1 line-clamp-4 text-xs leading-5 text-slate-600">{hit.preview || hit.content}</p>
    </div>
  );
}

function StoredChunkCard({ chunk }: { chunk: KnowledgeChunk }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-white p-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-500">
        <span className="font-mono text-slate-600">chunk_id: {chunk.chunk_id}</span>
        <span>page: {chunk.page_num ?? "-"}</span>
      </div>
      <p className="mt-1 truncate text-[11px] text-slate-500">
        doc_id: {chunk.doc_id} · chunk: {chunk.chunk_index}
      </p>
      <p className="mt-2 line-clamp-4 text-xs leading-5 text-slate-600">{chunk.preview || chunk.content}</p>
    </div>
  );
}

interface KnowledgePanelProps {
  onDocumentsChange?: (documents: KnowledgeDocument[]) => void;
}

export function KnowledgePanel({ onDocumentsChange }: KnowledgePanelProps) {
  const [open, setOpen] = useState(false);
  const [docs, setDocs] = useState<KnowledgeDocument[]>([]);
  const [hits, setHits] = useState<KnowledgeSearchHit[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [selectedChunks, setSelectedChunks] = useState<KnowledgeChunk[]>([]);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [query, setQuery] = useState("");
  const [useRerank, setUseRerank] = useState(false);
  const [busy, setBusy] = useState(false);
  const [searching, setSearching] = useState(false);
  const [loadingChunks, setLoadingChunks] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const documents = await listKnowledgeDocuments();
      setDocs(documents);
      onDocumentsChange?.(documents);
    } catch (e) {
      setError(e instanceof Error ? e.message : "知识库加载失败");
    }
  }, [onDocumentsChange]);

  useEffect(() => {
    const timer = window.setTimeout(() => void refresh(), 0);
    return () => window.clearTimeout(timer);
  }, [refresh]);

  useEffect(() => {
    if (!docs.some((doc) => doc.status === "pending" || doc.status === "processing")) return;
    const timer = window.setInterval(() => void refresh(), 2000);
    return () => window.clearInterval(timer);
  }, [docs, refresh]);

  const toggleOpen = async () => {
    const nextOpen = !open;
    setOpen(nextOpen);
    if (nextOpen) await refresh();
  };

  const addText = async () => {
    if (!title.trim() || !content.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await createKnowledgeDocument(title.trim(), content.trim());
      setTitle("");
      setContent("");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setBusy(false);
    }
  };

  const uploadFile = async (file: File | null) => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      await uploadKnowledgeDocument(file);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "上传失败");
    } finally {
      setBusy(false);
    }
  };

  const runSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    setError(null);
    try {
      setHits(await searchKnowledgeDocuments(query.trim(), 8, useRerank));
    } catch (e) {
      setError(e instanceof Error ? e.message : "检索失败");
    } finally {
      setSearching(false);
    }
  };

  const viewChunks = async (docId: string) => {
    setLoadingChunks(true);
    setError(null);
    setSelectedDocId(docId);
    try {
      setSelectedChunks(await listKnowledgeDocumentChunks(docId));
    } catch (e) {
      setSelectedChunks([]);
      setError(e instanceof Error ? e.message : "加载文档 chunks 失败");
    } finally {
      setLoadingChunks(false);
    }
  };

  const remove = async (docId: string) => {
    setBusy(true);
    try {
      await deleteKnowledgeDocument(docId);
      setHits((items) => items.filter((hit) => hit.doc_id !== docId));
      if (selectedDocId === docId) {
        setSelectedDocId(null);
        setSelectedChunks([]);
      }
      await refresh();
    } finally {
      setBusy(false);
    }
  };

  const reindex = async (docId: string) => {
    setBusy(true);
    setError(null);
    try {
      await reindexKnowledgeDocument(docId);
      await refresh();
      if (selectedDocId === docId) await viewChunks(docId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "重建索引失败");
    } finally {
      setBusy(false);
    }
  };

  const ready = docs.filter((doc) => doc.status === "ready").length;
  const selectedDoc = docs.find((doc) => doc.doc_id === selectedDocId) ?? null;

  return (
    <section className="space-y-4 rounded-2xl border border-[var(--border)] bg-white p-4 sm:p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-[var(--ink)]">私域知识库</h2>
          <p className="mt-1 text-xs text-slate-500">
            已收录 {docs.length} 份资料，{ready} 份可检索。研究时会自动召回相关片段。
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={toggleOpen}>
          {open ? "收起" : "管理知识库"}
        </Button>
      </div>

      {open && (
        <div className="space-y-4">
          {error && <div className="rounded-2xl border border-red-200 bg-red-50 p-3 text-xs text-red-600">{error}</div>}

          <div className="grid gap-3 md:grid-cols-[1fr_auto] md:items-start">
            <div className="space-y-2">
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="资料标题"
                className="min-h-11 w-full rounded-xl border border-[var(--border)] bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-[var(--accent)] focus:ring-4 focus:ring-[var(--accent-soft)]"
              />
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="粘贴资料正文，保存后会分块并生成索引"
                rows={4}
                className="w-full resize-y rounded-xl border border-[var(--border)] bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-[var(--accent)] focus:ring-4 focus:ring-[var(--accent-soft)]"
              />
            </div>
            <div className="flex gap-2 md:flex-col">
              <Button
                variant="primary"
                size="sm"
                onClick={addText}
                disabled={busy || !title.trim() || !content.trim()}
              >
                {busy ? "处理中..." : "保存文本"}
              </Button>
              <label className={getButtonClasses({ variant: "secondary", size: "sm", className: "cursor-pointer" })}>
                上传文件
                <input
                  type="file"
                  accept=".txt,.md,.markdown,.pdf"
                  className="hidden"
                  onChange={(e) => void uploadFile(e.target.files?.[0] ?? null)}
                />
              </label>
            </div>
          </div>

          <div className="space-y-3 rounded-xl border border-[var(--border)] bg-[var(--surface-muted)] p-3">
            <div className="flex flex-col gap-2 sm:flex-row">
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void runSearch();
                }}
                placeholder="输入问题，测试知识库召回"
                className="min-h-11 min-w-0 flex-1 rounded-xl border border-[var(--border)] bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-[var(--accent)] focus:ring-4 focus:ring-[var(--accent-soft)]"
              />
              <label className="flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-2 py-2 text-[11px] text-slate-500">
                <input type="checkbox" checked={useRerank} onChange={(e) => setUseRerank(e.target.checked)} />
                rerank
              </label>
              <Button
                variant="secondary"
                size="sm"
                onClick={runSearch}
                disabled={searching || !query.trim()}
              >
                {searching ? "检索中..." : "检索"}
              </Button>
            </div>
            <div className="rounded-2xl border border-dashed border-slate-200 bg-white/70 p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <h3 className="text-xs font-semibold text-slate-800">召回调试面板</h3>
                <span className="text-[11px] text-slate-500">{hits.length} 个 chunk</span>
              </div>
              {hits.length === 0 ? (
                <p className="text-xs text-slate-500">检索后会显示 chunk_id、doc_id、页码、score、vector、keyword、rerank 和 preview。</p>
              ) : (
                <div className="space-y-2">
                  {hits.map((hit) => (
                    <ChunkDebugCard key={hit.chunk_id} hit={hit} />
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="grid gap-3 lg:grid-cols-[1fr_1fr]">
            <div className="space-y-2">
              <h3 className="text-xs font-semibold text-slate-800">文档状态</h3>
              {docs.length === 0 ? (
                <p className="rounded-2xl border border-dashed border-slate-200 bg-white/60 p-4 text-xs text-slate-500">还没有知识库资料。</p>
              ) : (
                docs.map((doc) => (
                  <div key={doc.doc_id} className="rounded-2xl border border-slate-200 bg-white/75 p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-slate-900">{doc.title}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          {doc.source_type} · {doc.chunk_count} chunks · {doc.content_length} 字
                        </p>
                        {getDocErrorSummary(doc) && <p className="mt-1 line-clamp-2 text-xs text-red-600">{getDocErrorSummary(doc)}</p>}
                      </div>
                      <StatusBadge status={doc.status} />
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => void viewChunks(doc.doc_id)}
                        disabled={loadingChunks}
                      >
                        查看 chunks
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => void reindex(doc.doc_id)}
                        disabled={busy}
                      >
                        重建
                      </Button>
                      <Button
                        variant="danger"
                        size="sm"
                        onClick={() => void remove(doc.doc_id)}
                        disabled={busy}
                      >
                        删除
                      </Button>
                    </div>
                  </div>
                ))
              )}
            </div>

            <div className="space-y-2">
              <h3 className="text-xs font-semibold text-slate-800">文档 chunks</h3>
              {!selectedDoc ? (
                <p className="rounded-2xl border border-dashed border-slate-200 bg-white/60 p-4 text-xs text-slate-500">选择文档后查看已入库的 chunks。</p>
              ) : (
                <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-3">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <p className="truncate text-xs font-semibold text-slate-800">{selectedDoc.title}</p>
                    <span className="text-[11px] text-slate-500">{selectedChunks.length} chunks</span>
                  </div>
                  {loadingChunks ? (
                    <p className="text-xs text-slate-500">chunks 加载中...</p>
                  ) : selectedChunks.length === 0 ? (
                    <p className="text-xs text-slate-500">该文档暂无 chunks，可能仍在处理或索引失败。</p>
                  ) : (
                    <div className="max-h-96 space-y-2 overflow-y-auto pr-1">
                      {selectedChunks.map((chunk) => (
                        <StoredChunkCard key={chunk.chunk_id} chunk={chunk} />
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
