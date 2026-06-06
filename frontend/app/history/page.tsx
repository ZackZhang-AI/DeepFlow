"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import type { ResearchTask, Report } from "@/lib/types";

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  coordinating: { label: "分析中", color: "text-blue-400" },
  planning: { label: "规划中", color: "text-cyan-400" },
  researching: { label: "研究中", color: "text-yellow-400" },
  generating_report: { label: "生成报告", color: "text-purple-400" },
  completed: { label: "已完成", color: "text-green-400" },
  failed: { label: "失败", color: "text-red-400" },
  awaiting_confirmation: { label: "待确认", color: "text-orange-400" },
};

export default function HistoryPage() {
  const [tasks, setTasks] = useState<ResearchTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTask, setSelectedTask] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);

  useEffect(() => {
    fetch("http://localhost:8000/api/research-tasks?limit=50")
      .then((r) => r.json())
      .then((data) => {
        setTasks(data as ResearchTask[]);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const viewReport = async (taskId: string) => {
    setSelectedTask(taskId);
    try {
      const r = await fetch(`http://localhost:8000/api/reports/${taskId}`);
      if (r.ok) {
        setReport(await r.json());
      }
    } catch {
      // Report not ready
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-950 to-slate-900 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <Link href="/" className="text-xl font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
              DeepFlow
            </Link>
            <nav className="flex gap-4 text-sm">
              <Link href="/" className="text-slate-400 hover:text-slate-200 transition-colors">
                研究
              </Link>
              <span className="text-cyan-400">历史</span>
            </nav>
          </div>
          <span className="text-xs text-slate-500">AI 深度研究</span>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold">研究历史</h2>
          <Link
            href="/"
            className="px-4 py-2 bg-gradient-to-r from-cyan-500 to-blue-600 rounded-lg text-sm font-medium hover:from-cyan-400 hover:to-blue-500 transition-all"
          >
            新的研究
          </Link>
        </div>

        {loading ? (
          <div className="flex justify-center py-12">
            <div className="w-6 h-6 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : tasks.length === 0 ? (
          <div className="text-center py-12 text-slate-500">
            <p className="text-lg mb-2">暂无研究记录</p>
            <Link href="/" className="text-cyan-400 hover:underline text-sm">
              开始第一次研究
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {tasks.map((task) => {
              const status = STATUS_MAP[task.status] || { label: task.status, color: "text-slate-400" };
              const date = new Date(task.created_at).toLocaleString("zh-CN", {
                month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
              });

              return (
                <div
                  key={task.task_id}
                  className={`bg-slate-800/30 border rounded-xl p-5 transition-all cursor-pointer ${
                    selectedTask === task.task_id
                      ? "border-cyan-500/50 bg-slate-800/50"
                      : "border-slate-800 hover:border-slate-700"
                  }`}
                  onClick={() => task.status === "completed" && viewReport(task.task_id)}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-medium truncate">{task.topic}</h3>
                      <div className="flex items-center gap-3 mt-2 text-xs text-slate-500">
                        <span>{date}</span>
                        {task.total_steps > 0 && (
                          <span>{task.current_step}/{task.total_steps} 步</span>
                        )}
                        <span className={`${status.color}`}>{status.label}</span>
                      </div>
                    </div>
                    {task.status === "completed" && (
                      <span className="text-xs text-cyan-400 shrink-0">
                        {selectedTask === task.task_id ? "收起" : "查看报告 →"}
                      </span>
                    )}
                    {task.status === "failed" && (
                      <span className="text-xs text-red-400 shrink-0">查看错误</span>
                    )}
                  </div>

                  {/* Inline report preview */}
                  {selectedTask === task.task_id && report && (
                    <div className="mt-4 pt-4 border-t border-slate-700">
                      <div className="text-sm text-slate-300 space-y-2 max-h-64 overflow-y-auto">
                        <p className="font-medium text-cyan-400">{report.title}</p>
                        <div className="flex gap-4 text-xs text-slate-500">
                          <span>{report.sources_count} 来源</span>
                          <span>{(report.tokens_used / 1000).toFixed(1)}K tokens</span>
                          <span>¥{report.cost_rmb.toFixed(2)}</span>
                        </div>
                        <pre className="text-xs text-slate-400 whitespace-pre-wrap font-sans line-clamp-6">
                          {report.content_markdown.slice(0, 500)}...
                        </pre>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </main>
  );
}
