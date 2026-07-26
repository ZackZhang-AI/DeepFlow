import type { Workflow } from "@/lib/types";

function formatDate(value?: string) {
  if (!value) return "未知时间";
  return new Date(value).toLocaleString("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

interface WorkflowListProps {
  workflows: Workflow[];
  selectedWorkflowId: string | null;
  onSelect: (workflowId: string) => void;
}

export function WorkflowList({ workflows, selectedWorkflowId, onSelect }: WorkflowListProps) {
  return (
    <aside className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold">工作流列表</h2>
        <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-600">
          {workflows.length}
        </span>
      </div>
      {workflows.length > 0 ? (
        <div className="space-y-2">
          {workflows.map((workflow) => {
            const active = workflow.workflow_id === selectedWorkflowId;
            return (
              <button
                key={workflow.workflow_id}
                type="button"
                onClick={() => onSelect(workflow.workflow_id)}
                className={`w-full rounded-xl border p-3 text-left transition ${
                  active
                    ? "border-cyan-300 bg-cyan-50 shadow-sm"
                    : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50"
                }`}
              >
                <div className="line-clamp-1 text-sm font-semibold">{workflow.name}</div>
                <div className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">
                  {workflow.description || "暂无描述"}
                </div>
                <div className="mt-2 text-[11px] text-slate-400">{formatDate(workflow.updated_at)}</div>
              </button>
            );
          })}
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
          还没有工作流，可以从默认 Planner 到 Researcher 到 Reporter 开始。
        </div>
      )}
    </aside>
  );
}
