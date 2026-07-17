"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  createWorkflow,
  deleteWorkflow,
  getAuthToken,
  getWorkflow,
  listWorkflowRuns,
  listWorkflows,
  listWorkflowTrace,
  redirectToLogin,
  runWorkflow,
  updateWorkflow,
} from "@/lib/api";
import { Button, getButtonClasses } from "@/components/ui/Button";
import type { Workflow, WorkflowNodeRun, WorkflowRun } from "@/lib/types";

interface WorkflowFormState {
  name: string;
  description: string;
  nodesText: string;
  edgesText: string;
  budgetText: string;
}

const DEFAULT_NODES: Record<string, unknown>[] = [
  {
    id: "planner",
    type: "Planner",
    label: "规划研究问题",
    config: { output_schema: "research_plan" },
  },
  {
    id: "researcher",
    type: "Researcher",
    label: "检索公开资料与私域知识库",
    config: { tools: ["web_search", "knowledge_search"] },
  },
  {
    id: "reporter",
    type: "Reporter",
    label: "生成结构化报告",
    config: { report_style: "general" },
  },
];

const DEFAULT_EDGES: Record<string, unknown>[] = [
  { from: "planner", to: "researcher", condition: "success" },
  { from: "researcher", to: "reporter", condition: "success" },
];

const DEFAULT_BUDGET: Record<string, unknown> = {
  max_steps: 6,
  max_retries: 1,
  max_search_calls: 8,
  max_tokens_budget: 20000,
};

const EMPTY_FORM: WorkflowFormState = {
  name: "",
  description: "",
  nodesText: JSON.stringify(DEFAULT_NODES, null, 2),
  edgesText: JSON.stringify(DEFAULT_EDGES, null, 2),
  budgetText: JSON.stringify(DEFAULT_BUDGET, null, 2),
};

const DEFAULT_RUN_INPUT = JSON.stringify({ topic: "AI Agent 在企业知识管理中的应用" }, null, 2);

function formatDate(value?: string) {
  if (!value) return "未知时间";
  return new Date(value).toLocaleString("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function parseJsonObject(value: string, fieldName: string) {
  try {
    const parsed = JSON.parse(value);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error(`${fieldName} 必须是 JSON 对象`);
    }
    return parsed as Record<string, unknown>;
  } catch (err) {
    throw new Error(err instanceof Error ? err.message : `${fieldName} JSON 格式错误`);
  }
}

function parseJsonArray(value: string, fieldName: string) {
  try {
    const parsed = JSON.parse(value);
    if (!Array.isArray(parsed)) {
      throw new Error(`${fieldName} 必须是 JSON 数组`);
    }
    return parsed as Record<string, unknown>[];
  } catch (err) {
    throw new Error(err instanceof Error ? err.message : `${fieldName} JSON 格式错误`);
  }
}

function toFormState(workflow: Workflow): WorkflowFormState {
  return {
    name: workflow.name,
    description: workflow.description,
    nodesText: JSON.stringify(workflow.nodes ?? DEFAULT_NODES, null, 2),
    edgesText: JSON.stringify(workflow.edges ?? DEFAULT_EDGES, null, 2),
    budgetText: JSON.stringify(workflow.budget ?? DEFAULT_BUDGET, null, 2),
  };
}

function buildWorkflowPayload(form: WorkflowFormState): Partial<Workflow> {
  if (!form.name.trim()) throw new Error("请填写工作流名称");
  return {
    name: form.name.trim(),
    description: form.description.trim(),
    nodes: parseJsonArray(form.nodesText, "nodes"),
    edges: parseJsonArray(form.edgesText, "edges"),
    budget: parseJsonObject(form.budgetText, "budget"),
  };
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

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [selectedWorkflow, setSelectedWorkflow] = useState<Workflow | null>(null);
  const [editingWorkflowId, setEditingWorkflowId] = useState<string | null>(null);
  const [form, setForm] = useState<WorkflowFormState>(EMPTY_FORM);
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<WorkflowRun | null>(null);
  const [trace, setTrace] = useState<WorkflowNodeRun[]>([]);
  const [runInputText, setRunInputText] = useState(DEFAULT_RUN_INPUT);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const selectedWorkflowId = selectedWorkflow?.workflow_id ?? null;
  const hasWorkflows = workflows.length > 0;

  const selectedSummary = useMemo(
    () => workflows.find((workflow) => workflow.workflow_id === selectedWorkflowId) ?? null,
    [selectedWorkflowId, workflows],
  );

  const loadWorkflows = useCallback(async () => {
    try {
      const loaded = await listWorkflows();
      setWorkflows(loaded);
      if (!selectedWorkflowId && loaded.length > 0) {
        const first = await getWorkflow(loaded[0].workflow_id);
        setSelectedWorkflow(first);
        setForm(toFormState(first));
        setEditingWorkflowId(first.workflow_id);
      }
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "工作流列表加载失败");
    } finally {
      setLoading(false);
    }
  }, [selectedWorkflowId]);

  const loadRuns = useCallback(async (workflowId: string) => {
    try {
      const loadedRuns = await listWorkflowRuns(workflowId);
      setRuns(loadedRuns);
      if (loadedRuns.length > 0) {
        setSelectedRun(loadedRuns[0]);
        const loadedTrace = await listWorkflowTrace(loadedRuns[0].run_id);
        setTrace(loadedTrace);
      } else {
        setSelectedRun(null);
        setTrace([]);
      }
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "运行历史加载失败");
    }
  }, []);

  useEffect(() => {
    if (!getAuthToken()) {
      redirectToLogin();
      return;
    }
    const timer = window.setTimeout(() => {
      void loadWorkflows();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadWorkflows]);

  useEffect(() => {
    if (!selectedWorkflowId) return;
    const timer = window.setTimeout(() => {
      void loadRuns(selectedWorkflowId);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadRuns, selectedWorkflowId]);

  const selectWorkflow = async (workflowId: string) => {
    setPageError(null);
    setFormError(null);
    try {
      const detail = await getWorkflow(workflowId);
      setSelectedWorkflow(detail);
      setEditingWorkflowId(detail.workflow_id);
      setForm(toFormState(detail));
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "工作流详情加载失败");
    }
  };

  const resetForCreate = () => {
    setSelectedWorkflow(null);
    setEditingWorkflowId(null);
    setForm(EMPTY_FORM);
    setRuns([]);
    setSelectedRun(null);
    setTrace([]);
    setFormError(null);
    setPageError(null);
  };

  const saveWorkflow = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    setFormError(null);
    setPageError(null);
    try {
      const payload = buildWorkflowPayload(form);
      const saved = editingWorkflowId
        ? await updateWorkflow(editingWorkflowId, payload)
        : await createWorkflow(payload);
      setSelectedWorkflow(saved);
      setEditingWorkflowId(saved.workflow_id);
      setForm(toFormState(saved));
      setWorkflows((current) => {
        const exists = current.some((item) => item.workflow_id === saved.workflow_id);
        return exists ? current.map((item) => (item.workflow_id === saved.workflow_id ? saved : item)) : [saved, ...current];
      });
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "工作流保存失败");
    } finally {
      setSaving(false);
    }
  };

  const removeWorkflow = async (workflowId: string) => {
    setDeletingId(workflowId);
    setPageError(null);
    try {
      await deleteWorkflow(workflowId);
      setWorkflows((current) => current.filter((item) => item.workflow_id !== workflowId));
      if (selectedWorkflowId === workflowId) resetForCreate();
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "工作流删除失败");
    } finally {
      setDeletingId(null);
    }
  };

  const executeWorkflow = async () => {
    if (!selectedWorkflowId) {
      setPageError("请先选择或创建一个工作流");
      return;
    }
    setRunning(true);
    setPageError(null);
    try {
      const input = parseJsonObject(runInputText, "运行输入");
      const createdRun = await runWorkflow(selectedWorkflowId, input);
      setSelectedRun(createdRun);
      setRuns((current) => [createdRun, ...current.filter((item) => item.run_id !== createdRun.run_id)]);
      const loadedTrace = await listWorkflowTrace(createdRun.run_id);
      setTrace(loadedTrace);
      await loadRuns(selectedWorkflowId);
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "工作流运行失败");
    } finally {
      setRunning(false);
    }
  };

  const selectRun = async (run: WorkflowRun) => {
    setSelectedRun(run);
    setPageError(null);
    try {
      const loadedTrace = await listWorkflowTrace(run.run_id);
      setTrace(loadedTrace);
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "节点 Trace 加载失败");
    }
  };

  return (
    <main className="min-h-screen bg-[#f7f8f4] text-slate-950">
      <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-5 sm:px-6 lg:px-8">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <Link href="/" className="flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-xl border border-cyan-500/20 bg-cyan-50 text-sm font-black text-cyan-700">
              D
            </span>
            <span className="text-lg font-semibold tracking-tight">DeepFlow</span>
          </Link>
          <nav className="flex items-center gap-2">
            <Link href="/tools" className={getButtonClasses({ variant: "ghost", size: "sm", className: "min-h-9" })}>
              工具管理
            </Link>
            <Link href="/history" className={getButtonClasses({ variant: "ghost", size: "sm", className: "min-h-9" })}>
              资产中心
            </Link>
            <Link href="/" className={getButtonClasses({ variant: "secondary", size: "sm", className: "min-h-9" })}>
              返回研究台
            </Link>
          </nav>
        </header>

        <section className="rounded-2xl border border-slate-200 bg-white/80 p-5 shadow-sm">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-700">Agent Workflow</p>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight">自定义 Agent 工作流</h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                用配置式节点串联 Planner、Researcher、Reporter、Coder、Artifact、Human Feedback 与 MCP Tool，适合保存可复用研究流程。
              </p>
            </div>
            <Button variant="primary" onClick={resetForCreate}>
              新建工作流
            </Button>
          </div>
        </section>

        {pageError && (
          <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {pageError}
          </div>
        )}

        {loading ? (
          <div className="grid min-h-80 place-items-center rounded-2xl border border-slate-200 bg-white/70">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent" />
          </div>
        ) : (
          <div className="grid gap-5 xl:grid-cols-[280px_minmax(0,1fr)_420px]">
            <aside className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="mb-4 flex items-center justify-between gap-3">
                <h2 className="text-base font-semibold">工作流列表</h2>
                <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-600">
                  {workflows.length}
                </span>
              </div>
              {hasWorkflows ? (
                <div className="space-y-2">
                  {workflows.map((workflow) => {
                    const active = workflow.workflow_id === selectedWorkflowId;
                    return (
                      <button
                        key={workflow.workflow_id}
                        type="button"
                        onClick={() => void selectWorkflow(workflow.workflow_id)}
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

            <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold">{editingWorkflowId ? "编辑工作流" : "创建工作流"}</h2>
                  <p className="mt-1 text-sm text-slate-500">
                    节点与连线使用 JSON 配置，先保证可运行，再逐步扩展复杂分支。
                  </p>
                </div>
                {selectedSummary && (
                  <Button
                    variant="danger"
                    size="sm"
                    loading={deletingId === selectedSummary.workflow_id}
                    onClick={() => void removeWorkflow(selectedSummary.workflow_id)}
                  >
                    删除
                  </Button>
                )}
              </div>

              {formError && (
                <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {formError}
                </div>
              )}

              <form className="space-y-4" onSubmit={(event) => void saveWorkflow(event)}>
                <label className="block">
                  <span className="text-xs font-semibold text-slate-500">名称</span>
                  <input
                    value={form.name}
                    onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                    className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
                    placeholder="例如：竞品研究标准流程"
                  />
                </label>
                <label className="block">
                  <span className="text-xs font-semibold text-slate-500">描述</span>
                  <textarea
                    value={form.description}
                    onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
                    className="mt-2 min-h-20 w-full resize-none rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm leading-6 outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-500/10"
                    placeholder="说明这个工作流适合什么研究任务"
                  />
                </label>

                <div className="grid gap-4 lg:grid-cols-2">
                  <JsonEditor
                    label="nodes JSON"
                    value={form.nodesText}
                    onChange={(value) => setForm((current) => ({ ...current, nodesText: value }))}
                    minHeight="min-h-96"
                  />
                  <div className="grid gap-4">
                    <JsonEditor
                      label="edges JSON"
                      value={form.edgesText}
                      onChange={(value) => setForm((current) => ({ ...current, edgesText: value }))}
                      minHeight="min-h-44"
                    />
                    <JsonEditor
                      label="budget JSON"
                      value={form.budgetText}
                      onChange={(value) => setForm((current) => ({ ...current, budgetText: value }))}
                      minHeight="min-h-44"
                    />
                  </div>
                </div>

                <div className="flex flex-wrap items-center justify-end gap-3 border-t border-slate-100 pt-4">
                  <Button variant="secondary" onClick={resetForCreate}>
                    重置为新建
                  </Button>
                  <Button type="submit" variant="primary" loading={saving}>
                    {editingWorkflowId ? "保存修改" : "创建工作流"}
                  </Button>
                </div>
              </form>
            </section>

            <aside className="flex flex-col gap-5">
              <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="mb-4 flex items-center justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-semibold">运行工作流</h2>
                    <p className="mt-1 text-sm text-slate-500">输入 JSON 需包含 topic。</p>
                  </div>
                  <Button variant="primary" size="sm" loading={running} disabled={!selectedWorkflowId} onClick={() => void executeWorkflow()}>
                    运行
                  </Button>
                </div>
                <JsonEditor label="input JSON" value={runInputText} onChange={setRunInputText} minHeight="min-h-36" />
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
                          onClick={() => void selectRun(run)}
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
          </div>
        )}
      </div>
    </main>
  );
}

function JsonEditor({
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
