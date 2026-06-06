"use client";

interface TimelineEvent {
  type: string;
  data: Record<string, unknown>;
  time: number;
}

interface Props {
  events: TimelineEvent[];
}

const EVENT_LABELS: Record<string, { label: string; color: string }> = {
  "coordinator.started": { label: "分析意图", color: "text-blue-400" },
  "planner.completed": { label: "计划生成", color: "text-cyan-400" },
  "research.started": { label: "开始研究", color: "text-green-400" },
  "step.started": { label: "执行步骤", color: "text-yellow-400" },
  "step.completed": { label: "步骤完成", color: "text-emerald-400" },
  "report.started": { label: "生成报告", color: "text-purple-400" },
  "report.completed": { label: "报告完成", color: "text-pink-400" },
  "error.fatal": { label: "错误", color: "text-red-400" },
};

export function Timeline({ events }: Props) {
  if (events.length === 0) return null;

  return (
    <div className="bg-slate-800/20 border border-slate-800 rounded-xl p-4">
      <h3 className="text-xs font-semibold text-slate-500 mb-3 uppercase tracking-wider">
        执行时间线
      </h3>
      <div className="space-y-2">
        {events.map((event, i) => {
          const info = EVENT_LABELS[event.type] || { label: event.type, color: "text-slate-500" };
          const elapsed =
            i === 0
              ? "0s"
              : `${((event.time - events[0].time) / 1000).toFixed(0)}s`;

          return (
            <div key={i} className="flex items-start gap-3 text-xs">
              {/* Timeline dot */}
              <div className="flex flex-col items-center pt-0.5">
                <div className={`w-2 h-2 rounded-full ${event.type.includes("error") ? "bg-red-500" : event.type.includes("completed") ? "bg-green-500" : "bg-slate-600"}`} />
                {i < events.length - 1 && (
                  <div className="w-px h-full min-h-[16px] bg-slate-700 mt-0.5" />
                )}
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0 pb-2">
                <div className="flex items-center gap-2">
                  <span className={`font-medium ${info.color}`}>{info.label}</span>
                  <span className="text-slate-600 font-mono">+{elapsed}</span>
                </div>
                <div className="text-slate-500 mt-0.5 truncate">
                  {event.type === "step.started" && `步骤 ${event.data.step_index}/${event.data.total_steps}: ${event.data.title}`}
                  {event.type === "step.completed" && `步骤 ${event.data.step_index} 完成 (${event.data.sources_count} 来源)`}
                  {event.type === "planner.completed" && `${event.data.steps_count} 个研究步骤`}
                  {event.type === "report.completed" && `${event.data.sources_count} 来源, ${event.data.tokens_used} tokens`}
                  {event.type === "error.fatal" && `${event.data.message}`}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
