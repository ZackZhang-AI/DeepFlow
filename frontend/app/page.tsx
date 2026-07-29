"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  APIRequestError,
  createResearch,
  getAuthToken,
  getCurrentUser,
  getSystemReadiness,
  listKnowledgeDocuments,
  listResearchTasks,
  redirectToLogin,
} from "@/lib/api";
import { ResearchComposer, RESEARCH_DEPTHS, type ResearchDepth } from "@/components/ResearchComposer";
import { WorkspaceHeader } from "@/components/layout/WorkspaceHeader";
import { ProviderReadinessCard } from "@/components/research/ProviderReadinessCard";
import { KnowledgePanel } from "@/components/KnowledgePanel";
import type { KnowledgeDocument, ProviderReadiness, ResearchStatus, ResearchTask } from "@/lib/types";

const STATUS_LABELS: Record<ResearchStatus, string> = {
  coordinating: "分析需求",
  clarifying: "待补充",
  planning: "生成计划",
  awaiting_confirmation: "待确认",
  queued: "排队中",
  researching: "研究中",
  generating_report: "生成报告",
  completed: "已完成",
  failed: "需处理",
};

function formatTime(value: string) {
  return new Date(value).toLocaleString("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function Home() {
  const router = useRouter();
  const [topic, setTopic] = useState("");
  const [selectedQuickPrompt, setSelectedQuickPrompt] = useState<string | null>(null);
  const [researchDepth, setResearchDepth] = useState<ResearchDepth>("fast");
  const [sourceDomains, setSourceDomains] = useState("");
  const [recencyDays, setRecencyDays] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [authChecking, setAuthChecking] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [recentTasks, setRecentTasks] = useState<ResearchTask[]>([]);
  const [recentLoading, setRecentLoading] = useState(true);
  const [readiness, setReadiness] = useState<ProviderReadiness | null>(null);
  const [readinessLoading, setReadinessLoading] = useState(true);
  const [knowledgeDocuments, setKnowledgeDocuments] = useState<KnowledgeDocument[]>([]);
  const [knowledgeEnabled, setKnowledgeEnabled] = useState(false);
  const [selectedKnowledgeDocumentIds, setSelectedKnowledgeDocumentIds] = useState<string[]>([]);

  const selectedDepth = useMemo(
    () => RESEARCH_DEPTHS.find((item) => item.id === researchDepth) ?? RESEARCH_DEPTHS[1],
    [researchDepth],
  );

  useEffect(() => {
    if (!getAuthToken()) {
      redirectToLogin();
      return;
    }

    Promise.all([getCurrentUser(), listResearchTasks(5), listKnowledgeDocuments().catch(() => [])])
      .then(([, tasks, documents]) => {
        setRecentTasks(tasks);
        setKnowledgeDocuments(documents);
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "页面加载失败"))
      .finally(() => {
        setAuthChecking(false);
        setRecentLoading(false);
      });

    getSystemReadiness(true)
      .then(setReadiness)
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Provider 状态检查失败"))
      .finally(() => setReadinessLoading(false));
  }, []);

  const refreshReadiness = useCallback(async () => {
    setReadinessLoading(true);
    setError(null);
    try {
      setReadiness(await getSystemReadiness(true));
    } catch (reason) {
      setReadiness(null);
      setError(reason instanceof Error ? reason.message : "Provider 状态检查失败");
    } finally {
      setReadinessLoading(false);
    }
  }, []);

  const handleKnowledgeDocumentsChange = useCallback((documents: KnowledgeDocument[]) => {
    setKnowledgeDocuments(documents);
    const readyIds = new Set(
      documents.filter((document) => document.status === "ready").map((document) => document.doc_id),
    );
    if (readyIds.size === 0) setKnowledgeEnabled(false);
    setSelectedKnowledgeDocumentIds((current) => current.filter((docId) => readyIds.has(docId)));
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!topic.trim() || submitting || !readiness?.ready) return;
    setSubmitting(true);
    setError(null);

    try {
      const domains = sourceDomains
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
      const recency = recencyDays ? Number(recencyDays) : undefined;
      const task = await createResearch(
        topic.trim(),
        "zh-CN",
        selectedDepth.maxSteps,
        domains,
        recency,
        undefined,
        researchDepth,
        {
          enabled: knowledgeEnabled,
          documentIds: knowledgeEnabled ? selectedKnowledgeDocumentIds : [],
        },
      );
      router.push(`/research/${task.task_id}`);
    } catch (reason) {
      if (
        reason instanceof APIRequestError
        && (reason.status === 402 || reason.errorCode === "provider_balance_exhausted")
      ) {
        setError("模型账户余额不足，请充值后重新检查 Provider。");
        setReadiness((current) => current
          ? {
              ...current,
              ready: false,
              model: {
                ...current.model,
                ready: false,
                error_code: "provider_balance_exhausted",
                reason: "模型账户余额不足，请充值后重新检查。",
              },
            }
          : current);
      } else {
        setError(reason instanceof Error ? reason.message : "创建研究失败");
      }
      setSubmitting(false);
    }
  }, [knowledgeEnabled, readiness?.ready, recencyDays, researchDepth, router, selectedDepth.maxSteps, selectedKnowledgeDocumentIds, sourceDomains, submitting, topic]);

  if (authChecking) {
    return (
      <main className="min-h-[100dvh] bg-[var(--background)]">
        <div className="border-b border-[var(--border)] bg-white/60">
          <div className="mx-auto h-16 max-w-7xl px-4 py-4 sm:px-6 lg:px-8">
            <div className="page-skeleton h-8 w-32 rounded-lg" />
          </div>
        </div>
        <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
          <div className="page-skeleton h-9 w-72 max-w-full rounded-lg" />
          <div className="page-skeleton mt-8 h-[28rem] rounded-2xl" />
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-[100dvh] bg-[var(--background)] text-[var(--ink)]">
      <WorkspaceHeader active="research" actions={<span className="hidden text-xs text-[var(--muted)] sm:block">AI 深度研究工作台</span>} />

      <div className="mx-auto max-w-7xl px-4 pb-16 pt-9 sm:px-6 sm:pt-12 lg:px-8">
        <section>
          <div className="mb-7 max-w-2xl">
            <h1 className="text-3xl font-semibold text-[var(--ink)] sm:text-4xl">开始一项深度研究</h1>
            <p className="mt-3 text-sm leading-6 text-[var(--muted)] sm:text-base">
              描述你要解决的问题，DeepFlow 会规划研究路径、检索真实资料并生成可追溯的报告。
            </p>
          </div>

          {error && (
            <div role="alert" className="mb-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <ProviderReadinessCard
            readiness={readiness}
            loading={readinessLoading}
            onRefresh={() => void refreshReadiness()}
          />

          <ResearchComposer
            topic={topic}
            selectedQuickPrompt={selectedQuickPrompt}
            researchDepth={researchDepth}
            sourceDomains={sourceDomains}
            recencyDays={recencyDays}
            knowledgeEnabled={knowledgeEnabled}
            knowledgeDocuments={knowledgeDocuments}
            selectedKnowledgeDocumentIds={selectedKnowledgeDocumentIds}
            isPlanning={submitting}
            isClarifying={false}
            creationDisabledReason={
              readinessLoading
                ? "正在确认模型与搜索服务，请稍候。"
                : readiness?.ready
                  ? undefined
                  : readiness?.model.error_code === "provider_balance_exhausted"
                    ? "模型账户余额不足，请充值后重新检查。"
                    : "研究服务尚未就绪，请检查 Provider 配置后重新检查。"
            }
            onTopicChange={(value) => {
              setTopic(value);
              setSelectedQuickPrompt(null);
            }}
            onQuickPrompt={(promptId, prompt) => {
              setTopic(prompt);
              setSelectedQuickPrompt(promptId);
            }}
            onDepthChange={setResearchDepth}
            onSourceDomainsChange={setSourceDomains}
            onRecencyDaysChange={setRecencyDays}
            onKnowledgeEnabledChange={setKnowledgeEnabled}
            onKnowledgeSelectionChange={setSelectedKnowledgeDocumentIds}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void handleSubmit();
              }
            }}
            onSubmit={() => void handleSubmit()}
          />
        </section>

        <div id="private-knowledge" className="mt-8 scroll-mt-24">
          <KnowledgePanel onDocumentsChange={handleKnowledgeDocumentsChange} />
        </div>

        <section className="mt-12 border-t border-[var(--border)] pt-8" aria-labelledby="recent-research-heading">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 id="recent-research-heading" className="text-xl font-semibold text-[var(--ink)]">最近研究</h2>
              <p className="mt-1 text-sm text-[var(--muted)]">继续未完成的任务，或回看已生成的报告。</p>
            </div>
            <Link href="/history" className="shrink-0 text-sm font-medium text-teal-700 hover:text-teal-900">
              查看全部
            </Link>
          </div>

          {recentLoading ? (
            <div className="mt-5 grid gap-3 md:grid-cols-2">
              {[0, 1, 2, 3].map((item) => <div key={item} className="page-skeleton h-28 rounded-xl" />)}
            </div>
          ) : recentTasks.length === 0 ? (
            <div className="mt-5 rounded-xl border border-dashed border-[var(--border)] bg-[var(--surface-muted)] px-5 py-10 text-center text-sm text-[var(--muted)]">
              还没有研究记录，从上方输入一个主题开始。
            </div>
          ) : (
            <div className="mt-5 grid gap-3 md:grid-cols-2">
              {recentTasks.map((task) => (
                <Link
                  key={task.task_id}
                  href={`/research/${task.task_id}`}
                  className="group min-w-0 rounded-xl border border-[var(--border)] bg-white p-4 transition hover:-translate-y-0.5 hover:border-teal-300 hover:shadow-[0_8px_20px_rgba(23,32,31,0.06)] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[var(--accent-soft)]"
                >
                  <div className="flex items-start justify-between gap-3">
                    <h3 className="min-w-0 line-clamp-2 text-sm font-semibold leading-6 text-[var(--ink)]">{task.topic}</h3>
                    <span className={`shrink-0 rounded-full border px-2.5 py-1 text-xs font-medium ${
                      task.status === "failed"
                        ? "border-red-200 bg-red-50 text-red-700"
                        : task.status === "completed"
                          ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                          : "border-cyan-200 bg-cyan-50 text-cyan-700"
                    }`}>
                      {STATUS_LABELS[task.status]}
                    </span>
                  </div>
                  <div className="mt-4 flex items-center justify-between border-t border-[var(--border)] pt-3 text-xs text-[var(--muted)]">
                    <span>{formatTime(task.updated_at)}</span>
                    <span className="font-medium text-teal-700 group-hover:text-teal-900">打开任务 →</span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
