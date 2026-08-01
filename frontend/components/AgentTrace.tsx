"use client";

import { useEffect, useState } from "react";
import { listAgentRuns } from "@/lib/api";
import type { AgentRun } from "@/lib/types";

interface Props {
  taskId: string;
}

export function AgentTrace({ taskId }: Props) {
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    listAgentRuns(taskId)
      .then((data: AgentRun[]) => {
        if (!cancelled) setRuns(data);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "执行日志加载失败");
      });
    return () => {
      cancelled = true;
    };
  }, [open, taskId]);

  return (
    <section className="bg-slate-800/30 border border-slate-700 rounded-xl p-4">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="w-full flex items-center justify-between text-left"
      >
        <span className="text-sm font-semibold text-slate-200">Agent Trace</span>
        <span className="text-xs text-slate-500">{open ? "收起" : "查看"}</span>
      </button>

      {open && (
        <div className="mt-4 space-y-3">
          {error && <div className="text-sm text-red-300">{error}</div>}
          {runs.length === 0 && !error ? (
            <div className="text-sm text-slate-500">暂无执行记录</div>
          ) : (
            runs.map((run) => {
              let tools: { tool?: string; count?: number }[] = [];
              try {
                tools = JSON.parse(run.tool_calls_json || "[]");
              } catch {
                tools = [];
              }
              return (
                <div key={run.run_id} className="border border-slate-700 rounded-lg p-3 bg-slate-900/40">
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <span className="font-semibold text-cyan-300">{run.agent_name}</span>
                    <span className="text-slate-500">{run.phase}</span>
                    <span className={run.status === "completed" ? "text-emerald-300" : "text-red-300"}>
                      {run.status}
                    </span>
                    <span className="text-slate-500">{run.elapsed_seconds.toFixed(1)}s</span>
                    <span className="text-slate-500">
                      {(run.prompt_tokens + run.completion_tokens).toLocaleString()} tokens
                    </span>
                  </div>
                  {tools.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {tools.map((tool, index) => (
                        <span key={index} className="text-[11px] px-2 py-0.5 rounded bg-slate-800 text-slate-400">
                          {tool.tool}: {tool.count ?? 0}
                        </span>
                      ))}
                    </div>
                  )}
                  <p className="mt-2 text-xs text-slate-400 line-clamp-3 whitespace-pre-wrap">
                    {run.output_summary || run.error || run.input_summary}
                  </p>
                </div>
              );
            })
          )}
        </div>
      )}
    </section>
  );
}
