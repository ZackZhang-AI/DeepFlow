import type {
  AgentRun,
  Artifact,
  AuthResponse,
  AuthUser,
  KnowledgeChunk,
  KnowledgeDocument,
  KnowledgeSearchHit,
  ProseAction,
  ProseResponse,
  Report,
  ReportVersion,
  ReportVersionDetail,
  RestoreReportVersionResponse,
  ResearchTask,
  ResearchTemplate,
  ResearchTemplateSummary,
  Project,
  ReportComment,
  ShareLink,
  ToolDefinition,
  ToolTestResult,
  Workflow,
  WorkflowNodeRun,
  WorkflowRun,
  Workspace,
  WorkspaceRole,
} from "@/lib/types";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const TOKEN_KEY = "deepflow.auth.token";

export class AuthExpiredError extends Error {
  constructor(message = "登录状态已失效，请重新登录") {
    super(message);
    this.name = "AuthExpiredError";
  }
}

export function getAuthToken() {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setAuthToken(token: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearAuthToken() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
}

export function redirectToLogin() {
  if (typeof window === "undefined") return;
  const current = `${window.location.pathname}${window.location.search}`;
  const next = current.startsWith("/login") ? "/" : current;
  window.location.assign(`/login?next=${encodeURIComponent(next)}`);
}

function getErrorMessage(text: string, fallback: string) {
  if (!text) return fallback;
  try {
    const parsed = JSON.parse(text) as { detail?: unknown; message?: unknown; error?: unknown };
    const value = parsed.detail ?? parsed.message ?? parsed.error;
    if (typeof value === "string") return value;
    if (Array.isArray(value)) return value.map(String).join("\n");
  } catch {
    return text;
  }
  return text;
}

function withAuthHeader(headers: Headers, token: string | null) {
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return headers;
}

export async function authFetch(input: string, init: RequestInit = {}) {
  const token = getAuthToken();
  const headers = withAuthHeader(new Headers(init.headers), token);

  const res = await fetch(`${API_BASE}${input}`, {
    ...init,
    headers,
  });

  if (res.status === 401) {
    clearAuthToken();
    redirectToLogin();
    throw new AuthExpiredError();
  }

  return res;
}

async function readJson<T>(res: Response, fallback: string): Promise<T> {
  if (!res.ok) {
    throw new Error(getErrorMessage(await res.text(), fallback));
  }
  return res.json() as Promise<T>;
}

async function authJson<T>(input: string, init: RequestInit = {}, fallback = "请求失败") {
  const res = await authFetch(input, init);
  return readJson<T>(res, fallback);
}

async function publicJson<T>(input: string, init: RequestInit = {}, fallback = "请求失败") {
  const res = await fetch(`${API_BASE}${input}`, init);
  return readJson<T>(res, fallback);
}

export async function login(username: string, password: string) {
  const data = await publicJson<AuthResponse>(
    "/api/auth/login",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    },
    "登录失败",
  );
  setAuthToken(data.access_token);
  return data;
}

export async function register(username: string, password: string) {
  const data = await publicJson<AuthResponse>(
    "/api/auth/register",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    },
    "注册失败",
  );
  setAuthToken(data.access_token);
  return data;
}

export async function getCurrentUser() {
  return authJson<AuthUser>("/api/auth/me", undefined, "获取登录状态失败");
}

export async function createResearch(
  topic: string,
  locale = "zh-CN",
  maxSteps = 5,
  searchDomains: string[] = [],
  recencyDays?: number,
): Promise<ResearchTask> {
  return authJson<ResearchTask>(
    "/api/research-tasks",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        topic,
        locale,
        max_steps: maxSteps,
        search_domains: searchDomains,
        recency_days: recencyDays,
      }),
    },
    "创建研究失败",
  );
}

export async function answerClarifications(taskId: string, answers: Record<string, string>) {
  return authJson<ResearchTask>(`/api/research-tasks/${taskId}/clarifications`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answers }),
  });
}

export async function getTask(taskId: string) {
  return authJson<ResearchTask>(`/api/research-tasks/${taskId}`, undefined, `任务不存在：${taskId}`);
}

export async function listResearchTasks(limit = 50, offset = 0) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  return authJson<ResearchTask[]>(`/api/research-tasks?${params.toString()}`);
}

export async function getReport(taskId: string) {
  return authJson<Report>(`/api/reports/${taskId}`, undefined, `报告不存在：${taskId}`);
}

export async function confirmPlan(
  taskId: string,
  action: "accept" | "edit" | "reject",
  modifiedSteps?: unknown[],
) {
  return authJson(`/api/research-tasks/${taskId}/confirm-plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, modified_steps: modifiedSteps }),
  });
}

export async function saveReport(taskId: string, contentMarkdown: string, changeNote = "手动编辑") {
  return authJson(`/api/reports/${taskId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content_markdown: contentMarkdown, change_note: changeNote }),
  });
}

export async function rewriteReport(taskId: string, section: string, instruction: string) {
  return authJson(`/api/reports/${taskId}/rewrite`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ section, instruction }),
  });
}

export async function listReportVersions(taskId: string) {
  return authJson<ReportVersion[]>(`/api/reports/${taskId}/versions`);
}

export async function getReportVersion(versionId: string) {
  return authJson<ReportVersionDetail>(`/api/reports/versions/${versionId}`);
}

export async function restoreReportVersion(taskId: string, versionId: string) {
  return authJson<RestoreReportVersionResponse>(`/api/reports/${taskId}/versions/${versionId}/restore`, {
    method: "POST",
  });
}

export async function processProse(action: ProseAction, text: string, instruction = "") {
  return authJson<ProseResponse>(`/api/artifacts/prose/${action}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, instruction }),
  });
}

export async function listKnowledgeDocuments() {
  return authJson<KnowledgeDocument[]>("/api/knowledge-documents");
}

export async function createKnowledgeDocument(title: string, content: string) {
  return authJson<KnowledgeDocument>("/api/knowledge-documents", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, content, source_type: "text" }),
  });
}

export async function uploadKnowledgeDocument(file: File) {
  const form = new FormData();
  form.append("file", file);
  return authJson<KnowledgeDocument>("/api/knowledge-documents/upload", {
    method: "POST",
    body: form,
  });
}

export async function deleteKnowledgeDocument(docId: string) {
  return authJson(`/api/knowledge-documents/${docId}`, {
    method: "DELETE",
  });
}

export async function searchKnowledgeDocuments(query: string, limit = 5, rerank?: boolean) {
  const params = new URLSearchParams({ q: query, limit: String(limit) });
  if (rerank !== undefined) params.set("rerank", String(rerank));
  return authJson<KnowledgeSearchHit[]>(`/api/knowledge-documents/search?${params.toString()}`);
}

export async function listKnowledgeDocumentChunks(docId: string) {
  return authJson<KnowledgeChunk[]>(`/api/knowledge-documents/${docId}/chunks`);
}

export async function reindexKnowledgeDocument(docId: string) {
  return authJson<KnowledgeDocument>(`/api/knowledge-documents/${docId}/reindex`, {
    method: "POST",
  });
}

export async function listAgentRuns(taskId: string) {
  return authJson<AgentRun[]>(`/api/research-tasks/${taskId}/agent-runs`);
}

export async function listTaskArtifacts(taskId: string) {
  return authJson<Artifact[]>(`/api/artifacts/${taskId}`);
}

export async function listTools() {
  return authJson<ToolDefinition[]>("/api/tools");
}

export async function setToolEnabled(toolId: string, enabled: boolean) {
  return authJson<ToolDefinition>(`/api/tools/${toolId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
  });
}

export async function testTool(toolId: string, input: Record<string, unknown>) {
  return authJson<ToolTestResult>(`/api/tools/${toolId}/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ input }),
  });
}

export async function listWorkspaces() {
  return authJson<Workspace[]>("/api/workspaces");
}

export async function createWorkspace(name: string, description = "") {
  return authJson<Workspace>("/api/workspaces", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description }),
  });
}

export async function getWorkspace(workspaceId: string) {
  return authJson<Workspace>(`/api/workspaces/${workspaceId}`);
}

export async function addWorkspaceMember(workspaceId: string, username: string, role: WorkspaceRole) {
  return authJson(`/api/workspaces/${workspaceId}/members`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, role }),
  });
}

export async function listProjects(workspaceId: string) {
  return authJson<Project[]>(`/api/workspaces/${workspaceId}/projects`);
}

export async function createProject(workspaceId: string, name: string, description = "") {
  return authJson<Project>(`/api/workspaces/${workspaceId}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description }),
  });
}

export async function addReportComment(taskId: string, content: string, anchor = "") {
  return authJson<ReportComment>("/api/workspaces/comments", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task_id: taskId, content, anchor }),
  });
}

export async function listReportComments(taskId: string) {
  return authJson<ReportComment[]>(`/api/workspaces/comments/${taskId}`);
}

export async function createShareLink(resourceType: "task_report" | "artifact", resourceId: string) {
  return authJson<ShareLink>("/api/share-links", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ resource_type: resourceType, resource_id: resourceId }),
  });
}

export async function listTemplates() {
  return authJson<ResearchTemplateSummary[]>("/api/templates");
}

export async function getTemplate(templateId: string) {
  return authJson<ResearchTemplate>(`/api/templates/${templateId}`);
}

export async function createTemplate(payload: Partial<ResearchTemplate>) {
  return authJson<ResearchTemplate>("/api/templates", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function updateTemplate(templateId: string, payload: Partial<ResearchTemplate>) {
  return authJson<ResearchTemplate>(`/api/templates/${templateId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteTemplate(templateId: string) {
  return authJson(`/api/templates/${templateId}`, { method: "DELETE" });
}

export async function startResearchFromTemplate(templateId: string, topic: string, locale = "zh-CN") {
  return authJson<ResearchTask>(`/api/templates/${templateId}/start-research`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic, locale }),
  });
}

export async function listWorkflows() {
  return authJson<Workflow[]>("/api/workflows");
}

export async function getWorkflow(workflowId: string) {
  return authJson<Workflow>(`/api/workflows/${workflowId}`);
}

export async function createWorkflow(payload: Partial<Workflow>) {
  return authJson<Workflow>("/api/workflows", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function updateWorkflow(workflowId: string, payload: Partial<Workflow>) {
  return authJson<Workflow>(`/api/workflows/${workflowId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteWorkflow(workflowId: string) {
  return authJson(`/api/workflows/${workflowId}`, { method: "DELETE" });
}

export async function runWorkflow(workflowId: string, input: Record<string, unknown>) {
  return authJson<WorkflowRun>(`/api/workflows/${workflowId}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ input }),
  });
}

export async function listWorkflowRuns(workflowId: string) {
  return authJson<WorkflowRun[]>(`/api/workflows/${workflowId}/runs`);
}

export async function listWorkflowTrace(runId: string) {
  return authJson<WorkflowNodeRun[]>(`/api/workflows/runs/${runId}/trace`);
}

export async function downloadWithAuth(path: string, filename: string) {
  const res = await authFetch(path);
  if (!res.ok) throw new Error(getErrorMessage(await res.text(), "下载失败"));
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function subscribeToEvents(
  taskId: string,
  onEvent: (type: string, data: Record<string, unknown>) => void,
  onError?: (err: Event) => void,
) {
  const params = new URLSearchParams();
  const token = getAuthToken();
  if (token) params.set("token", token);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  const es = new EventSource(`${API_BASE}/api/research-tasks/${taskId}/events${suffix}`);

  const eventTypes = [
    "coordinator.started",
    "planner.completed",
    "research.started",
    "step.started",
    "step.completed",
    "report.started",
    "report.completed",
    "error.fatal",
  ];

  for (const eventType of eventTypes) {
    es.addEventListener(eventType, (e: MessageEvent) => {
      onEvent(eventType, JSON.parse(e.data));
    });
  }

  if (onError) es.onerror = onError;
  return () => es.close();
}
