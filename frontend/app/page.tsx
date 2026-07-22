"use client";

import { useCallback, useEffect, useState } from "react";
import {
  answerClarifications,
  confirmPlan,
  createResearch,
  getAuthToken,
  getCurrentUser,
  getReport,
  redirectToLogin,
  subscribeToEvents,
} from "@/lib/api";
import { ArtifactTools } from "@/components/ArtifactTools";
import { KnowledgePanel } from "@/components/KnowledgePanel";
import { ResearchComposer, RESEARCH_DEPTHS, type ResearchDepth } from "@/components/ResearchComposer";
import { ReportView } from "@/components/ReportView";
import { StyleSelector } from "@/components/StyleSelector";
import { Timeline } from "@/components/Timeline";
import { WorkspaceHeader } from "@/components/layout/WorkspaceHeader";
import { Button } from "@/components/ui/Button";
import type { ResearchPlan, ResearchStep, Report } from "@/lib/types";

type UIState = "input" | "loading" | "clarifying" | "plan_ready" | "researching" | "completed" | "error";
export default function Home() {
  const [uiState, setUiState] = useState<UIState>("input");
  const [topic, setTopic] = useState("");
  const [selectedQuickPrompt, setSelectedQuickPrompt] = useState<string | null>(null);
  const [researchDepth, setResearchDepth] = useState<ResearchDepth>("standard");
  const [sourceDomains, setSourceDomains] = useState("");
  const [recencyDays, setRecencyDays] = useState("");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [clarificationQuestions, setClarificationQuestions] = useState<string[]>([]);
  const [clarificationAnswers, setClarificationAnswers] = useState<Record<string, string>>({});
  const [plan, setPlan] = useState<ResearchPlan | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [reportStyle, setReportStyle] = useState("general");
  const [events, setEvents] = useState<{ type: string; data: Record<string, unknown>; time: number }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [totalSteps, setTotalSteps] = useState(0);
  const [confirmingPlan, setConfirmingPlan] = useState(false);
  const [editableSteps, setEditableSteps] = useState<ResearchStep[]>([]);
  const [authChecking, setAuthChecking] = useState(true);

  const selectedDepth = RESEARCH_DEPTHS.find((item) => item.id === researchDepth) ?? RESEARCH_DEPTHS[1];
  const isPlanning = uiState === "loading";

  useEffect(() => {
    if (!getAuthToken()) {
      redirectToLogin();
      return;
    }

    getCurrentUser()
      .then(() => setAuthChecking(false))
      .catch((err) => {
        if (err instanceof Error) setError(err.message);
        setAuthChecking(false);
      });
  }, []);

  const startEventStream = useCallback((nextTaskId: string) => {
    return subscribeToEvents(
      nextTaskId,
      (type, data) => {
        setEvents((prev) => [...prev, { type, data, time: Date.now() }]);

        if (type === "planner.completed") {
          const nextPlan = (data.plan ?? data) as unknown as ResearchPlan;
          setPlan(nextPlan);
          setEditableSteps(nextPlan.steps ?? []);
          setTotalSteps((data.steps_count as number) ?? nextPlan.steps?.length ?? selectedDepth.maxSteps);
          setUiState("plan_ready");
        } else if (type === "research.started") {
          setUiState("researching");
          setTotalSteps((data.total_steps as number) ?? totalSteps);
        } else if (type === "step.started") {
          setCurrentStep((data.step_index as number) ?? 0);
          setTotalSteps((data.total_steps as number) ?? totalSteps);
        } else if (type === "step.completed") {
          setCurrentStep((data.step_index as number) ?? 0);
        } else if (type === "report.completed") {
          getReport(nextTaskId).then((rep) => {
            setReport(rep);
            setUiState("completed");
          });
        } else if (type === "error.fatal") {
          setError((data.message as string) ?? "未知错误");
          setUiState("error");
        }
      },
      (err) => console.error("SSE:", err),
    );
  }, [selectedDepth.maxSteps, totalSteps]);

  const handleTopicChange = (value: string) => {
    setTopic(value);
    setSelectedQuickPrompt(null);
  };

  const handleQuickPrompt = (promptId: string, prompt: string) => {
    setTopic(prompt);
    setSelectedQuickPrompt(promptId);
  };

  const handleSubmit = useCallback(async () => {
    if (!getAuthToken()) {
      redirectToLogin();
      return;
    }
    if (!topic.trim() || uiState === "loading") return;
    setUiState("loading");
    setError(null);
    setEvents([]);
    setReport(null);
    setPlan(null);
    setEditableSteps([]);
    setConfirmingPlan(false);
    setClarificationQuestions([]);
    setClarificationAnswers({});

    try {
      const domains = sourceDomains.split(",").map((item) => item.trim()).filter(Boolean);
      const recency = recencyDays ? Number(recencyDays) : undefined;
      const task = await createResearch(topic.trim(), "zh-CN", selectedDepth.maxSteps, domains, recency);
      setTaskId(task.task_id);

      if (task.status === "clarifying") {
        setClarificationQuestions(task.clarification_questions ?? []);
        setUiState("clarifying");
        return;
      }

      startEventStream(task.task_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "未知错误");
      setUiState("error");
    }
  }, [recencyDays, selectedDepth.maxSteps, sourceDomains, startEventStream, topic, uiState]);

  const handleClarificationSubmit = async () => {
    if (!taskId) return;
    setUiState("loading");
    setError(null);
    try {
      const task = await answerClarifications(taskId, clarificationAnswers);
      startEventStream(task.task_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "提交补充信息失败");
      setUiState("error");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSubmit();
    }
  };

  const handleReset = () => {
    setUiState("input");
    setTopic("");
    setSelectedQuickPrompt(null);
    setResearchDepth("standard");
    setSourceDomains("");
    setRecencyDays("");
    setTaskId(null);
    setClarificationQuestions([]);
    setClarificationAnswers({});
    setPlan(null);
    setEditableSteps([]);
    setReport(null);
    setEvents([]);
    setError(null);
    setCurrentStep(0);
    setTotalSteps(0);
    setConfirmingPlan(false);
  };

  const handleConfirmPlan = useCallback(async () => {
    if (!taskId) return;
    setConfirmingPlan(true);
    setError(null);
    try {
      if (plan && editableSteps.length > 0) {
        await confirmPlan(taskId, "edit", editableSteps);
      }
      await confirmPlan(taskId, "accept");
      setUiState("researching");
    } catch (e) {
      setError(e instanceof Error ? e.message : "确认计划失败");
      setUiState("error");
    } finally {
      setConfirmingPlan(false);
    }
  }, [editableSteps, plan, taskId]);

  const handleRejectPlan = useCallback(async () => {
    if (!taskId) return;
    setConfirmingPlan(true);
    try {
      await confirmPlan(taskId, "reject");
    } finally {
      handleReset();
    }
  }, [taskId]);

  const updateStep = (index: number, patch: Partial<ResearchStep>) => {
    setEditableSteps((steps) => steps.map((step, i) => (i === index ? { ...step, ...patch } : step)));
  };

  const handleRestyle = (style: string, markdown: string) => {
    setReportStyle(style);
    if (report) setReport({ ...report, content_markdown: markdown });
  };

  if (authChecking) {
    return (
      <main className="min-h-screen bg-[var(--background)]">
        <div className="border-b border-[var(--border)] bg-white/60">
          <div className="mx-auto flex h-16 max-w-7xl items-center px-4 sm:px-6 lg:px-8">
            <div className="page-skeleton h-8 w-32 rounded-lg" />
          </div>
        </div>
        <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
          <div className="page-skeleton h-9 w-72 max-w-full rounded-lg" />
          <div className="page-skeleton mt-4 h-5 w-[30rem] max-w-full rounded-md" />
          <div className="mt-8 grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
            <div className="page-skeleton h-[28rem] rounded-2xl" />
            <div className="page-skeleton h-80 rounded-2xl" />
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[var(--background)] text-[var(--ink)]">
      <WorkspaceHeader active="research" actions={<span className="hidden text-xs text-[var(--muted)] sm:block">AI 深度研究工作台</span>} />

      <div className="mx-auto max-w-7xl px-4 pb-16 pt-9 sm:px-6 sm:pt-12 lg:px-8">
        {(uiState === "input" || uiState === "loading" || uiState === "clarifying") && (
          <section>
            <div className="mb-7 max-w-2xl">
              <h1 className="text-3xl font-semibold text-[var(--ink)] sm:text-4xl">开始一项深度研究</h1>
              <p className="mt-3 text-sm leading-6 text-[var(--muted)] sm:text-base">
                描述你要解决的问题，DeepFlow 将规划研究路径、检索资料并生成可追溯的报告。
              </p>
            </div>

            <ResearchComposer
              topic={topic}
              selectedQuickPrompt={selectedQuickPrompt}
              researchDepth={researchDepth}
              sourceDomains={sourceDomains}
              recencyDays={recencyDays}
              isPlanning={isPlanning}
              isClarifying={uiState === "clarifying"}
              onTopicChange={handleTopicChange}
              onQuickPrompt={handleQuickPrompt}
              onDepthChange={setResearchDepth}
              onSourceDomainsChange={setSourceDomains}
              onRecencyDaysChange={setRecencyDays}
              onKeyDown={handleKeyDown}
              onSubmit={() => void handleSubmit()}
            />

            {uiState === "clarifying" && (
              <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-5">
                <h2 className="text-lg font-semibold text-[var(--ink)]">还需要补充一点上下文</h2>
                <div className="mt-4 space-y-3">
                  {clarificationQuestions.map((question, index) => (
                    <label key={question} className="block">
                      <span className="text-sm font-medium text-slate-700">{question}</span>
                      <input
                        value={clarificationAnswers[String(index)] ?? ""}
                        onChange={(e) => setClarificationAnswers((prev) => ({ ...prev, [String(index)]: e.target.value }))}
                        className="mt-2 min-h-11 w-full rounded-xl border border-amber-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:ring-4 focus:ring-amber-500/10"
                      />
                    </label>
                  ))}
                </div>
                <div className="mt-4 flex gap-2">
                  <Button variant="primary" size="md" onClick={() => void handleClarificationSubmit()}>
                    提交并继续规划
                  </Button>
                  <Button variant="secondary" size="md" onClick={handleReset}>
                    重新输入
                  </Button>
                </div>
              </div>
            )}

            <div className="mt-5">
              <KnowledgePanel />
            </div>
          </section>
        )}

        {uiState !== "input" && uiState !== "loading" && uiState !== "clarifying" && (
          <div className="mx-auto max-w-5xl">
            {(uiState === "plan_ready" || uiState === "researching") && plan && (
              <div className="space-y-6">
                <section className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-[0_12px_32px_rgba(23,32,31,0.05)] sm:p-6">
                  <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
                    <div>
                      <p className="text-xs font-medium text-teal-700">执行前确认</p>
                      <h2 className="mt-2 text-2xl font-semibold text-[var(--ink)]">研究计划</h2>
                      <p className="mt-1 text-sm text-slate-500">{plan.title}</p>
                    </div>
                    {uiState === "researching" && (
                      <span className="w-fit rounded-full border border-cyan-700/10 bg-cyan-50 px-3 py-1.5 text-xs font-medium text-cyan-700">
                        第 {currentStep}/{totalSteps} 步
                      </span>
                    )}
                  </div>

                  <div className="space-y-3">
                    {(uiState === "plan_ready" ? editableSteps : plan.steps).map((step, i) => {
                      const stepNum = i + 1;
                      const isCurrent = stepNum === currentStep;
                      const isDone = stepNum < currentStep;
                      return (
                        <div
                          key={`${step.title}-${i}`}
                          className={`flex flex-col gap-3 rounded-xl border p-4 transition-all sm:flex-row sm:items-start ${
                            isCurrent ? "border-teal-300 bg-teal-50" : isDone ? "border-emerald-200 bg-emerald-50/50" : "border-[var(--border)] bg-white"
                          }`}
                        >
                          <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-full text-xs font-semibold ${isDone ? "bg-emerald-500 text-white" : "bg-slate-950 text-white"}`}>
                            {isDone ? "✓" : stepNum}
                          </span>
                          {uiState === "plan_ready" ? (
                            <div className="flex-1 space-y-2">
                              <input
                                value={step.title}
                                onChange={(e) => updateStep(i, { title: e.target.value })}
                                className="min-h-11 w-full rounded-xl border border-[var(--border)] bg-white px-3 py-2 text-sm font-medium text-slate-900 outline-none transition focus:border-[var(--accent)] focus:ring-4 focus:ring-[var(--accent-soft)]"
                              />
                              <textarea
                                value={step.description}
                                onChange={(e) => updateStep(i, { description: e.target.value })}
                                rows={2}
                                className="w-full resize-y rounded-xl border border-[var(--border)] bg-white px-3 py-2 text-sm leading-6 text-slate-600 outline-none transition focus:border-[var(--accent)] focus:ring-4 focus:ring-[var(--accent-soft)]"
                              />
                            </div>
                          ) : (
                            <span className="flex-1 pt-1 text-sm font-medium text-slate-700">{step.title}</span>
                          )}
                          <div className="flex shrink-0 items-center gap-2">
                            <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${step.need_search ? "bg-blue-50 text-blue-700 ring-1 ring-blue-200" : "bg-violet-50 text-violet-700 ring-1 ring-violet-200"}`}>
                              {step.need_search ? "搜索" : "计算"}
                            </span>
                            {uiState === "plan_ready" && (
                              <label className="flex items-center gap-1.5 rounded-full border border-slate-900/10 bg-white/70 px-2.5 py-1 text-[11px] font-medium text-slate-500">
                                <input
                                  type="checkbox"
                                  checked={step.need_search}
                                  onChange={(e) => updateStep(i, { need_search: e.target.checked, step_type: e.target.checked ? "research" : "processing" })}
                                  className="accent-cyan-600"
                                />
                                联网
                              </label>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {uiState === "plan_ready" && (
                    <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
                      <Button variant="primary" size="md" loading={confirmingPlan} onClick={handleConfirmPlan}>
                        {confirmingPlan ? "启动中..." : "确认并执行研究"}
                      </Button>
                      <Button variant="secondary" size="md" disabled={confirmingPlan} onClick={handleRejectPlan}>
                        取消计划
                      </Button>
                    </div>
                  )}

                  {uiState === "researching" && (
                    <div className="mt-5 flex items-center gap-3 rounded-xl border border-teal-200 bg-teal-50 px-4 py-3 text-sm font-medium text-teal-800">
                      <span className="h-2 w-2 animate-pulse rounded-full bg-teal-600" aria-hidden="true" />
                      正在执行第 {currentStep}/{totalSteps} 步...
                    </div>
                  )}
                </section>

                {uiState === "researching" && events.length > 0 && (
                  <Timeline events={events.filter((event) => event.type.startsWith("step.") || event.type === "research.started")} />
                )}
              </div>
            )}

            {uiState === "completed" && report && (
              <div className="space-y-5">
                <StyleSelector taskId={taskId!} currentStyle={reportStyle} onRestyled={handleRestyle} />
                <ReportView key={report.report_id} report={report} onExport={() => undefined} onNewResearch={handleReset} />
                <ArtifactTools taskId={taskId!} />
                <Timeline events={events} />
              </div>
            )}

            {uiState === "error" && (
              <div className="flex min-h-[58vh] flex-col items-center justify-center gap-4 text-center">
                <div className="grid h-14 w-14 place-items-center rounded-full border border-red-200 bg-red-50 text-xl font-bold text-red-500 shadow-sm">!</div>
                <h2 className="text-2xl font-semibold tracking-tight text-slate-950">研究失败</h2>
                <p className="max-w-md text-sm leading-6 text-slate-500">{error || "未知错误"}</p>
                {events.length > 0 && (
                  <div className="mt-4 w-full max-w-lg">
                    <Timeline events={events} />
                  </div>
                )}
                <Button variant="secondary" size="md" onClick={handleReset}>
                  重新开始
                </Button>
              </div>
            )}

            <div className="mt-6">
              <KnowledgePanel />
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
