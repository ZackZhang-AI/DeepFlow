"use client";

import { useMemo, useState } from "react";
import { listKnowledgeDocumentChunks } from "@/lib/api";
import type { KnowledgeChunk, Report } from "@/lib/types";

interface SourceEvent {
  data: Record<string, unknown>;
}

const SOURCE_PATTERN = /(?:https?:\/\/[^\s<>"')\]]+|kb:\/\/[A-Za-z0-9_-]+#[A-Za-z0-9_-]+)/g;

function extractSources(value: unknown): string[] {
  const matches = JSON.stringify(value).match(SOURCE_PATTERN) ?? [];
  return matches.map((item) => item.replace(/[.,;]+$/, ""));
}

export function SourceInspector({ events, report }: { events: SourceEvent[]; report: Report | null }) {
  const [copied, setCopied] = useState<string | null>(null);
  const [selectedChunk, setSelectedChunk] = useState<KnowledgeChunk | null>(null);
  const [chunkLoading, setChunkLoading] = useState(false);
  const [chunkError, setChunkError] = useState<string | null>(null);
  const sources = useMemo(
    () => Array.from(new Set([
      ...events.flatMap((event) => extractSources(event.data)),
      ...extractSources(report?.content_markdown ?? ""),
    ])),
    [events, report],
  );

  const copySource = async (source: string) => {
    await navigator.clipboard.writeText(source);
    setCopied(source);
    window.setTimeout(() => setCopied(null), 1500);
  };

  const openKnowledgeSource = async (source: string) => {
    const match = /^kb:\/\/([^#]+)#(.+)$/.exec(source);
    if (!match) return;
    setChunkLoading(true);
    setChunkError(null);
    try {
      const chunks = await listKnowledgeDocumentChunks(match[1]);
      const chunk = chunks.find((item) => item.chunk_id === match[2]);
      if (!chunk) throw new Error("未找到对应知识库片段");
      setSelectedChunk(chunk);
      window.setTimeout(() => {
        document.getElementById("knowledge-source-detail")?.scrollIntoView({
          behavior: "smooth",
          block: "nearest",
        });
      }, 0);
    } catch (reason) {
      setChunkError(reason instanceof Error ? reason.message : "知识库原文加载失败");
    } finally {
      setChunkLoading(false);
    }
  };

  return (
    <section id="source-inspector" className="rounded-xl border border-[var(--border)] bg-white p-4 sm:p-5" aria-labelledby="source-heading">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 id="source-heading" className="text-base font-semibold text-[var(--ink)]">来源检查</h2>
          <p className="mt-1 text-xs text-[var(--muted)]">仅展示任务事件和报告中实际记录的来源。</p>
        </div>
        <span className="shrink-0 text-sm font-semibold text-teal-700">{sources.length}</span>
      </div>

      {sources.length === 0 ? (
        <p className="mt-4 rounded-xl border border-dashed border-[var(--border)] bg-[var(--surface-muted)] px-3 py-6 text-center text-sm text-[var(--muted)]">
          暂无可检查来源，研究执行后会自动显示。
        </p>
      ) : (
        <ol className="mt-4 space-y-2">
          {sources.map((source, index) => {
            const isKnowledge = source.startsWith("kb://");
            return (
              <li key={source} className="flex min-w-0 items-start gap-3 rounded-xl border border-[var(--border)] bg-[var(--surface-muted)] p-3">
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-white text-xs font-semibold text-slate-600">{index + 1}</span>
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-semibold text-slate-700">{isKnowledge ? "知识库片段" : "公开网页"}</p>
                  <p className="mt-1 break-all text-xs leading-5 text-[var(--muted)]">{source}</p>
                </div>
                {isKnowledge ? (
                  <div className="flex shrink-0 items-center gap-1">
                    <button type="button" onClick={() => void openKnowledgeSource(source)} className="rounded-lg px-2 py-1 text-xs font-medium text-teal-700 hover:bg-white">
                      定位原文
                    </button>
                    <button type="button" onClick={() => void copySource(source)} className="rounded-lg px-2 py-1 text-xs text-slate-500 hover:bg-white">
                      {copied === source ? "已复制" : "复制"}
                    </button>
                  </div>
                ) : (
                  <a href={source} target="_blank" rel="noreferrer" className="shrink-0 rounded-lg px-2 py-1 text-xs font-medium text-teal-700 hover:bg-white">
                    打开
                  </a>
                )}
              </li>
            );
          })}
        </ol>
      )}

      {(chunkLoading || chunkError || selectedChunk) && (
        <div id="knowledge-source-detail" className="mt-4 border-t border-[var(--border)] pt-4" aria-live="polite">
          {chunkLoading && <p className="text-sm text-[var(--muted)]">正在加载知识库原文...</p>}
          {chunkError && <p className="text-sm text-red-600">{chunkError}</p>}
          {selectedChunk && !chunkLoading && (
            <article className="rounded-lg border border-teal-200 bg-teal-50/50 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-sm font-semibold text-[var(--ink)]">
                  {selectedChunk.title || selectedChunk.source_name || "知识库原文"}
                </h3>
                <span className="text-xs text-[var(--muted)]">
                  第 {selectedChunk.chunk_index + 1} 段
                  {selectedChunk.page_num ? ` · 第 ${selectedChunk.page_num} 页` : ""}
                </span>
              </div>
              <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-6 text-slate-700">
                {selectedChunk.content || selectedChunk.preview}
              </p>
            </article>
          )}
        </div>
      )}
    </section>
  );
}
