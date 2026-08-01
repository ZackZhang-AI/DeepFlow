"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { DemoBadge } from "@/components/ui/DemoBadge";
import { Button } from "@/components/ui/Button";
import { API_BASE } from "@/lib/api";
import type { SharedSource } from "@/lib/types";

interface SharedPayload {
  readonly: boolean;
  share: {
    share_id: string;
    token: string;
    resource_type: "task_report" | "artifact" | string;
    resource_id: string;
    created_at?: string;
    is_demo?: boolean;
  };
  resource: Record<string, unknown>;
}

interface SharedViewModel {
  kind: string;
  title: string;
  subtitle: string;
  body: string;
  updatedAt: string;
  sources: SharedSource[];
  sourcesCount: number;
  isDemo: boolean;
  tokens: number;
  elapsedSeconds: number;
  metadata: string | null;
}

const COLD_START_TIMEOUT_MS = 90_000;
const RETRY_DELAYS_MS = [1_000, 2_000, 4_000, 8_000, 15_000, 20_000, 20_000, 20_000];
const RETRYABLE_STATUSES = new Set([502, 503, 504]);

class SharedRequestError extends Error {
  constructor(message: string, readonly retryable: boolean) {
    super(message);
    this.name = "SharedRequestError";
  }
}

function getString(value: unknown, fallback = "") {
  return typeof value === "string" ? value : fallback;
}

function getNumber(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function getBoolean(value: unknown) {
  return value === true;
}

function formatDate(value?: string) {
  if (!value) return "未知时间";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function formatDuration(seconds: number) {
  if (seconds < 60) return `${Math.round(seconds)} 秒`;
  const minutes = Math.floor(seconds / 60);
  const remainder = Math.round(seconds % 60);
  return remainder ? `${minutes} 分 ${remainder} 秒` : `${minutes} 分钟`;
}

function renderMetadata(raw: unknown) {
  if (!raw || typeof raw !== "string") return null;
  try {
    return JSON.stringify(JSON.parse(raw) as unknown, null, 2);
  } catch {
    return raw;
  }
}

function normalizeSources(raw: unknown): SharedSource[] {
  if (!Array.isArray(raw)) return [];
  return raw.flatMap((item, index) => {
    if (typeof item === "string") {
      return /^https?:\/\//i.test(item)
        ? [{ title: `来源 ${index + 1}`, url: item, source_type: "web" }]
        : [];
    }
    if (!item || typeof item !== "object") return [];
    const source = item as Record<string, unknown>;
    const url = getString(source.url, getString(source.href));
    if (!/^https?:\/\//i.test(url)) return [];
    return [{
      title: getString(source.title, getString(source.name, `来源 ${index + 1}`)),
      url,
      source_type: getString(source.source_type, getString(source.type, "web")),
    }];
  });
}

async function responseMessage(response: Response) {
  try {
    const payload = (await response.json()) as { detail?: unknown; message?: unknown };
    return getString(payload.detail, getString(payload.message));
  } catch {
    return "";
  }
}

function sleep(ms: number, signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const handleAbort = () => {
      window.clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    };
    const timer = window.setTimeout(() => {
      signal.removeEventListener("abort", handleAbort);
      resolve();
    }, ms);
    signal.addEventListener("abort", handleAbort, { once: true });
  });
}

export default function SharedPage() {
  const params = useParams<{ token: string }>();
  const token = params.token;
  const [payload, setPayload] = useState<SharedPayload | null>(null);
  const [state, setState] = useState<"loading" | "waking" | "ready" | "failed">("loading");
  const [attempt, setAttempt] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  const loadSharedResource = useCallback(async (signal: AbortSignal) => {
    const deadline = Date.now() + COLD_START_TIMEOUT_MS;
    let retryIndex = 0;

    while (!signal.aborted) {
      setAttempt(retryIndex + 1);
      try {
        const remaining = deadline - Date.now();
        if (remaining <= 0) throw new SharedRequestError("演示服务在 90 秒内未能恢复，请稍后手动重试。", false);

        const requestController = new AbortController();
        const abortRequest = () => requestController.abort();
        signal.addEventListener("abort", abortRequest, { once: true });
        const timeout = window.setTimeout(() => requestController.abort(), remaining);
        let response: Response;
        try {
          response = await fetch(`${API_BASE}/api/shared/${encodeURIComponent(token)}`, {
            signal: requestController.signal,
            cache: "no-store",
          });
        } finally {
          window.clearTimeout(timeout);
          signal.removeEventListener("abort", abortRequest);
        }

        if (!response.ok) {
          const message = await responseMessage(response);
          if (RETRYABLE_STATUSES.has(response.status)) {
            throw new SharedRequestError(message || "演示服务正在启动", true);
          }
          throw new SharedRequestError(
            message || (response.status === 404 || response.status === 410 ? "分享内容不存在或已失效。" : "分享内容暂时无法访问。"),
            false,
          );
        }

        setPayload((await response.json()) as SharedPayload);
        setState("ready");
        setError(null);
        return;
      } catch (caught) {
        if (signal.aborted) return;
        const requestError = caught instanceof SharedRequestError
          ? caught
          : new SharedRequestError("网络暂时不可用，正在尝试连接演示服务。", true);
        if (!requestError.retryable || Date.now() >= deadline || retryIndex >= RETRY_DELAYS_MS.length) {
          setState("failed");
          setError(requestError.retryable ? "演示服务在 90 秒内未能恢复，请稍后手动重试。" : requestError.message);
          return;
        }

        setState("waking");
        const delay = Math.min(RETRY_DELAYS_MS[retryIndex], Math.max(0, deadline - Date.now()));
        retryIndex += 1;
        try {
          await sleep(delay, signal);
        } catch {
          return;
        }
      }
    }
  }, [token]);

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => {
      setPayload(null);
      setState("loading");
      setError(null);
      void loadSharedResource(controller.signal);
    });
    return () => controller.abort();
  }, [loadSharedResource, retryKey]);

  const viewModel = useMemo<SharedViewModel | null>(() => {
    if (!payload) return null;
    const resource = payload.resource;
    const isDemo = getBoolean(resource.is_demo) || getBoolean(payload.share.is_demo);
    if (payload.share.resource_type === "task_report") {
      const sources = normalizeSources(resource.sources);
      return {
        kind: "研究报告",
        title: getString(resource.topic, getString(resource.title, "DeepFlow 研究报告")),
        subtitle: `任务 ID：${getString(resource.task_id, payload.share.resource_id)}`,
        body: getString(resource.report_markdown, getString(resource.content_markdown, "报告内容为空")),
        updatedAt: getString(resource.updated_at, payload.share.created_at),
        sources,
        sourcesCount: Math.max(sources.length, getNumber(resource.sources_count)),
        isDemo,
        tokens: getNumber(resource.tokens_used),
        elapsedSeconds: getNumber(resource.elapsed_seconds),
        metadata: null,
      };
    }

    const sources = normalizeSources(resource.sources);
    return {
      kind: "成果物",
      title: getString(resource.title, "DeepFlow 成果物"),
      subtitle: `${getString(resource.artifact_type, "artifact")} · ${getString(resource.artifact_id, payload.share.resource_id)}`,
      body: getString(resource.content, "该成果物没有可直接预览的文本内容。"),
      updatedAt: getString(resource.created_at, payload.share.created_at),
      sources,
      sourcesCount: sources.length,
      isDemo,
      tokens: getNumber(resource.tokens_used),
      elapsedSeconds: getNumber(resource.elapsed_seconds),
      metadata: renderMetadata(resource.metadata_json),
    };
  }, [payload]);

  return (
    <main className="min-h-[100dvh] overflow-x-hidden bg-[var(--background)] text-[var(--ink)]">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-5 px-4 py-5 sm:px-6 sm:py-8 lg:px-8">
        <header className="flex items-center justify-between gap-3 border-b border-[var(--border)] pb-4">
          <div className="flex min-w-0 items-center gap-2">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-[var(--ink)] text-sm font-bold text-white">D</span>
            <span className="truncate text-base font-semibold">DeepFlow</span>
          </div>
          <span className="shrink-0 rounded-full border border-[var(--border)] bg-white px-3 py-1 text-xs font-semibold text-[var(--muted)]">只读报告</span>
        </header>

        {state === "loading" && (
          <section className="grid min-h-[520px] place-items-center rounded-2xl border border-[var(--border)] bg-white p-6 text-center" aria-live="polite">
            <div>
              <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-[var(--accent)] border-t-transparent" />
              <p className="mt-4 text-sm font-medium">正在加载示例研究</p>
            </div>
          </section>
        )}

        {state === "waking" && (
          <section className="grid min-h-[520px] place-items-center rounded-2xl border border-teal-200 bg-white p-6 text-center" aria-live="polite">
            <div className="max-w-md">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-teal-50">
                <span className="h-3 w-3 animate-pulse rounded-full bg-[var(--accent)]" />
              </div>
              <h1 className="mt-5 text-xl font-semibold">正在唤醒演示服务</h1>
              <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
                免费服务休眠后需要一些时间恢复，页面会自动重试，无需刷新。
              </p>
              <p className="mt-4 text-xs text-[var(--muted)]">第 {attempt} 次连接 · 最长等待 90 秒</p>
            </div>
          </section>
        )}

        {state === "failed" && (
          <section className="grid min-h-[420px] place-items-center rounded-2xl border border-red-200 bg-white p-6 text-center" role="alert">
            <div className="max-w-md">
              <p className="text-xs font-semibold text-red-600">加载未完成</p>
              <h1 className="mt-2 text-xl font-semibold">示例研究暂时无法访问</h1>
              <p className="mt-3 text-sm leading-6 text-[var(--muted)]">{error}</p>
              <Button className="mt-5" variant="secondary" onClick={() => setRetryKey((value) => value + 1)}>
                手动重试
              </Button>
            </div>
          </section>
        )}

        {state === "ready" && viewModel && (
          <article className="min-w-0 rounded-2xl border border-[var(--border)] bg-white p-4 shadow-[0_12px_32px_rgba(23,32,31,0.05)] sm:p-7">
            <div className="border-b border-[var(--border)] pb-6">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-semibold text-teal-700">{viewModel.kind}</span>
                {viewModel.isDemo && <DemoBadge />}
                <span className="rounded-full border border-[var(--border)] bg-[var(--surface-muted)] px-2.5 py-1 text-xs font-semibold text-[var(--muted)]">只读</span>
              </div>
              <h1 className="mt-4 break-words text-2xl font-semibold leading-tight sm:text-3xl">{viewModel.title}</h1>
              <p className="mt-2 break-all font-mono text-xs text-[var(--muted)]">{viewModel.subtitle}</p>

              <dl className="mt-6 grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--border)] sm:grid-cols-4">
                <Metric label="来源" value={`${viewModel.sourcesCount} 个`} />
                <Metric label="Token" value={viewModel.tokens.toLocaleString("zh-CN")} />
                <Metric label="耗时" value={formatDuration(viewModel.elapsedSeconds)} />
                <Metric label="更新时间" value={formatDate(viewModel.updatedAt)} compact />
              </dl>
            </div>

            <div className="mt-7 min-w-0 overflow-hidden text-slate-700">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  h1: ({ children }) => <h1 className="mb-5 mt-8 break-words text-2xl font-semibold leading-tight text-[var(--ink)] first:mt-0">{children}</h1>,
                  h2: ({ children }) => <h2 className="mb-4 mt-8 break-words border-b border-[var(--border)] pb-2 text-xl font-semibold leading-snug text-[var(--ink)]">{children}</h2>,
                  h3: ({ children }) => <h3 className="mb-3 mt-6 break-words text-lg font-semibold leading-snug text-[var(--ink)]">{children}</h3>,
                  p: ({ children }) => <p className="my-4 break-words text-sm leading-8 text-slate-700 sm:text-base">{children}</p>,
                  ul: ({ children }) => <ul className="my-4 list-disc space-y-2 pl-6 text-sm leading-7 text-slate-700 sm:text-base">{children}</ul>,
                  ol: ({ children }) => <ol className="my-4 list-decimal space-y-2 pl-6 text-sm leading-7 text-slate-700 sm:text-base">{children}</ol>,
                  li: ({ children }) => <li className="break-words pl-1">{children}</li>,
                  table: ({ children }) => <table className="my-6 block w-full max-w-full overflow-x-auto border-collapse text-left text-sm">{children}</table>,
                  th: ({ children }) => <th className="whitespace-nowrap border border-[var(--border)] bg-[var(--surface-muted)] px-3 py-2 font-semibold text-[var(--ink)]">{children}</th>,
                  td: ({ children }) => <td className="min-w-32 border border-[var(--border)] px-3 py-2 align-top leading-6 text-slate-700">{children}</td>,
                  blockquote: ({ children }) => <blockquote className="my-5 border-l-4 border-teal-500 bg-teal-50/60 px-4 py-2 text-slate-600">{children}</blockquote>,
                  pre: ({ children }) => <pre className="my-5 max-w-full overflow-x-auto rounded-xl bg-slate-950 p-4 text-xs leading-6 text-slate-100 sm:text-sm">{children}</pre>,
                  code: ({ className, children }) => className ? (
                    <code className={`${className} font-mono`}>{children}</code>
                  ) : (
                    <code className="break-words rounded bg-[var(--surface-muted)] px-1.5 py-0.5 font-mono text-[0.9em] text-teal-800">{children}</code>
                  ),
                  a: ({ href, children, ...props }) => {
                    const external = typeof href === "string" && /^https?:\/\//i.test(href);
                    return (
                      <a
                        {...props}
                        href={href}
                        target={external ? "_blank" : undefined}
                        rel={external ? "noopener noreferrer" : undefined}
                        className="break-all font-medium text-teal-700 underline decoration-teal-300 underline-offset-2 hover:text-teal-900"
                      >
                        {children}
                      </a>
                    );
                  },
                }}
              >
                {viewModel.body}
              </ReactMarkdown>
            </div>

            {viewModel.sources.length > 0 && (
              <section className="mt-8 border-t border-[var(--border)] pt-6" aria-labelledby="shared-sources-heading">
                <div className="flex flex-wrap items-end justify-between gap-2">
                  <div>
                    <h2 id="shared-sources-heading" className="text-lg font-semibold">参考来源</h2>
                    <p className="mt-1 text-sm text-[var(--muted)]">报告引用的公开资料，可直接打开核验。</p>
                  </div>
                  <span className="text-xs text-[var(--muted)]">共 {viewModel.sources.length} 条</span>
                </div>
                <ol className="mt-4 divide-y divide-[var(--border)] border-y border-[var(--border)]">
                  {viewModel.sources.map((source, index) => (
                    <li key={`${source.url}-${index}`} className="py-4">
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="group block focus-visible:rounded-lg focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[var(--accent-soft)]"
                      >
                        <div className="flex min-w-0 items-start justify-between gap-4">
                          <div className="min-w-0">
                            <p className="break-words text-sm font-semibold text-[var(--ink)] group-hover:text-teal-800">{index + 1}. {source.title}</p>
                            <p className="mt-1 truncate text-xs text-[var(--muted)]">{source.url}</p>
                          </div>
                          <span className="shrink-0 rounded-lg bg-[var(--surface-muted)] px-2 py-1 text-xs text-[var(--muted)]">{source.source_type}</span>
                        </div>
                      </a>
                    </li>
                  ))}
                </ol>
              </section>
            )}

            {viewModel.metadata && (
              <details className="mt-7 rounded-xl border border-[var(--border)] bg-[var(--surface-muted)] p-4">
                <summary className="cursor-pointer text-sm font-semibold">成果物元数据</summary>
                <pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap break-words text-xs leading-5 text-slate-700">{viewModel.metadata}</pre>
              </details>
            )}
          </article>
        )}

        <footer className="py-2 text-center text-xs leading-5 text-[var(--muted)]">
          该页面仅用于查看研究成果，不提供编辑或执行操作。
        </footer>
      </div>
    </main>
  );
}

function Metric({ label, value, compact = false }: { label: string; value: string; compact?: boolean }) {
  return (
    <div className="min-w-0 bg-white p-3 sm:p-4">
      <dt className="text-xs text-[var(--muted)]">{label}</dt>
      <dd className={`mt-1 break-words font-semibold text-[var(--ink)] ${compact ? "text-xs leading-5 sm:text-sm" : "text-sm sm:text-base"}`}>{value}</dd>
    </div>
  );
}
