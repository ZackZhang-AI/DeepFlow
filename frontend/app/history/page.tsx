"use client";

import { KeyboardEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  downloadWithAuth,
  getAuthToken,
  getCurrentUser,
  getReport,
  getResearchUsageSummary,
  listKnowledgeDocuments,
  listResearchTasks,
  listTaskArtifacts,
  logout,
  redirectToLogin,
} from "@/lib/api";
import { WorkspaceHeader } from "@/components/layout/WorkspaceHeader";
import { Button, getButtonClasses } from "@/components/ui/Button";
import { UsageSummaryStrip } from "@/components/history/UsageSummaryStrip";
import type { Artifact, AuthUser, KnowledgeDocument, Report, ResearchStatus, ResearchTask, UsageSummary } from "@/lib/types";
import { DemoBadge } from "@/components/ui/DemoBadge";

type AssetTab = "tasks" | "artifacts" | "knowledge";
type SelectedPanel = "report" | "error" | "progress" | null;

interface ArtifactAsset extends Artifact {
  taskTopic: string;
}

const STATUS_META: Record<ResearchStatus, {
  label: string;
  tone: "success" | "danger" | "info" | "warning" | "neutral";
  action: "report" | "error" | "progress";
}> = {
  coordinating: { label: "分析中", tone: "info", action: "progress" },
  clarifying: { label: "待补充", tone: "warning", action: "progress" },
  planning: { label: "规划中", tone: "info", action: "progress" },
  awaiting_confirmation: { label: "待确认", tone: "warning", action: "progress" },
  queued: { label: "已排队", tone: "info", action: "progress" },
  researching: { label: "研究中", tone: "warning", action: "progress" },
  generating_report: { label: "生成报告", tone: "info", action: "progress" },
  completed: { label: "已完成", tone: "success", action: "report" },
  failed: { label: "失败", tone: "danger", action: "error" },
};

const BADGE_CLASSES = {
  success: "border-emerald-200 bg-emerald-50 text-emerald-700",
  danger: "border-red-200 bg-red-50 text-red-600",
  info: "border-cyan-200 bg-cyan-50 text-cyan-700",
  warning: "border-amber-200 bg-amber-50 text-amber-700",
  neutral: "border-slate-200 bg-slate-50 text-slate-600",
};

const KNOWLEDGE_STATUS_META = {
  pending: { label: "待处理", tone: "warning" },
  processing: { label: "处理中", tone: "info" },
  ready: { label: "可检索", tone: "success" },
  completed: { label: "可检索", tone: "success" },
  failed: { label: "失败", tone: "danger" },
} satisfies Record<string, { label: string; tone: keyof typeof BADGE_CLASSES }>;

function StatusBadge({ status }: { status: ResearchStatus }) {
  const meta = STATUS_META[status] ?? { label: status, tone: "neutral" as const };
  return <span className={`whitespace-nowrap rounded-full border px-2.5 py-1 text-xs font-semibold ${BADGE_CLASSES[meta.tone]}`}>{meta.label}</span>;
}

function KnowledgeStatusBadge({ doc }: { doc: KnowledgeDocument }) {
  const meta = KNOWLEDGE_STATUS_META[doc.status] ?? { label: doc.status, tone: "neutral" as const };
  return <span className={`whitespace-nowrap rounded-full border px-2.5 py-1 text-xs font-semibold ${BADGE_CLASSES[meta.tone]}`}>{meta.label}</span>;
}

function getKnowledgeErrorSummary(doc: KnowledgeDocument) {
  if (doc.status !== "failed") return "";
  return doc.error_message || "处理失败，请重新上传或重建索引。";
}

function formatDate(value?: string) {
  if (!value) return "未知时间";
  return new Date(value).toLocaleString("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function getFailureMessage(task: ResearchTask) {
  return task.error_message || "该任务失败，暂时没有详细错误。请查看后端日志或重新发起研究。";
}

function getArtifactTypeLabel(type: string) {
  if (type.includes("podcast_audio")) return "播客音频";
  if (type.includes("podcast")) return "播客脚本";
  if (type.includes("pptx")) return "PPTX";
  if (type.includes("ppt")) return "演示文稿";
  if (type.includes("report_style")) return "报告版本";
  return type || "成果物";
}

export default function HistoryPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<AssetTab>("tasks");
  const [tasks, setTasks] = useState<ResearchTask[]>([]);
  const [artifacts, setArtifacts] = useState<ArtifactAsset[]>([]);
  const [knowledgeDocs, setKnowledgeDocs] = useState<KnowledgeDocument[]>([]);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [assetError, setAssetError] = useState<string | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [selectedPanel, setSelectedPanel] = useState<SelectedPanel>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [loadingReportTask, setLoadingReportTask] = useState<string | null>(null);
  const [usageSummary, setUsageSummary] = useState<UsageSummary | null>(null);

  const stats = useMemo(() => {
    const completed = tasks.filter((task) => task.status === "completed").length;
    const running = tasks.filter((task) => ["coordinating", "planning", "queued", "researching", "generating_report"].includes(task.status)).length;
    return { completed, running };
  }, [tasks]);

  const loadAssets = useCallback(async () => {
    setLoading(true);
    setAssetError(null);
    try {
      const usageSummaryPromise = getResearchUsageSummary().catch(() => null);
      const loadedTasks = await listResearchTasks(50);
      setTasks(loadedTasks);
      setUsageSummary(await usageSummaryPromise);

      const tasksForArtifacts = loadedTasks.filter((task) => task.status === "completed").slice(0, 20);
      const artifactResults = await Promise.allSettled(
        tasksForArtifacts.map(async (task) => {
          const items = await listTaskArtifacts(task.task_id);
          return items.map((artifact) => ({ ...artifact, taskTopic: task.topic }));
        }),
      );
      setArtifacts(artifactResults.flatMap((result) => (result.status === "fulfilled" ? result.value : [])));

      try {
        setKnowledgeDocs(await listKnowledgeDocuments());
      } catch {
        setKnowledgeDocs([]);
      }
    } catch (err) {
      setAssetError(err instanceof Error ? err.message : "资产加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!getAuthToken()) {
      redirectToLogin();
      return;
    }

    getCurrentUser()
      .then((currentUser) => {
        setUser(currentUser);
        void loadAssets();
      })
      .catch((err) => {
        if (err instanceof Error) setAssetError(err.message);
        setLoading(false);
      });
  }, [loadAssets]);

  const viewReport = async (taskId: string) => {
    setSelectedTaskId(taskId);
    setSelectedPanel("report");
    setLoadingReportTask(taskId);
    setReport(null);
    try {
      setReport(await getReport(taskId));
    } catch {
      setReport(null);
    } finally {
      setLoadingReportTask(null);
    }
  };

  const previewTask = (task: ResearchTask) => {
    const action = STATUS_META[task.status]?.action ?? "progress";
    if (action === "report") {
      void viewReport(task.task_id);
      return;
    }
    setSelectedTaskId(task.task_id);
    setSelectedPanel(action);
    setReport(null);
  };

  const openTask = (task: ResearchTask) => {
    router.push(`/research/${task.task_id}`);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>, task: ResearchTask) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openTask(task);
    }
  };

  const handleLogout = async () => {
    try {
      await logout();
    } finally {
      redirectToLogin();
    }
  };

  const getTaskActionLabel = (task: ResearchTask) => {
    const action = STATUS_META[task.status]?.action;
    if (action === "report") return "查看报告";
    if (action === "error") return "查看错误";
    return "查看进度";
  };

  const getTaskActionVariant = (task: ResearchTask) => {
    const action = STATUS_META[task.status]?.action;
    if (action === "error") return "danger" as const;
    if (action === "report") return "soft" as const;
    return "secondary" as const;
  };

  return (
    <main className="min-h-screen bg-[var(--background)] text-[var(--ink)]">
      <WorkspaceHeader
        active="assets"
        actions={
          <>
            <span className="hidden text-xs text-[var(--muted)] sm:block">{user?.username ?? "个人工作台"}</span>
            <Button variant="ghost" size="sm" onClick={handleLogout}>退出</Button>
          </>
        }
      />

      <div className="mx-auto max-w-7xl px-4 py-9 sm:px-6 sm:py-12 lg:px-8">
        <div className="mb-7 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="text-3xl font-semibold text-[var(--ink)]">研究资产</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted)]">
              查看研究任务、成果物与知识库资料。
            </p>
          </div>
          <Link href="/" className={getButtonClasses({ variant: "primary", size: "md", className: "w-fit" })}>
            <span aria-hidden="true">+</span> 新建研究
          </Link>
        </div>

        <UsageSummaryStrip summary={usageSummary} />

        <div className="mb-5 flex flex-wrap gap-x-6 gap-y-2 border-y border-[var(--border)] py-3 text-sm text-[var(--muted)]">
          <span>研究任务 <strong className="ml-1 font-semibold text-[var(--ink)]">{tasks.length}</strong></span>
          <span>已完成 <strong className="ml-1 font-semibold text-[var(--ink)]">{stats.completed}</strong></span>
          <span>进行中 <strong className="ml-1 font-semibold text-[var(--ink)]">{stats.running}</strong></span>
        </div>

        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_380px]">
          <section className="rounded-2xl border border-[var(--border)] bg-white p-4 shadow-[0_12px_32px_rgba(23,32,31,0.05)]">
            <div className="mb-4 flex flex-wrap items-center gap-1 border-b border-[var(--border)] pb-3">
              {[
                ["tasks", "研究任务"],
                ["artifacts", "成果物"],
                ["knowledge", "知识库"],
              ].map(([id, label]) => (
                <button
                  key={id}
                  onClick={() => setActiveTab(id as AssetTab)}
                  className={`min-h-11 rounded-xl px-4 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[var(--accent-soft)] ${activeTab === id ? "bg-[var(--ink)] text-white" : "text-[var(--muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--ink)]"}`}
                >
                  {label}
                </button>
              ))}
              <button
                onClick={() => void loadAssets()}
                className="ml-auto min-h-11 rounded-xl px-3 py-2 text-sm font-medium text-[var(--muted)] transition-colors hover:bg-[var(--surface-muted)] hover:text-[var(--ink)] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[var(--accent-soft)]"
              >
                刷新
              </button>
            </div>

            {assetError && <div className="mb-4 rounded-2xl border border-red-200 bg-red-50 p-3 text-sm text-red-600">{assetError}</div>}
            {loading ? (
              <div className="space-y-3 py-2">
                {[0, 1, 2, 3].map((item) => <div key={item} className="page-skeleton h-24 rounded-xl" />)}
              </div>
            ) : (
              <>
                {activeTab === "tasks" && (
                  <div className="space-y-3">
                    {tasks.length === 0 ? (
                      <EmptyState text="还没有研究任务。" />
                    ) : (
                      tasks.map((task) => (
                        <div
                          key={task.task_id}
                          role="button"
                          tabIndex={0}
                          onClick={() => openTask(task)}
                          onKeyDown={(event) => handleKeyDown(event, task)}
                          className={`rounded-xl border p-4 text-left transition-all hover:-translate-y-0.5 hover:border-teal-300 hover:shadow-[0_8px_20px_rgba(23,32,31,0.06)] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[var(--accent-soft)] ${selectedTaskId === task.task_id ? "border-teal-300 bg-teal-50/60" : "border-[var(--border)] bg-white"}`}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <div className="flex flex-wrap items-start gap-2">
                                <h3 className="min-w-0 flex-1 line-clamp-2 text-sm font-semibold text-slate-950">{task.topic}</h3>
                                {task.is_demo && <DemoBadge />}
                              </div>
                              <p className="mt-1 text-xs text-slate-500">{formatDate(task.updated_at)}</p>
                            </div>
                            <StatusBadge status={task.status} />
                          </div>
                          <div className="mt-3 flex items-center justify-end border-t border-[var(--border)] pt-3">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={(event) => {
                                event.stopPropagation();
                                previewTask(task);
                              }}
                            >
                              快速预览
                            </Button>
                            <Button
                              variant={getTaskActionVariant(task)}
                              size="sm"
                              onClick={(event) => {
                                event.stopPropagation();
                                openTask(task);
                              }}
                            >
                              {getTaskActionLabel(task)} <span aria-hidden="true">→</span>
                            </Button>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}

                {activeTab === "artifacts" && (
                  <div className="space-y-3">
                    {artifacts.length === 0 ? (
                      <EmptyState text="还没有成果物。" />
                    ) : (
                      artifacts.map((artifact) => (
                        <div key={artifact.artifact_id} className="rounded-xl border border-[var(--border)] bg-white p-4">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="text-xs font-semibold text-cyan-700">{getArtifactTypeLabel(artifact.artifact_type)}</p>
                              <h3 className="mt-1 line-clamp-2 text-sm font-semibold text-slate-950">{artifact.title || artifact.artifact_id}</h3>
                              <p className="mt-1 line-clamp-1 text-xs text-slate-500">{artifact.taskTopic}</p>
                            </div>
                            <Button
                              variant="secondary"
                              size="sm"
                              onClick={() => void downloadWithAuth(artifact.download_url || `/api/artifacts/download/${artifact.artifact_id}`, artifact.title || "artifact.md")}
                            >
                              下载
                            </Button>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}

                {activeTab === "knowledge" && (
                  <div className="space-y-3">
                    {knowledgeDocs.length === 0 ? (
                      <EmptyState text="还没有知识库文档。" />
                    ) : (
                      knowledgeDocs.map((doc) => (
                        <div key={doc.doc_id} className="rounded-xl border border-[var(--border)] bg-white p-4">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <h3 className="line-clamp-2 text-sm font-semibold text-slate-950">{doc.title}</h3>
                              <p className="mt-1 text-xs text-slate-500">
                                {doc.source_type} · {doc.chunk_count} chunks · {doc.content_length} 字
                              </p>
                              {getKnowledgeErrorSummary(doc) && (
                                <p className="mt-2 line-clamp-2 rounded-xl border border-red-100 bg-red-50 px-2 py-1 text-xs text-red-600">
                                  {getKnowledgeErrorSummary(doc)}
                                </p>
                              )}
                            </div>
                            <KnowledgeStatusBadge doc={doc} />
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </>
            )}
          </section>

          <aside className="min-h-80 rounded-2xl border border-[var(--border)] bg-white p-5 shadow-[0_12px_32px_rgba(23,32,31,0.05)] lg:sticky lg:top-20 lg:self-start">
            {!selectedPanel && (
              <div className="flex min-h-80 flex-col items-center justify-center text-center">
                <p className="text-sm font-medium text-slate-700">选择左侧资产查看详情</p>
                <p className="mt-2 text-xs leading-5 text-[var(--muted)]">任务报告、错误原因和执行进度会显示在这里。</p>
              </div>
            )}

            {selectedPanel === "report" && (
              <div>
                <h2 className="text-lg font-semibold tracking-tight text-slate-950">报告预览</h2>
                {loadingReportTask ? (
                  <div className="mt-5 space-y-3" aria-label="正在加载报告">
                    <div className="page-skeleton h-24 rounded-xl" />
                    <div className="page-skeleton h-11 rounded-xl" />
                    <div className="page-skeleton h-11 rounded-xl" />
                  </div>
                ) : report ? (
                  <div className="mt-4 space-y-3">
                    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-muted)] p-4">
                      <h3 className="text-sm font-semibold text-slate-950">{report.title}</h3>
                      <p className="mt-2 text-xs leading-6 text-slate-500">
                        {report.sources_count} 个来源 · {Math.round(report.elapsed_seconds)}s · ¥{report.cost_rmb.toFixed(2)}
                      </p>
                    </div>
                    <Button
                      variant="secondary"
                      fullWidth
                      onClick={() => selectedTaskId && void downloadWithAuth(`/api/reports/${selectedTaskId}/download?format=markdown`, `${report.title || "report"}.md`)}
                    >
                      下载 Markdown
                    </Button>
                    <Button
                      variant="primary"
                      fullWidth
                      onClick={() => selectedTaskId && void downloadWithAuth(`/api/reports/${selectedTaskId}/download?format=pdf`, `${report.title || "report"}.pdf`)}
                    >
                      下载 PDF
                    </Button>
                  </div>
                ) : (
                  <p className="mt-4 text-sm text-slate-500">报告加载失败或尚未生成。</p>
                )}
              </div>
            )}

            {selectedPanel === "progress" && (
              <div>
                <h2 className="text-lg font-semibold tracking-tight text-slate-950">任务进度</h2>
                <p className="mt-3 text-sm leading-6 text-slate-500">该任务还在处理中，回到研究页后可继续查看实时进度。</p>
              </div>
            )}

            {selectedPanel === "error" && selectedTaskId && (
              <div>
                <h2 className="text-lg font-semibold tracking-tight text-red-600">失败原因</h2>
                <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-600">
                  {getFailureMessage(tasks.find((task) => task.task_id === selectedTaskId)!)}
                </p>
              </div>
            )}
          </aside>
        </div>
      </div>
    </main>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="flex min-h-48 items-center justify-center rounded-xl border border-dashed border-[var(--border)] bg-[var(--surface-muted)] text-sm text-[var(--muted)]">
      {text}
    </div>
  );
}
