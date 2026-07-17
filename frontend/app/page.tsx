"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
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
import { ReportView } from "@/components/ReportView";
import { StyleSelector } from "@/components/StyleSelector";
import { Timeline } from "@/components/Timeline";
import { Button, getButtonClasses } from "@/components/ui/Button";
import type { ResearchPlan, ResearchStep, Report } from "@/lib/types";

type UIState = "input" | "loading" | "clarifying" | "plan_ready" | "researching" | "completed" | "error";
type ResearchDepth = "fast" | "standard" | "deep";

const QUICK_PROMPTS = [
  {
    id: "market",
    label: "市场分析",
    prompt: "分析某个市场的发展趋势、主要玩家和商业化机会",
  },
  {
    id: "competitor",
    label: "竞品研究",
    prompt: "对比分析几个产品的定位、功能、商业模式和优劣势",
  },
  {
    id: "tech",
    label: "技术调研",
    prompt: "调研某项技术的原理、应用场景、代表产品和发展趋势",
  },
] as const;

const RESEARCH_DEPTHS: Array<{
  id: ResearchDepth;
  title: string;
  time: string;
  description: string;
  maxSteps: number;
}> = [
  { id: "fast", title: "快速研究", time: "约 3 分钟", description: "适合快速了解", maxSteps: 3 },
  { id: "standard", title: "标准研究", time: "约 8 分钟", description: "适合常规分析", maxSteps: 5 },
  { id: "deep", title: "深度研究", time: "约 15 分钟", description: "适合完整报告", maxSteps: 8 },
];

function ArrowRightIcon() {
  return (
    <svg aria-hidden="true" className="h-4 w-4" viewBox="0 0 20 20" fill="none">
      <path d="M4 10h11m0 0-4-4m4 4-4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

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
    const matchedPrompt = QUICK_PROMPTS.find((item) => item.prompt === value);
    setSelectedQuickPrompt(matchedPrompt?.id ?? null);
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
      <main className="relative grid min-h-screen place-items-center overflow-hidden bg-[#f7f8f4] text-slate-950">
        <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_18%_8%,rgba(70,188,196,0.20),transparent_34%),radial-gradient(circle_at_82%_16%,rgba(102,144,255,0.16),transparent_32%),linear-gradient(180deg,#fbfbf7_0%,#eef6f6_48%,#f7f8f4_100%)]" />
        <div className="flex items-center gap-3 rounded-2xl border border-white/70 bg-white/72 px-5 py-4 text-sm font-medium text-slate-600 shadow-[0_18px_55px_rgba(15,23,42,0.10)] backdrop-blur-xl">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent" />
          正在确认登录状态...
        </div>
      </main>
    );
  }

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#f7f8f4] text-slate-950">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_18%_8%,rgba(70,188,196,0.24),transparent_34%),radial-gradient(circle_at_82%_16%,rgba(102,144,255,0.18),transparent_32%),linear-gradient(180deg,#fbfbf7_0%,#eef6f6_48%,#f7f8f4_100%)]" />
      <div className="pointer-events-none absolute inset-0 -z-10 opacity-[0.45] [background-image:linear-gradient(rgba(15,23,42,0.055)_1px,transparent_1px),linear-gradient(90deg,rgba(15,23,42,0.055)_1px,transparent_1px)] [background-size:42px_42px]" />

      <header className="sticky top-0 z-30 border-b border-slate-900/10 bg-white/72 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
          <div className="flex items-center gap-6">
            <Link href="/" className="group flex items-center gap-2">
              <span className="grid h-8 w-8 place-items-center rounded-xl border border-cyan-500/20 bg-gradient-to-br from-cyan-50 to-blue-50 text-sm font-black text-cyan-700 shadow-sm shadow-cyan-900/5">D</span>
              <span className="text-lg font-semibold tracking-tight text-slate-950">DeepFlow</span>
            </Link>
            <nav className="hidden items-center rounded-2xl border border-slate-200 bg-white/55 p-1 text-sm shadow-sm shadow-slate-900/[0.03] sm:flex">
              <span className={getButtonClasses({ variant: "ghost", size: "sm", className: "min-h-9 bg-slate-950 text-white hover:bg-slate-950 hover:text-white" })}>研究</span>
              <Link href="/history" className={getButtonClasses({ variant: "ghost", size: "sm", className: "min-h-9" })}>资产</Link>
            </nav>
          </div>
          <span className="rounded-full border border-cyan-700/10 bg-cyan-50/70 px-3 py-1.5 text-xs font-medium text-slate-600 shadow-sm shadow-cyan-900/5">
            AI 深度研究工作台
          </span>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-4 pb-14 pt-8 sm:px-6 sm:pt-12">
        {(uiState === "input" || uiState === "loading" || uiState === "clarifying") && (
          <section className="mx-auto flex min-h-[calc(100vh-112px)] max-w-4xl flex-col justify-center gap-8 py-8">
            <div className="text-center">
              <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-slate-900/10 bg-white/60 px-3 py-1.5 text-xs font-medium text-slate-600 shadow-sm backdrop-blur">
                <span className="h-1.5 w-1.5 rounded-full bg-cyan-500 shadow-[0_0_12px_rgba(6,182,212,0.7)]" />
                私域资料 + Agent 研究闭环
              </div>
              <h1 className="mx-auto max-w-4xl text-balance text-4xl font-semibold tracking-tight text-slate-950 sm:text-5xl lg:text-6xl">
                把复杂问题交给 <span className="bg-gradient-to-r from-cyan-600 via-teal-500 to-blue-600 bg-clip-text text-transparent">DeepFlow</span>，生成可信研究报告
              </h1>
              <p className="mx-auto mt-5 max-w-2xl text-pretty text-base leading-7 text-slate-600 sm:text-lg">
                输入研究主题，AI Agent 会规划路径、检索资料、整合私域知识，并输出结构化 Markdown 报告。
              </p>
            </div>

            <div className="rounded-[2rem] border border-white/70 bg-white/58 p-3 shadow-[0_28px_90px_rgba(15,23,42,0.12)] backdrop-blur-2xl">
              <div className="rounded-[1.55rem] border border-slate-900/10 bg-white/80 p-4 shadow-inner shadow-white transition-all focus-within:border-cyan-500/35 sm:p-5">
                <textarea
                  value={topic}
                  onChange={(e) => handleTopicChange(e.target.value)}
                  onKeyDown={handleKeyDown}
                  disabled={isPlanning}
                  placeholder="例如：分析 2026 年 AI Agent 市场发展趋势、主要玩家与商业化机会..."
                  className="min-h-32 w-full resize-none bg-transparent px-1 py-1 text-base leading-7 text-slate-950 placeholder:text-slate-400 focus:outline-none disabled:cursor-not-allowed disabled:opacity-60 sm:text-lg"
                  rows={4}
                />
                <div className="mt-4 grid gap-3 border-t border-slate-900/10 pt-4 sm:grid-cols-2">
                  <input
                    value={sourceDomains}
                    onChange={(e) => setSourceDomains(e.target.value)}
                    placeholder="限定来源域名，可选，用逗号分隔"
                    className="rounded-2xl border border-slate-200 bg-white/75 px-3 py-2 text-sm text-slate-900 outline-none focus:ring-4 focus:ring-cyan-500/10"
                  />
                  <input
                    value={recencyDays}
                    onChange={(e) => setRecencyDays(e.target.value.replace(/\D/g, ""))}
                    placeholder="优先近 N 天资料，可选"
                    className="rounded-2xl border border-slate-200 bg-white/75 px-3 py-2 text-sm text-slate-900 outline-none focus:ring-4 focus:ring-cyan-500/10"
                  />
                </div>
                <div className="mt-4 flex flex-col gap-4 border-t border-slate-900/10 pt-4">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex flex-wrap gap-2">
                      {QUICK_PROMPTS.map((item) => (
                        <Button
                          key={item.id}
                          variant="ghost"
                          size="sm"
                          disabled={isPlanning}
                          onClick={() => handleQuickPrompt(item.id, item.prompt)}
                          className={selectedQuickPrompt === item.id ? "border-cyan-300 bg-cyan-50 text-cyan-800 shadow-sm" : "bg-slate-50/60"}
                        >
                          {item.label}
                        </Button>
                      ))}
                    </div>
                    <Button
                      variant="primary"
                      size="lg"
                      loading={isPlanning}
                      disabled={!topic.trim() || uiState === "clarifying"}
                      onClick={handleSubmit}
                      iconRight={<ArrowRightIcon />}
                      className="w-full sm:w-auto sm:min-w-44"
                    >
                      {isPlanning ? "正在规划研究..." : "生成研究报告"}
                    </Button>
                  </div>

                  <div className="grid gap-2 rounded-2xl border border-slate-200 bg-slate-50/70 p-2 sm:grid-cols-3">
                    {RESEARCH_DEPTHS.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        disabled={isPlanning}
                        onClick={() => setResearchDepth(item.id)}
                        className={`min-h-16 rounded-xl border px-3 py-2 text-left transition-all disabled:pointer-events-none disabled:opacity-50 ${
                          researchDepth === item.id
                            ? "border-cyan-300 bg-white text-slate-950 shadow-sm"
                            : "border-transparent text-slate-500 hover:border-slate-200 hover:bg-white/75 hover:text-slate-800"
                        }`}
                      >
                        <span className="block text-sm font-semibold">{item.title}</span>
                        <span className="mt-0.5 block text-xs font-medium text-cyan-700">{item.time}</span>
                        <span className="mt-1 block text-xs text-slate-500">{item.description}</span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {uiState === "clarifying" && (
              <div className="rounded-3xl border border-amber-200 bg-amber-50/80 p-5 shadow-[0_18px_55px_rgba(15,23,42,0.07)]">
                <h2 className="text-lg font-semibold text-slate-950">还需要补充一点上下文</h2>
                <div className="mt-4 space-y-3">
                  {clarificationQuestions.map((question, index) => (
                    <label key={question} className="block">
                      <span className="text-sm font-medium text-slate-700">{question}</span>
                      <input
                        value={clarificationAnswers[String(index)] ?? ""}
                        onChange={(e) => setClarificationAnswers((prev) => ({ ...prev, [String(index)]: e.target.value }))}
                        className="mt-2 w-full rounded-2xl border border-amber-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:ring-4 focus:ring-amber-500/10"
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

            <KnowledgePanel />
          </section>
        )}

        {uiState !== "input" && uiState !== "loading" && uiState !== "clarifying" && (
          <div className="mx-auto max-w-5xl">
            <div className="mb-6">
              <KnowledgePanel />
            </div>

            {(uiState === "plan_ready" || uiState === "researching") && plan && (
              <div className="space-y-6">
                <section className="rounded-3xl border border-white/70 bg-white/70 p-5 shadow-[0_24px_70px_rgba(15,23,42,0.10)] backdrop-blur-xl sm:p-6">
                  <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-700">Research Plan</p>
                      <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">研究计划</h2>
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
                          className={`flex flex-col gap-3 rounded-2xl border p-4 transition-all sm:flex-row sm:items-start ${
                            isCurrent ? "border-cyan-400/50 bg-cyan-50/70" : isDone ? "border-emerald-200/70 bg-emerald-50/50" : "border-slate-900/10 bg-white/70"
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
                                className="w-full rounded-xl border border-slate-900/10 bg-white/80 px-3 py-2 text-sm font-medium text-slate-900 shadow-sm transition focus:border-cyan-500/50 focus:outline-none focus:ring-4 focus:ring-cyan-500/10"
                              />
                              <textarea
                                value={step.description}
                                onChange={(e) => updateStep(i, { description: e.target.value })}
                                rows={2}
                                className="w-full resize-y rounded-xl border border-slate-900/10 bg-white/80 px-3 py-2 text-sm leading-6 text-slate-600 shadow-sm transition focus:border-cyan-500/50 focus:outline-none focus:ring-4 focus:ring-cyan-500/10"
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
                    <div className="mt-5 flex items-center gap-3 rounded-2xl border border-cyan-700/10 bg-cyan-50/70 px-4 py-3 text-sm font-medium text-cyan-800">
                      <div className="h-4 w-4 animate-spin rounded-full border-2 border-cyan-600 border-t-transparent" />
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
          </div>
        )}
      </div>
    </main>
  );
}
