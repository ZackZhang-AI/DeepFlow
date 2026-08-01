import type { ResearchTask } from "@/lib/types";

interface ProgressEvent {
  type: string;
  data: Record<string, unknown>;
  time: number;
}

export function ResearchProgress({ task, events }: { task: ResearchTask; events: ProgressEvent[] }) {
  const completedSteps = Math.max(0, Math.min(task.current_step, task.total_steps));
  const latestStep = [...events].reverse().find((event) => event.type === "step.started");
  const sourceCount = events.reduce((count, event) => {
    const value = Number(event.data.sources_count ?? 0);
    return Number.isFinite(value) ? Math.max(count, value) : count;
  }, 0);
  const firstTime = events[0]?.time;
  const latestTime = events.at(-1)?.time;
  const elapsed = firstTime && latestTime ? Math.max(0, Math.round((latestTime - firstTime) / 1000)) : 0;

  return (
    <section className="rounded-xl border border-[var(--border)] bg-white p-4 shadow-[0_12px_32px_rgba(23,32,31,0.05)] sm:p-6" aria-labelledby="progress-heading">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 id="progress-heading" className="text-xl font-semibold text-[var(--ink)]">研究进度</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            {latestStep?.data.title ? `正在处理：${String(latestStep.data.title)}` : "正在同步最新执行状态"}
          </p>
        </div>
        <span className="shrink-0 text-sm font-semibold tabular-nums text-teal-700">{Math.round(task.progress || 0)}%</span>
      </div>

      <div className="mt-5 h-2 overflow-hidden rounded-full bg-slate-100" aria-label={`研究完成 ${Math.round(task.progress || 0)}%`}>
        <div className="h-full rounded-full bg-teal-600 transition-[width] duration-500" style={{ width: `${Math.max(2, Math.min(100, task.progress || 0))}%` }} />
      </div>

      <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-5 border-t border-[var(--border)] pt-5 sm:grid-cols-4">
        <div>
          <dt className="text-xs text-[var(--muted)]">当前步骤</dt>
          <dd className="mt-1 text-lg font-semibold text-[var(--ink)]">{Math.min(completedSteps + 1, task.total_steps || 1)}</dd>
        </div>
        <div>
          <dt className="text-xs text-[var(--muted)]">已完成</dt>
          <dd className="mt-1 text-lg font-semibold text-[var(--ink)]">{completedSteps}</dd>
        </div>
        <div>
          <dt className="text-xs text-[var(--muted)]">来源数</dt>
          <dd className="mt-1 text-lg font-semibold text-[var(--ink)]">{sourceCount}</dd>
        </div>
        <div>
          <dt className="text-xs text-[var(--muted)]">本次已用</dt>
          <dd className="mt-1 text-lg font-semibold text-[var(--ink)]">{elapsed}s</dd>
        </div>
      </dl>

      {events.length > 0 && (
        <ol className="mt-6 space-y-2 border-t border-[var(--border)] pt-5">
          {events.slice(-6).map((event, index) => (
            <li key={`${event.type}-${event.time}-${index}`} className="flex min-w-0 items-start gap-3 text-sm">
              <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${event.type.includes("error") ? "bg-red-500" : event.type.includes("completed") ? "bg-emerald-500" : "bg-cyan-500"}`} />
              <span className="min-w-0 break-words text-slate-600">
                {event.type === "step.started" && `开始步骤：${String(event.data.title ?? event.data.step_index ?? "")}`}
                {event.type === "step.completed" && `完成步骤 ${String(event.data.step_index ?? "")}`}
                {event.type === "report.started" && "开始生成报告"}
                {event.type === "research.started" && "研究任务已启动"}
                {!["step.started", "step.completed", "report.started", "research.started"].includes(event.type) && event.type}
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
