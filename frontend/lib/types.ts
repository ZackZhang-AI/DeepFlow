export interface AuthUser {
  user_id: string;
  username: string;
  created_at?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type?: string;
  expires_at?: string;
  user: AuthUser;
}

export interface ResearchTask {
  task_id: string;
  topic: string;
  locale: string;
  status: ResearchStatus;
  current_step: number;
  total_steps: number;
  report_id: string | null;
  clarification_questions: string[];
  knowledge_enabled: boolean;
  knowledge_document_ids: string[];
  created_at: string;
  updated_at: string;
  errors_json?: string;
  phase: ResearchPhase;
  progress: number;
  retryable: boolean;
  error_code: string;
  error_message: string;
  last_event_seq: number;
  plan: ResearchPlan | null;
  budget: TaskBudget;
  usage: TaskUsage;
  budget_percent: number;
}

export type BudgetProfile = "fast" | "standard" | "deep";

export interface TaskBudget {
  profile: BudgetProfile;
  max_steps: number;
  max_search_calls_per_step: number;
  max_crawl_pages_per_step: number;
  max_tokens: number;
  search_depth: "basic" | "advanced";
}

export interface TaskUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost_rmb: number;
  search_calls: number;
  crawl_calls: number;
  search_credits: number;
  planner_model: string;
  researcher_model: string;
  reporter_model: string;
}

export interface UsageSummary {
  total_tasks: number;
  completed_tasks: number;
  failed_tasks: number;
  total_cost_rmb: number;
  avg_cost_rmb: number;
  total_tokens: number;
  total_search_credits: number;
}

export type ResearchPhase = ResearchStatus | "reporting";

export interface ResearchFailure {
  retryable: boolean;
  error_code: string;
  error_message: string;
}

export interface ResearchProgress {
  phase: ResearchPhase;
  current_step: number;
  total_steps: number;
  progress: number;
}

export type TaskRecoveryAction = "reconnect" | "retry" | "edit_plan" | "new_research";

export type ResearchStatus =
  | "coordinating"
  | "clarifying"
  | "planning"
  | "awaiting_confirmation"
  | "queued"
  | "researching"
  | "generating_report"
  | "completed"
  | "failed";

export interface ResearchPlan {
  locale: string;
  has_enough_context: boolean;
  thought: string;
  title: string;
  steps: ResearchStep[];
}

export interface ResearchStep {
  title: string;
  description: string;
  need_search: boolean;
  step_type: "research" | "processing";
}

export interface Report {
  report_id: string;
  task_id: string;
  title: string;
  content_markdown: string;
  sources_count: number;
  tokens_used: number;
  cost_rmb: number;
  elapsed_seconds: number;
  created_at: string;
}

export interface ReportVersion {
  version_id: string;
  task_id: string;
  user_id?: string;
  change_note: string;
  content_length: number;
  created_at: string;
}

export interface ReportVersionDetail extends ReportVersion {
  content_markdown: string;
}

export interface RestoreReportVersionResponse {
  status: string;
  task_id: string;
  restored_version_id: string;
  backup_version_id: string;
  report_markdown: string;
}

export type ProseAction = "improve" | "expand" | "shorten";

export interface ProseResponse {
  result: string;
  tokens: number;
}

export interface ResearchEvent {
  sequence: number;
  type: string;
  data: Record<string, unknown>;
  created_at?: string;
}

export interface ReadinessItem {
  configured: boolean;
  ready: boolean;
  reason: string;
}

export interface ModelReadiness extends ReadinessItem {
  models: string[];
  probed: boolean;
  checked_at: string | null;
  error_code: string;
}

export interface ProviderReadiness {
  ready: boolean;
  model: ModelReadiness;
  search: ReadinessItem;
  embedding: ReadinessItem;
  docker: ReadinessItem;
  database: ReadinessItem;
}

export type KnowledgeDocumentStatus = "pending" | "processing" | "ready" | "failed";

export interface KnowledgeDocument {
  doc_id: string;
  title: string;
  source_name: string;
  source_type: string;
  content_length: number;
  status: KnowledgeDocumentStatus;
  chunk_count: number;
  error_message: string;
  created_at: string;
  updated_at: string;
}

export interface AgentRun {
  run_id: string;
  task_id: string;
  user_id?: string;
  agent_name: string;
  phase: string;
  status: string;
  input_summary: string;
  output_summary: string;
  tool_calls_json: string;
  prompt_tokens: number;
  completion_tokens: number;
  elapsed_seconds: number;
  error: string;
  created_at: string;
}

export type KnowledgeRetrievalMode = "hybrid" | "vector" | "keyword" | "rerank" | "stored" | string;

export interface KnowledgeChunk {
  chunk_id: string;
  doc_id: string;
  chunk_index: number;
  title: string;
  source_name: string;
  source_type: string;
  page_num: number | null;
  preview: string;
  content: string;
  metadata: Record<string, unknown>;
}

export interface KnowledgeSearchHit extends KnowledgeChunk {
  score: number;
  vector_score: number;
  keyword_score: number;
  rerank_score: number | null;
  retrieval_mode: KnowledgeRetrievalMode;
}

export interface Artifact {
  artifact_id: string;
  task_id: string;
  artifact_type: string;
  title: string;
  content?: string | null;
  metadata_json?: string;
  metadata?: Record<string, unknown>;
  download_url?: string;
  detail_url?: string;
  can_view?: boolean;
  is_file?: boolean;
  created_at?: string;
  updated_at?: string;
}

export type ToolCategory = "research" | "knowledge" | "code" | string;

export interface ToolDefinition {
  tool_id: string;
  name: string;
  description: string;
  category: ToolCategory;
  enabled: boolean;
  input_schema: Record<string, string>;
}

export interface ToolTestResult {
  success: boolean;
  input_summary: string;
  output_summary: string;
  elapsed_seconds: number;
  error: string;
  raw_output?: unknown;
}

export type WorkspaceRole = "owner" | "editor" | "viewer";

export interface Workspace {
  workspace_id: string;
  owner_user_id: string;
  name: string;
  description: string;
  role?: WorkspaceRole;
  members?: WorkspaceMember[];
  created_at: string;
  updated_at: string;
}

export interface WorkspaceMember {
  workspace_id?: string;
  user_id: string;
  username?: string;
  role: WorkspaceRole;
  created_at?: string;
}

export interface Project {
  project_id: string;
  workspace_id: string;
  owner_user_id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
}

export interface ReportComment {
  comment_id: string;
  task_id: string;
  user_id: string;
  username?: string;
  anchor: string;
  content: string;
  created_at: string;
}

export interface ShareLink {
  share_id: string;
  token: string;
  url: string;
  resource_type: "task_report" | "artifact";
  expires_at?: string;
}

export interface ResearchTemplateSummary {
  template_id: string;
  user_id: string;
  name: string;
  category: string;
  description: string;
  report_style: string;
  created_at: string;
  updated_at: string;
}

export interface ResearchTemplate extends ResearchTemplateSummary {
  clarification_questions: string[];
  plan_structure: Record<string, unknown>[];
  recommended_domains: string[];
}

export interface Workflow {
  workflow_id: string;
  user_id: string;
  name: string;
  description: string;
  nodes: Record<string, unknown>[];
  edges: Record<string, unknown>[];
  budget: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface WorkflowRun {
  run_id: string;
  workflow_id: string;
  user_id: string;
  status: "running" | "completed" | "failed" | string;
  input: Record<string, unknown>;
  outputs: Record<string, unknown>;
  error: string;
  created_at: string;
  updated_at: string;
}

export interface WorkflowNodeRun {
  node_run_id: string;
  run_id: string;
  workflow_id: string;
  user_id: string;
  node_id: string;
  node_type: string;
  status: string;
  input_summary: string;
  output_summary: string;
  tool_calls_json: string;
  elapsed_seconds: number;
  error: string;
  created_at: string;
}
