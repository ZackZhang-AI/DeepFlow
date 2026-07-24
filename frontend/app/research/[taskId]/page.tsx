"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  answerClarifications,
  confirmPlan,
  getAuthToken,
  getReport,
  getTask,
  redirectToLogin,
  retryResearchTask,
  subscribeToEvents,
} from "@/lib/api";
import { WorkspaceHeader } from "@/components/layout/WorkspaceHeader";
import { ClarificationForm } from "@/components/research/ClarificationForm";
import { PlanEditor } from "@/components/research/PlanEditor";
import { RecoveryActions } from "@/components/research/RecoveryActions";
import { ReportWorkspace } from "@/components/research/ReportWorkspace";
import { ResearchProgress } from "@/components/research/ResearchProgress";
import { ResearchStatusHeader } from "@/components/research/ResearchStatusHeader";
import { SourceInspector } from "@/components/research/SourceInspector";
import type { Report, ResearchStep, ResearchTask } from "@/lib/types";

interface DisplayEvent {
  type: string;
  data: Record<string, unknown>;
  time: number;
}

const ACTIVE_STATUSES = new Set(["coordinating", "planning", "queued", "researching", "generating_report"]);

export default function ResearchTaskPage() {
  const params = useParams<{ taskId: string }>();
  const router = useRouter();
  const taskId = params.taskId;
  const [task, setTask] = useState<ResearchTask | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [events, setEvents] = useState<DisplayEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [pollingFallback, setPollingFallback] = useState(false);
  const [reconnectKey, setReconnectKey] = useState(0);
  const [editingFailedPlan, setEditingFailedPlan] = useState(false);
  const lastSequenceRef = useRef(0);
  const sseErrorsRef = useRef(0);

  const loadTask = useCallback(async () => {
    const nextTask = await getTask(taskId);
    setTask(nextTask);

    if (nextTask.status === "completed") {
      try {
        setReport(await getReport(taskId));
      } catch (reason) {
        setLoadError(reason instanceof Error ? reason.message : "报告加载失败");
      }
    }
    return nextTask;
  }, [taskId]);

  useEffect(() => {
    if (!getAuthToken()) {
      redirectToLogin();
      return;
    }

    let active = true;
    getTask(taskId)
      .then(async (nextTask) => {
        if (!active) return;
        lastSequenceRef.current = Math.max(lastSequenceRef.current, nextTask.last_event_seq || 0);
        setTask(nextTask);
        if (nextTask.status === "completed") {
          const nextReport = await getReport(taskId);
          if (active) setReport(nextReport);
        }
      })
      .catch((reason) => {
        if (active) setLoadError(reason instanceof Error ? reason.message : "任务加载失败");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [taskId]);

  const shouldStream = task ? ACTIVE_STATUSES.has(task.status) : false;

  useEffect(() => {
    if (!shouldStream || pollingFallback) return;

    const unsubscribe = subscribeToEvents(
      taskId,
      (type, data) => {
        sseErrorsRef.current = 0;
        setConnected(true);
        const sequence = Number(data.sequence ?? 0);
        if (sequence > 0) lastSequenceRef.current = Math.max(lastSequenceRef.current, sequence);
        setEvents((current) => {
          if (sequence > 0 && current.some((event) => Number(event.data.sequence) === sequence)) return current;
          return [...current, { type, data, time: Date.now() }].slice(-100);
        });
        void loadTask();
      },
      () => {
        setConnected(false);
        sseErrorsRef.current += 1;
        if (sseErrorsRef.current >= 3) setPollingFallback(true);
      },
      lastSequenceRef.current,
    );

    return unsubscribe;
  }, [loadTask, pollingFallback, reconnectKey, shouldStream, taskId]);

  useEffect(() => {
    if (!shouldStream) return;
    const interval = window.setInterval(
      () => void loadTask().catch(() => undefined),
      pollingFallback ? 2000 : 10000,
    );
    return () => window.clearInterval(interval);
  }, [loadTask, pollingFallback, shouldStream]);

  const reconnect = () => {
    sseErrorsRef.current = 0;
    setPollingFallback(false);
    setConnected(false);
    setLoadError(null);
    setReconnectKey((value) => value + 1);
    void loadTask();
  };

  const submitClarifications = async (answers: Record<string, string>) => {
    setBusy(true);
    setLoadError(null);
    try {
      await answerClarifications(taskId, answers);
      await loadTask();
      reconnect();
    } catch (reason) {
      setLoadError(reason instanceof Error ? reason.message : "提交补充信息失败");
    } finally {
      setBusy(false);
    }
  };

  const submitPlan = async (steps: ResearchStep[]) => {
    setBusy(true);
    setLoadError(null);
    try {
      await confirmPlan(taskId, "edit", steps);
      await confirmPlan(taskId, "accept");
      setEditingFailedPlan(false);
      await loadTask();
      reconnect();
    } catch (reason) {
      setLoadError(reason instanceof Error ? reason.message : "确认研究计划失败");
    } finally {
      setBusy(false);
    }
  };

  const retry = async () => {
    setBusy(true);
    setLoadError(null);
    try {
      lastSequenceRef.current = Math.max(lastSequenceRef.current, task.last_event_seq || 0);
      await retryResearchTask(taskId);
      await loadTask();
      reconnect();
    } catch (reason) {
      setLoadError(reason instanceof Error ? reason.message : "重试任务失败");
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <main className="min-h-[100dvh] bg-[var(--background)]">
        <WorkspaceHeader active="research" />
        <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
          <div className="page-skeleton h-8 w-3/4 max-w-2xl rounded-lg" />
          <div className="page-skeleton mt-4 h-5 w-60 rounded-md" />
          <div className="mt-8 grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
            <div className="page-skeleton h-[32rem] rounded-xl" />
            <div className="page-skeleton h-80 rounded-xl" />
          </div>
        </div>
      </main>
    );
  }

  if (!task) {
    return (
      <main className="min-h-[100dvh] bg-[var(--background)]">
        <WorkspaceHeader active="research" />
        <div className="mx-auto flex min-h-[70dvh] max-w-xl flex-col items-center justify-center px-4 text-center">
          <div className="grid h-12 w-12 place-items-center rounded-full border border-red-200 bg-red-50 text-lg font-bold text-red-600">!</div>
          <h1 className="mt-4 text-2xl font-semibold text-[var(--ink)]">无法打开研究任务</h1>
          <p className="mt-2 text-sm leading-6 text-[var(--muted)]">{loadError || "任务不存在，或你没有访问权限。"}</p>
          <Link href="/" className="mt-5 inline-flex min-h-11 items-center rounded-xl bg-[var(--ink)] px-4 text-sm font-medium text-white">返回新研究</Link>
        </div>
      </main>
    );
  }

  const showProgress = ACTIVE_STATUSES.has(task.status);

  return (
    <main className="min-h-[100dvh] bg-[var(--background)] text-[var(--ink)]">
      <WorkspaceHeader
        active="research"
        actions={
          <button type="button" onClick={() => router.push("/")} className="min-h-10 rounded-lg px-3 text-xs font-medium text-[var(--muted)] hover:bg-white hover:text-[var(--ink)]">
            新研究
          </button>
        }
      />

      <div className="mx-auto max-w-7xl px-4 pb-16 pt-7 sm:px-6 sm:pt-9 lg:px-8">
        <ResearchStatusHeader task={task} connected={connected && !pollingFallback} />

        {loadError && (
          <div role="alert" className="mt-5 flex flex-col gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 sm:flex-row sm:items-center sm:justify-between">
            <span className="break-words">{loadError}</span>
            <button type="button" onClick={reconnect} className="shrink-0 font-semibold text-red-800 underline underline-offset-4">重新加载</button>
          </div>
        )}

        <div className="mt-6 grid min-w-0 gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div className="min-w-0 space-y-5">
            {task.status === "clarifying" && (
              <ClarificationForm questions={task.clarification_questions || []} busy={busy} onSubmit={submitClarifications} />
            )}

            {task.status === "awaiting_confirmation" && task.plan && (
              <div id="plan-review">
                <PlanEditor plan={task.plan} busy={busy} onConfirm={submitPlan} />
              </div>
            )}

            {showProgress && <ResearchProgress task={task} events={events} />}

            {task.status === "failed" && (
              <>
                <RecoveryActions
                  task={task}
                  busy={busy}
                  onReconnect={reconnect}
                  onRetry={retry}
                />
                {task.plan && (
                  <div id="plan-review">
                    <button
                      type="button"
                      onClick={() => setEditingFailedPlan((value) => !value)}
                      className="mb-3 min-h-11 rounded-xl border border-[var(--border)] bg-white px-4 text-sm font-medium text-slate-700 hover:bg-[var(--surface-muted)]"
                    >
                      {editingFailedPlan ? "收起计划" : "修改计划后重新执行"}
                    </button>
                    {editingFailedPlan && <PlanEditor plan={task.plan} busy={busy} onConfirm={submitPlan} />}
                  </div>
                )}
              </>
            )}

            {task.status === "completed" && report && <ReportWorkspace taskId={taskId} initialReport={report} />}
          </div>

          <aside className="min-w-0 space-y-5 lg:sticky lg:top-20 lg:self-start">
            <SourceInspector events={events} report={report} />
            {task.plan && task.status !== "awaiting_confirmation" && !(task.status === "failed" && editingFailedPlan) && (
              <section className="rounded-xl border border-[var(--border)] bg-white p-4" aria-labelledby="plan-summary-heading">
                <h2 id="plan-summary-heading" className="text-base font-semibold text-[var(--ink)]">研究计划</h2>
                <ol className="mt-4 space-y-3">
                  {task.plan.steps.map((step, index) => (
                    <li key={`${step.title}-${index}`} className="flex min-w-0 gap-3 text-sm">
                      <span className={`grid h-6 w-6 shrink-0 place-items-center rounded-full text-xs font-semibold ${
                        index < task.current_step ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-600"
                      }`}>
                        {index + 1}
                      </span>
                      <span className="min-w-0 break-words leading-6 text-slate-600">{step.title}</span>
                    </li>
                  ))}
                </ol>
              </section>
            )}
          </aside>
        </div>
      </div>
    </main>
  );
}
