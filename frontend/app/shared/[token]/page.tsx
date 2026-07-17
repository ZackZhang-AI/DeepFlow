"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { API_BASE } from "@/lib/api";

interface SharedPayload {
  readonly: boolean;
  share: {
    share_id: string;
    token: string;
    user_id?: string;
    resource_type: "task_report" | "artifact" | string;
    resource_id: string;
    created_at?: string;
  };
  resource: Record<string, unknown>;
}

function getString(value: unknown, fallback = "") {
  return typeof value === "string" ? value : fallback;
}

function getNumber(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function formatDate(value?: string) {
  if (!value) return "未知时间";
  return new Date(value).toLocaleString("zh-CN", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function renderMetadata(raw: unknown) {
  if (!raw || typeof raw !== "string") return null;
  try {
    const parsed = JSON.parse(raw) as unknown;
    return JSON.stringify(parsed, null, 2);
  } catch {
    return raw;
  }
}

export default function SharedPage() {
  const params = useParams<{ token: string }>();
  const token = params.token;
  const [payload, setPayload] = useState<SharedPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadSharedResource() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${API_BASE}/api/shared/${encodeURIComponent(token)}`, {
          signal: controller.signal,
          cache: "no-store",
        });
        if (!res.ok) {
          const text = await res.text();
          throw new Error(text || "分享内容不存在或已失效");
        }
        setPayload((await res.json()) as SharedPayload);
      } catch (err) {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : "分享内容加载失败");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }

    void loadSharedResource();
    return () => controller.abort();
  }, [token]);

  const viewModel = useMemo(() => {
    if (!payload) return null;
    const resource = payload.resource;
    if (payload.share.resource_type === "task_report") {
      return {
        kind: "研究报告",
        title: getString(resource.topic, "DeepFlow 研究报告"),
        subtitle: `任务 ID：${getString(resource.task_id)}`,
        body: getString(resource.report_markdown, "报告内容为空"),
        updatedAt: getString(resource.updated_at),
        metrics: [
          { label: "来源", value: String(getNumber(resource.sources_count)) },
          { label: "Token", value: String(getNumber(resource.tokens_used)) },
          { label: "耗时", value: `${getNumber(resource.elapsed_seconds).toFixed(1)}s` },
        ],
        metadata: null,
      };
    }

    return {
      kind: "成果物",
      title: getString(resource.title, "DeepFlow 成果物"),
      subtitle: `${getString(resource.artifact_type, "artifact")} · ${getString(resource.artifact_id)}`,
      body: getString(resource.content, "该成果物没有可直接预览的文本内容。"),
      updatedAt: getString(resource.created_at),
      metrics: [
        { label: "任务", value: getString(resource.task_id, "-") },
        { label: "类型", value: getString(resource.artifact_type, "-") },
      ],
      metadata: renderMetadata(resource.metadata_json),
    };
  }, [payload]);

  return (
    <main className="min-h-screen bg-[#f7f8f4] text-slate-950">
      <div className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-5 sm:px-6 lg:px-8">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <Link href="/" className="flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-xl border border-cyan-500/20 bg-cyan-50 text-sm font-black text-cyan-700">
              D
            </span>
            <span className="text-lg font-semibold tracking-tight">DeepFlow</span>
          </Link>
          <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-600">只读分享</span>
        </header>

        {loading ? (
          <section className="grid min-h-[520px] place-items-center rounded-2xl border border-slate-200 bg-white/80">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent" />
          </section>
        ) : error ? (
          <section className="rounded-2xl border border-red-200 bg-red-50 p-6 text-red-700">
            <h1 className="text-xl font-semibold">分享内容无法访问</h1>
            <p className="mt-2 text-sm leading-6">{error}</p>
          </section>
        ) : viewModel ? (
          <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200 pb-5">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-700">{viewModel.kind}</p>
                <h1 className="mt-2 text-3xl font-semibold tracking-tight">{viewModel.title}</h1>
                <p className="mt-2 font-mono text-xs text-slate-400">{viewModel.subtitle}</p>
                <p className="mt-2 text-sm text-slate-500">更新时间 {formatDate(viewModel.updatedAt)}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {viewModel.metrics.map((metric) => (
                  <div key={`${metric.label}-${metric.value}`} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
                    <div className="text-xs text-slate-500">{metric.label}</div>
                    <div className="mt-1 font-semibold text-slate-900">{metric.value}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
              <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-7 text-slate-800">{viewModel.body}</pre>
            </div>

            {viewModel.metadata && (
              <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-950 p-4">
                <div className="mb-2 text-xs font-semibold text-slate-400">Metadata</div>
                <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words font-mono text-xs leading-5 text-slate-100">{viewModel.metadata}</pre>
              </div>
            )}
          </article>
        ) : null}
      </div>
    </main>
  );
}
