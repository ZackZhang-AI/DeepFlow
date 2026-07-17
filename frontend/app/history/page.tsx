"use client";

import { KeyboardEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  clearAuthToken,
  downloadWithAuth,
  getAuthToken,
  getCurrentUser,
  getReport,
  listKnowledgeDocuments,
  listResearchTasks,
  listTaskArtifacts,
  redirectToLogin,
} from "@/lib/api";
import { Button, getButtonClasses } from "@/components/ui/Button";
import type { Artifact, AuthUser, KnowledgeDocument, Report, ResearchStatus, ResearchTask } from "@/lib/types";

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

function PlusIcon() {
  return (
    <svg aria-hidden="true" className="h-4 w-4" viewBox="0 0 20 20" fill="none">
      <path d="M10 4v12M4 10h12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function ArrowRightIcon() {
  return (
    <svg aria-hidden="true" className="h-4 w-4" viewBox="0 0 20 20" fill="none">
      <path d="M4 10h11m0 0-4-4m4 4-4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function StatusBadge({ status }: { status: ResearchStatus }) {
  const meta = STATUS_META[status] ?? { label: status, tone: "neutral" as const };
  return <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${BADGE_CLASSES[meta.tone]}`}>{meta.label}</span>;
}

function KnowledgeStatusBadge({ doc }: { doc: KnowledgeDocument }) {
  const meta = KNOWLEDGE_STATUS_META[doc.status] ?? { label: doc.status, tone: "neutral" as const };
  return <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${BADGE_CLASSES[meta.tone]}`}>{meta.label}</span>;
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
  if (!task.errors_json) return "该任务失败，暂时没有详细错误。请查看后端日志或重新发起研究。";
  try {
    const parsed = JSON.parse(task.errors_json) as unknown;
    if (Array.isArray(parsed) && parsed.length > 0) return parsed.join("\n");
  } catch {
    return task.errors_json;
  }
  return "该任务失败，暂时没有详细错误。";
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

  const stats = useMemo(() => {
    const completed = tasks.filter((task) => task.status === "completed").length;
    const running = tasks.filter((task) => ["coordinating", "planning", "queued", "researching", "generating_report"].includes(task.status)).length;
    return { completed, running };
  }, [tasks]);

  const loadAssets = useCallback(async () => {
    setLoading(true);
    setAssetError(null);
    try {
      const loadedTasks = await listResearchTasks(50);
      setTasks(loadedTasks);

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

  const openTask = (task: ResearchTask) => {
    const action = STATUS_META[task.status]?.action ?? "progress";
    if (action === "report") {
      void viewReport(task.task_id);
      return;
    }
    setSelectedTaskId(task.task_id);
    setSelectedPanel(action);
    setReport(null);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>, task: ResearchTask) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openTask(task);
    }
  };

  const handleLogout = () => {
    clearAuthToken();
    redirectToLogin();
  };

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#f7f8f4] text-slate-950">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_18%_8%,rgba(70,188,196,0.20),transparent_34%),radial-gradient(circle_at_82%_16%,rgba(102,144,255,0.16),transparent_32%),linear-gradient(180deg,#fbfbf7_0%,#eef6f6_48%,#f7f8f4_100%)]" />
      <div className="pointer-events-none absolute inset-0 -z-10 opacity-[0.40] [background-image:linear-gradient(rgba(15,23,42,0.055)_1px,transparent_1px),linear-gradient(90deg,rgba(15,23,42,0.055)_1px,transparent_1px)] [background-size:42px_42px]" />

      <header className="sticky top-0 z-30 border-b border-slate-900/10 bg-white/72 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
          <div className="flex items-center gap-6">
            <Link href="/" className="group flex items-center gap-2">
              <span className="grid h-8 w-8 place-items-center rounded-xl border border-cyan-500/20 bg-gradient-to-br from-cyan-50 to-blue-50 text-sm font-black text-cyan-700 shadow-sm shadow-cyan-900/5">D</span>
              <span className="text-lg font-semibold tracking-tight text-slate-950">DeepFlow</span>
            </Link>
            <nav className="hidden items-center rounded-2xl border border-slate-200 bg-white/55 p-1 text-sm shadow-sm sm:flex">
              <Link href="/" className={getButtonClasses({ variant: "ghost", size: "sm", className: "min-h-9" })}>研究</Link>
              <span className={getButtonClasses({ variant: "ghost", size: "sm", className: "min-h-9 bg-slate-950 text-white hover:bg-slate-950 hover:text-white" })}>资产中心</span>
            </nav>
          </div>
          <div className="flex items-center gap-2">
            <span className="hidden rounded-full border border-cyan-700/10 bg-cyan-50/70 px-3 py-1.5 text-xs font-medium text-slate-600 shadow-sm sm:inline-flex">
              {user?.username ?? "个人工作台"}
            </span>
            <Button variant="ghost" size="sm" onClick={handleLogout}>
              退出
            </Button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-12">
        <div className="mb-7 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-700">Asset Center</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">个人资产中心</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
              统一管理你的研究任务、报告、PPTX、播客和知识库文档。
            </p>
          </div>
          <Link href="/" className={getButtonClasses({ variant: "primary", size: "md", className: "w-fit", })}>
            <PlusIcon />
            新建研究
          </Link>
        </div>

        <div className="mb-6 grid gap-3 sm:grid-cols-3">
          <StatCard label="研究任务" value={tasks.length} />
          <StatCard label="已完成" value={stats.completed} />
          <StatCard label="进行中" value={stats.running} />
        </div>

        <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
          <section className="rounded-3xl border border-white/70 bg-white/68 p-4 shadow-[0_24px_70px_rgba(15,23,42,0.10)] backdrop-blur-xl">
            <div className="mb-4 flex flex-wrap gap-2">
              {[
                ["tasks", "研究任务"],
                ["artifacts", "成果物"],
                ["knowledge", "知识库"],
              ].map(([id, label]) => (
                <button
                  key={id}
                  onClick={() => setActiveTab(id as AssetTab)}
                  className={`rounded-2xl px-4 py-2 text-sm font-semibold transition ${activeTab === id ? "bg-slate-950 text-white" : "bg-white/70 text-slate-600 hover:bg-white"}`}
                >
                  {label}
                </button>
              ))}
              <button
                onClick={() => void loadAssets()}
                className="ml-auto rounded-2xl border border-slate-200 bg-white/70 px-4 py-2 text-sm font-semibold text-slate-600 transition hover:bg-white"
              >
                刷新
              </button>
            </div>

            {assetError && <div className="mb-4 rounded-2xl border border-red-200 bg-red-50 p-3 text-sm text-red-600">{assetError}</div>}
            {loading ? (
              <div className="flex min-h-72 items-center justify-center">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent" />
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
                          className={`rounded-2xl border p-4 text-left transition hover:-translate-y-0.5 hover:bg-white ${selectedTaskId === task.task_id ? "border-cyan-300 bg-cyan-50/60" : "border-slate-200 bg-white/70"}`}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <h3 className="line-clamp-2 text-sm font-semibold text-slate-950">{task.topic}</h3>
                              <p className="mt-1 text-xs text-slate-500">{formatDate(task.updated_at)}</p>
                            </div>
                            <StatusBadge status={task.status} />
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
                        <div key={artifact.artifact_id} className="rounded-2xl border border-slate-200 bg-white/70 p-4">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="text-xs font-semibold text-cyan-700">{getArtifactTypeLabel(artifact.artifact_type)}</p>
                              <h3 className="mt-1 line-clamp-2 text-sm font-semibold text-slate-950">{artifact.title || artifact.artifact_id}</h3>
                              <p className="mt-1 line-clamp-1 text-xs text-slate-500">{artifact.taskTopic}</p>
                            </div>
                            <button
                              onClick={() => void downloadWithAuth(artifact.download_url || `/api/artifacts/download/${artifact.artifact_id}`, artifact.title || "artifact.md")}
                              className="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
                            >
                              下载
                            </button>
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
                        <div key={doc.doc_id} className="rounded-2xl border border-slate-200 bg-white/70 p-4">
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

          <aside className="rounded-3xl border border-white/70 bg-white/68 p-5 shadow-[0_24px_70px_rgba(15,23,42,0.10)] backdrop-blur-xl">
            {!selectedPanel && (
              <div className="flex min-h-80 flex-col items-center justify-center text-center">
                <div className="mb-3 grid h-12 w-12 place-items-center rounded-full bg-cyan-50 text-cyan-700">
                  <ArrowRightIcon />
                </div>
                <p className="text-sm font-medium text-slate-700">选择左侧资产查看详情</p>
              </div>
            )}

            {selectedPanel === "report" && (
              <div>
                <h2 className="text-lg font-semibold tracking-tight text-slate-950">报告预览</h2>
                {loadingReportTask ? (
                  <div className="mt-8 flex justify-center">
                    <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent" />
                  </div>
                ) : report ? (
                  <div className="mt-4 space-y-3">
                    <div className="rounded-2xl border border-slate-200 bg-white/70 p-4">
                      <h3 className="text-sm font-semibold text-slate-950">{report.title}</h3>
                      <p className="mt-2 text-xs leading-6 text-slate-500">
                        {report.sources_count} 个来源 · {Math.round(report.elapsed_seconds)}s · ¥{report.cost_rmb.toFixed(2)}
                      </p>
                    </div>
                    <button
                      onClick={() => selectedTaskId && void downloadWithAuth(`/api/reports/${selectedTaskId}/download?format=markdown`, `${report.title || "report"}.md`)}
                      className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                    >
                      下载 Markdown
                    </button>
                    <button
                      onClick={() => selectedTaskId && void downloadWithAuth(`/api/reports/${selectedTaskId}/download?format=pdf`, `${report.title || "report"}.pdf`)}
                      className="w-full rounded-2xl bg-slate-950 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800"
                    >
                      下载 PDF
                    </button>
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

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-3xl border border-white/70 bg-white/68 p-5 shadow-[0_14px_40px_rgba(15,23,42,0.06)]">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className="mt-2 text-3xl font-semibold text-slate-950">{value}</p>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="flex min-h-48 items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-white/50 text-sm text-slate-500">
      {text}
    </div>
  );
}
