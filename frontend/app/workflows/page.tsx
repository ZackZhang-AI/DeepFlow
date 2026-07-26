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
import { WorkflowEditor, type WorkflowFormState } from "@/components/workflows/WorkflowEditor";
import { WorkflowList } from "@/components/workflows/WorkflowList";
import { WorkflowRunsPanel } from "@/components/workflows/WorkflowRunsPanel";
import type { Workflow, WorkflowNodeRun, WorkflowRun } from "@/lib/types";

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
            <WorkflowList
              workflows={workflows}
              selectedWorkflowId={selectedWorkflowId}
              onSelect={(workflowId) => void selectWorkflow(workflowId)}
            />
            <WorkflowEditor
              editingWorkflowId={editingWorkflowId}
              selectedWorkflow={selectedSummary}
              form={form}
              formError={formError}
              saving={saving}
              deleting={Boolean(selectedSummary && deletingId === selectedSummary.workflow_id)}
              onChange={setForm}
              onSubmit={(event) => void saveWorkflow(event)}
              onDelete={() => selectedSummary && void removeWorkflow(selectedSummary.workflow_id)}
              onReset={resetForCreate}
            />
            <WorkflowRunsPanel
              selectedWorkflowId={selectedWorkflowId}
              runInputText={runInputText}
              running={running}
              runs={runs}
              selectedRun={selectedRun}
              trace={trace}
              onRunInputChange={setRunInputText}
              onRun={() => void executeWorkflow()}
              onSelectRun={(run) => void selectRun(run)}
            />
          </div>
        )}
      </div>
    </main>
  );
}
