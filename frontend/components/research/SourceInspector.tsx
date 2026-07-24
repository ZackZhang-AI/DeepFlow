"use client";

import { useMemo, useState } from "react";
import type { Report } from "@/lib/types";

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
                  <button type="button" onClick={() => void copySource(source)} className="shrink-0 rounded-lg px-2 py-1 text-xs font-medium text-teal-700 hover:bg-white">
                    {copied === source ? "已复制" : "复制定位"}
                  </button>
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
    </section>
  );
}
