import type { FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import type { Workflow } from "@/lib/types";

export interface WorkflowFormState {
  name: string;
  description: string;
  nodesText: string;
  edgesText: string;
  budgetText: string;
}

interface WorkflowEditorProps {
  editingWorkflowId: string | null;
  selectedWorkflow: Workflow | null;
  form: WorkflowFormState;
  formError: string | null;
  saving: boolean;
  deleting: boolean;
  onChange: (form: WorkflowFormState) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onDelete: () => void;
  onReset: () => void;
}

export function WorkflowEditor({
  editingWorkflowId,
  selectedWorkflow,
  form,
  formError,
  saving,
  deleting,
  onChange,
  onSubmit,
  onDelete,
  onReset,
}: WorkflowEditorProps) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">{editingWorkflowId ? "编辑工作流" : "创建工作流"}</h2>
          <p className="mt-1 text-sm text-slate-500">节点与连线使用 JSON 配置，先保证可运行，再逐步扩展复杂分支。</p>
        </div>
        {selectedWorkflow && (
          <Button variant="danger" size="sm" loading={deleting} onClick={onDelete}>
            删除
          </Button>
        )}
      </div>

      {formError && (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{formError}</div>
      )}

      <form className="space-y-4" onSubmit={onSubmit}>
        <label className="block">
          <span className="text-xs font-semibold text-slate-500">名称</span>
          <input
            value={form.name}
            onChange={(event) => onChange({ ...form, name: event.target.value })}
            className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
            placeholder="例如：竞品研究标准流程"
          />
        </label>
        <label className="block">
          <span className="text-xs font-semibold text-slate-500">描述</span>
          <textarea
            value={form.description}
            onChange={(event) => onChange({ ...form, description: event.target.value })}
            className="mt-2 min-h-20 w-full resize-none rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm leading-6 outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
            placeholder="说明这个工作流适合什么研究任务"
          />
        </label>

        <div className="grid gap-4 lg:grid-cols-2">
          <JsonEditor
            label="nodes JSON"
            value={form.nodesText}
            onChange={(nodesText) => onChange({ ...form, nodesText })}
            minHeight="min-h-96"
          />
          <div className="grid gap-4">
            <JsonEditor
              label="edges JSON"
              value={form.edgesText}
              onChange={(edgesText) => onChange({ ...form, edgesText })}
              minHeight="min-h-44"
            />
            <JsonEditor
              label="budget JSON"
              value={form.budgetText}
              onChange={(budgetText) => onChange({ ...form, budgetText })}
              minHeight="min-h-44"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-end gap-3 border-t border-slate-100 pt-4">
          <Button variant="secondary" onClick={onReset}>
            重置为新建
          </Button>
          <Button type="submit" variant="primary" loading={saving}>
            {editingWorkflowId ? "保存修改" : "创建工作流"}
          </Button>
        </div>
      </form>
    </section>
  );
}

export function JsonEditor({
  label,
  value,
  onChange,
  minHeight,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  minHeight: string;
}) {
  return (
    <label className="block">
      <span className="text-xs font-semibold text-slate-500">{label}</span>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        spellCheck={false}
        className={`mt-2 w-full resize-y rounded-xl border border-slate-200 bg-white p-3 font-mono text-xs leading-5 text-slate-900 outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10 ${minHeight}`}
      />
    </label>
  );
}
