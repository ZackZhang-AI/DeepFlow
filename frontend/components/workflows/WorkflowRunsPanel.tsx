import { Button } from "@/components/ui/Button";
import type { WorkflowNodeRun, WorkflowRun } from "@/lib/types";
import { JsonEditor } from "./WorkflowEditor";

function formatDate(value?: string) {
  if (!value) return "未知时间";
  return new Date(value).toLocaleString("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function statusClass(status: string) {
  if (status === "completed") return "border-emerald-200 bg-emerald-50 text-emerald-700";
  if (status === "failed") return "border-red-200 bg-red-50 text-red-700";
  if (status === "running") return "border-cyan-200 bg-cyan-50 text-cyan-700";
  return "border-slate-200 bg-slate-50 text-slate-600";
}

function compactJson(value: unknown) {
  if (value === null || value === undefined || value === "") return "无";
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

function parseToolCalls(value: string) {
  if (!value) return "[]";
  try {
    return JSON.stringify(JSON.parse(value), null, 2);
  } catch {
    return value;
  }
}

interface WorkflowRunsPanelProps {
  selectedWorkflowId: string | null;
  runInputText: string;
  running: boolean;
  runs: WorkflowRun[];
  selectedRun: WorkflowRun | null;
  trace: WorkflowNodeRun[];
  onRunInputChange: (value: string) => void;
  onRun: () => void;
  onSelectRun: (run: WorkflowRun) => void;
}

export function WorkflowRunsPanel({
  selectedWorkflowId,
  runInputText,
  running,
  runs,
  selectedRun,
  trace,
  onRunInputChange,
  onRun,
  onSelectRun,
}: WorkflowRunsPanelProps) {
  return (
    <aside className="flex flex-col gap-5">
      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">运行工作流</h2>
            <p className="mt-1 text-sm text-slate-500">输入 JSON 需包含 topic。</p>
          </div>
          <Button variant="primary" size="sm" loading={running} disabled={!selectedWorkflowId} onClick={onRun}>
            运行
          </Button>
        </div>
        <JsonEditor label="input JSON" value={runInputText} onChange={onRunInputChange} minHeight="min-h-36" />
        {selectedRun && (
          <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${statusClass(selectedRun.status)}`}>
                {selectedRun.status}
              </span>
              <span className="text-xs text-slate-500">{formatDate(selectedRun.updated_at)}</span>
            </div>
            {selectedRun.error && <div className="mt-3 text-sm text-red-700">{selectedRun.error}</div>}
            <div className="mt-3 text-xs font-semibold text-slate-500">outputs</div>
            <pre className="mt-2 max-h-56 overflow-auto rounded-xl bg-slate-950 p-3 text-xs leading-5 text-slate-100">
              {compactJson(selectedRun.outputs)}
            </pre>
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">运行历史</h2>
          <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-600">
            {runs.length}
          </span>
        </div>
        {runs.length > 0 ? (
          <div className="max-h-64 space-y-2 overflow-auto pr-1">
            {runs.map((run) => {
              const active = run.run_id === selectedRun?.run_id;
              return (
                <button
                  key={run.run_id}
                  type="button"
                  onClick={() => onSelectRun(run)}
                  className={`w-full rounded-xl border p-3 text-left transition ${
                    active ? "border-cyan-300 bg-cyan-50" : "border-slate-200 bg-white hover:bg-slate-50"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${statusClass(run.status)}`}>
                      {run.status}
                    </span>
                    <span className="text-[11px] text-slate-400">{formatDate(run.created_at)}</span>
                  </div>
                  <div className="mt-2 line-clamp-1 font-mono text-[11px] text-slate-500">{run.run_id}</div>
                </button>
              );
            })}
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
            选择工作流后可查看运行记录。
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="text-lg font-semibold">节点 Trace</h2>
        <div className="mt-4 space-y-3">
          {trace.length > 0 ? (
            trace.map((node) => (
              <article key={node.node_run_id} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <div className="text-sm font-semibold">{node.node_id}</div>
                    <div className="mt-0.5 text-xs text-slate-500">{node.node_type}</div>
                  </div>
                  <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${statusClass(node.status)}`}>
                    {node.status}
                  </span>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-500">
                  <div>耗时：{node.elapsed_seconds.toFixed(2)}s</div>
                  <div>{formatDate(node.created_at)}</div>
                </div>
                {node.error && <div className="mt-3 text-sm text-red-700">{node.error}</div>}
                <details className="mt-3">
                  <summary className="cursor-pointer text-xs font-semibold text-slate-500">tool_calls</summary>
                  <pre className="mt-2 max-h-36 overflow-auto rounded-xl bg-slate-950 p-3 text-xs leading-5 text-slate-100">
                    {parseToolCalls(node.tool_calls_json)}
                  </pre>
                </details>
              </article>
            ))
          ) : (
            <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
              运行后会显示每个节点的状态、工具调用、耗时和错误。
            </div>
          )}
        </div>
      </section>
    </aside>
  );
}
