// DeepFlow API 客户端

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function createResearch(topic: string, locale = "zh-CN", maxSteps = 5) {
  const res = await fetch(`${API_BASE}/api/research-tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic, locale, max_steps: maxSteps }),
  });
  if (!res.ok) throw new Error(`Failed to create research: ${res.statusText}`);
  return res.json();
}

export async function getTask(taskId: string) {
  const res = await fetch(`${API_BASE}/api/research-tasks/${taskId}`);
  if (!res.ok) throw new Error(`Task not found: ${taskId}`);
  return res.json();
}

export async function getReport(taskId: string) {
  const res = await fetch(`${API_BASE}/api/reports/${taskId}`);
  if (!res.ok) throw new Error(`Report not found: ${taskId}`);
  return res.json();
}

export async function confirmPlan(taskId: string, action: "accept" | "edit" | "reject") {
  const res = await fetch(`${API_BASE}/api/research-tasks/${taskId}/confirm-plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  });
  return res.json();
}

export function subscribeToEvents(
  taskId: string,
  onEvent: (type: string, data: Record<string, unknown>) => void,
  onError?: (err: Event) => void,
) {
  const es = new EventSource(`${API_BASE}/api/research-tasks/${taskId}/events`);

  const eventTypes = [
    "coordinator.started", "planner.completed",
    "research.started", "step.started", "step.completed",
    "report.started", "report.completed", "error.fatal",
  ];

  for (const eventType of eventTypes) {
    es.addEventListener(eventType, (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      onEvent(eventType, data);
    });
  }

  if (onError) {
    es.onerror = onError;
  }

  return () => es.close();
}
