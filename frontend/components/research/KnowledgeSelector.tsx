"use client";

import type { KnowledgeDocument } from "@/lib/types";

interface KnowledgeSelectorProps {
  enabled: boolean;
  documents: KnowledgeDocument[];
  selectedDocumentIds: string[];
  disabled?: boolean;
  onEnabledChange: (enabled: boolean) => void;
  onSelectionChange: (documentIds: string[]) => void;
}

export function KnowledgeSelector({
  enabled,
  documents,
  selectedDocumentIds,
  disabled = false,
  onEnabledChange,
  onSelectionChange,
}: KnowledgeSelectorProps) {
  const readyDocuments = documents.filter((document) => document.status === "ready");
  const selected = new Set(selectedDocumentIds);

  const toggleDocument = (docId: string) => {
    const next = new Set(selected);
    if (next.has(docId)) next.delete(docId);
    else next.add(docId);
    onSelectionChange(Array.from(next));
  };

  return (
    <fieldset className="rounded-xl border border-[var(--border)] bg-white p-3" disabled={disabled}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <label className="flex min-h-11 cursor-pointer items-center gap-3">
          <input
            type="checkbox"
            checked={enabled}
            disabled={disabled || readyDocuments.length === 0}
            onChange={(event) => {
              const nextEnabled = event.target.checked;
              onEnabledChange(nextEnabled);
              if (nextEnabled && selectedDocumentIds.length === 0) {
                onSelectionChange(readyDocuments.map((document) => document.doc_id));
              }
            }}
            className="h-4 w-4 accent-teal-700"
          />
          <span>
            <span className="block text-sm font-semibold text-[var(--ink)]">使用私域知识库</span>
            <span className="mt-0.5 block text-xs text-[var(--muted)]">
              {readyDocuments.length > 0
                ? `${readyDocuments.length} 份资料可用，仅在所选资料中召回`
                : "暂无可检索资料，请先在下方上传并完成索引"}
            </span>
          </span>
        </label>
        <a
          href="#private-knowledge"
          className="min-h-11 rounded-lg px-2 py-3 text-xs font-semibold text-teal-700 hover:bg-teal-50 hover:text-teal-900"
        >
          管理资料
        </a>
      </div>

      {enabled && readyDocuments.length > 0 && (
        <div className="mt-3 grid gap-2 border-t border-[var(--border)] pt-3 sm:grid-cols-2">
          {readyDocuments.map((document) => (
            <label
              key={document.doc_id}
              className="flex min-h-11 cursor-pointer items-center gap-2 rounded-lg border border-[var(--border)] px-3 py-2 text-xs text-slate-700 hover:border-teal-300 hover:bg-teal-50/50"
            >
              <input
                type="checkbox"
                checked={selected.has(document.doc_id)}
                onChange={() => toggleDocument(document.doc_id)}
                className="h-4 w-4 shrink-0 accent-teal-700"
              />
              <span className="min-w-0">
                <span className="block truncate font-semibold">{document.title}</span>
                <span className="mt-0.5 block text-[11px] text-slate-500">
                  {document.chunk_count} chunks
                </span>
              </span>
            </label>
          ))}
        </div>
      )}
    </fieldset>
  );
}
