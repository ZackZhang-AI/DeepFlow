import type { ResearchTask } from "@/lib/types";
import { DemoBadge } from "@/components/ui/DemoBadge";

const PHASE_LABELS: Record<string, string> = {
  coordinating: "分析研究意图",
  clarifying: "补充研究背景",
  planning: "生成研究计划",
  awaiting_confirmation: "确认研究计划",
  queued: "等待执行",
  researching: "执行研究",
  generating_report: "生成报告",
  reporting: "生成报告",
  completed: "研究完成",
  failed: "研究中断",
};

export function ResearchStatusHeader({ task, connected }: { task: ResearchTask; connected: boolean }) {
  const phase = task.phase || task.status;
  const isActive = !["completed", "failed", "clarifying", "awaiting_confirmation"].includes(task.status);

  return (
    <header className="border-b border-[var(--border)] pb-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${
              task.status === "failed"
                ? "border-red-200 bg-red-50 text-red-700"
                : task.status === "completed"
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                  : "border-cyan-200 bg-cyan-50 text-cyan-700"
            }`}>
              {PHASE_LABELS[phase] ?? phase}
            </span>
            {task.is_demo && <DemoBadge />}
            {isActive && (
              <span className="flex items-center gap-1.5 text-xs text-[var(--muted)]">
                <span className={`h-2 w-2 rounded-full ${connected ? "bg-emerald-500" : "bg-amber-500"}`} aria-hidden="true" />
                {connected ? "实时连接" : "状态轮询"}
              </span>
            )}
          </div>
          <h1 className="mt-3 break-words text-2xl font-semibold leading-tight text-[var(--ink)] sm:text-3xl">{task.topic}</h1>
          <p className="mt-2 text-xs text-[var(--muted)]">任务 ID：{task.task_id}</p>
        </div>
        {task.total_steps > 0 && (
          <div className="shrink-0 text-left sm:text-right">
            <p className="text-2xl font-semibold tabular-nums text-[var(--ink)]">{Math.round(task.progress || 0)}%</p>
            <p className="mt-1 text-xs text-[var(--muted)]">{task.current_step}/{task.total_steps} 个步骤</p>
          </div>
        )}
      </div>
    </header>
  );
}
