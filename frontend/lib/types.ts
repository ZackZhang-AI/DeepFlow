// DeepFlow 前端类型定义

export interface ResearchTask {
  task_id: string;
  topic: string;
  locale: string;
  status: ResearchStatus;
  current_step: number;
  total_steps: number;
  report_id: string | null;
  created_at: string;
  updated_at: string;
}

export type ResearchStatus =
  | "coordinating"
  | "planning"
  | "awaiting_confirmation"
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

export interface ResearchEvent {
  type: string;
  data: Record<string, unknown>;
}
