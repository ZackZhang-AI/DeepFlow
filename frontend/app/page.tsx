"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { createResearch, getReport, subscribeToEvents } from "@/lib/api";
import { ReportView } from "@/components/ReportView";
import { Timeline } from "@/components/Timeline";
import { StyleSelector } from "@/components/StyleSelector";
import { ArtifactTools } from "@/components/ArtifactTools";
import type { ResearchPlan, Report } from "@/lib/types";

type UIState = "input" | "loading" | "plan_ready" | "researching" | "completed" | "error";

export default function Home() {
  const [uiState, setUiState] = useState<UIState>("input");
  const [topic, setTopic] = useState("");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [plan, setPlan] = useState<ResearchPlan | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [reportStyle, setReportStyle] = useState("general");
  const [events, setEvents] = useState<{ type: string; data: Record<string, unknown>; time: number }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [totalSteps, setTotalSteps] = useState(0);

  const handleSubmit = useCallback(async () => {
    if (!topic.trim()) return;
    setUiState("loading");
    setError(null);
    setEvents([]);
    setReport(null);
    setPlan(null);

    try {
      const t = await createResearch(topic.trim());
      setTaskId(t.task_id);

      subscribeToEvents(
        t.task_id,
        (type, data) => {
          setEvents((prev) => [...prev, { type, data, time: Date.now() }]);

          if (type === "planner.completed") {
            setPlan((data.plan ?? data) as unknown as ResearchPlan);
            setTotalSteps((data.steps_count as number) ?? 5);
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
            getReport(t.task_id).then((rep: Report) => {
              setReport(rep);
              setUiState("completed");
            });
          } else if (type === "error.fatal") {
            setError((data.message as string) ?? "未知错误");
            setUiState("error");
          }
        },
        (err) => console.error("SSE:", err)
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "未知错误");
      setUiState("error");
    }
  }, [topic, totalSteps]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleReset = () => {
    setUiState("input");
    setTopic("");
    setTaskId(null);
    setPlan(null);
    setReport(null);
    setEvents([]);
    setError(null);
    setCurrentStep(0);
    setTotalSteps(0);
  };

  const handleExport = (format: string) => {
    console.log(`Exporting as ${format}`);
  };

  const handleRestyle = (style: string, markdown: string) => {
    setReportStyle(style);
    if (report) {
      setReport({ ...report, content_markdown: markdown });
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-950 to-slate-900 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <h1 className="text-xl font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
              DeepFlow
            </h1>
            <nav className="flex gap-4 text-sm">
              <span className="text-cyan-400">研究</span>
              <Link href="/history" className="text-slate-400 hover:text-slate-200 transition-colors">
                历史
              </Link>
            </nav>
          </div>
          <span className="text-xs text-slate-500">AI 深度研究</span>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-4 py-8">
        {/* Input */}
        {uiState === "input" && (
          <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6">
            <div className="text-center space-y-3">
              <h2 className="text-3xl font-bold">开始你的深度研究</h2>
              <p className="text-slate-400 max-w-md">
                输入一个研究主题，AI Agent 将自动完成资料收集、分析和报告撰写
              </p>
            </div>
            <div className="w-full max-w-2xl">
              <textarea
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="例如：分析 2026 年 AI Agent 市场发展趋势..."
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500 resize-none"
                rows={3}
              />
            </div>
            <button
              onClick={handleSubmit}
              disabled={!topic.trim()}
              className="px-8 py-3 bg-gradient-to-r from-cyan-500 to-blue-600 rounded-lg font-medium hover:from-cyan-400 hover:to-blue-500 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              开始研究
            </button>
            <div className="text-xs text-slate-600 space-x-4">
              <span>快速研究 ≈ 3 分钟</span><span>·</span>
              <span>标准研究 ≈ 8 分钟</span><span>·</span>
              <span>深度研究 ≈ 15 分钟</span>
            </div>
          </div>
        )}

        {/* Loading */}
        {uiState === "loading" && (
          <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
            <div className="w-8 h-8 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
            <p className="text-slate-400">正在分析研究主题...</p>
            <p className="text-sm text-slate-600">{topic}</p>
          </div>
        )}

        {/* Plan + Researching */}
        {(uiState === "plan_ready" || uiState === "researching") && plan && (
          <div className="space-y-6">
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
              <h2 className="text-lg font-semibold mb-1">研究计划</h2>
              <h3 className="text-cyan-400 font-medium mb-4">{plan.title}</h3>
              <div className="space-y-2">
                {plan.steps.map((step, i) => {
                  const stepNum = i + 1;
                  const isCurrent = stepNum === currentStep;
                  const isDone = stepNum < currentStep;
                  return (
                    <div
                      key={i}
                      className={`flex items-center gap-3 p-3 rounded-lg transition-colors ${
                        isCurrent
                          ? "bg-cyan-500/10 border border-cyan-500/30"
                          : isDone
                          ? "bg-slate-800/50 text-slate-400"
                          : "bg-slate-800/30"
                      }`}
                    >
                      <span className="text-xs font-mono w-6 h-6 rounded-full flex items-center justify-center bg-slate-700 text-slate-300 shrink-0">
                        {isDone ? "✓" : stepNum}
                      </span>
                      <span className="flex-1 text-sm">{step.title}</span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                        step.need_search
                          ? "bg-blue-500/20 text-blue-300"
                          : "bg-purple-500/20 text-purple-300"
                      }`}>
                        {step.need_search ? "搜索" : "计算"}
                      </span>
                    </div>
                  );
                })}
              </div>
              {uiState === "researching" && (
                <div className="mt-4 flex items-center gap-3 text-sm text-slate-400">
                  <div className="w-4 h-4 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
                  正在执行第 {currentStep}/{totalSteps} 步...
                </div>
              )}
            </div>

            {uiState === "researching" && events.length > 0 && (
              <Timeline events={events.filter(e => e.type.startsWith("step.") || e.type === "research.started")} />
            )}
          </div>
        )}

        {/* Completed: Report */}
        {uiState === "completed" && report && (
          <div className="space-y-4">
            <StyleSelector
              taskId={taskId!}
              currentStyle={reportStyle}
              onRestyled={handleRestyle}
            />
            <ReportView
              report={report}
              onExport={handleExport}
              onNewResearch={handleReset}
            />
            <ArtifactTools taskId={taskId!} report={report} />
            <Timeline events={events} />
          </div>
        )}

        {/* Error */}
        {uiState === "error" && (
          <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
            <div className="w-12 h-12 rounded-full bg-red-500/10 border border-red-500/30 flex items-center justify-center text-red-400 text-xl font-bold">
              !
            </div>
            <h2 className="text-xl font-bold text-red-400">研究失败</h2>
            <p className="text-slate-400 text-sm max-w-md text-center">{error || "未知错误"}</p>
            {events.length > 0 && (
              <div className="mt-4 w-full max-w-lg">
                <Timeline events={events} />
              </div>
            )}
            <button
              onClick={handleReset}
              className="px-6 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm hover:border-slate-500 transition-all"
            >
              重新开始
            </button>
          </div>
        )}
      </div>
    </main>
  );
}
